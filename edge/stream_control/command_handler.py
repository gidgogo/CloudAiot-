"""송출 원격 ON/OFF용 MQTT cmd 페이로드를 검증·실행하고 ACK를 만든다. MQTT 연결과 분리해 단위 테스트할 수 있게 했다.

공통 인터페이스 v1 11장 처리 순서:
1. 형식·버전 검사 → 실패 시 ERROR ACK (command_id를 알 수 없으면 ACK 없이 폐기)
2. 시간 동기화 확인 (11.7) → 미동기화면 ERROR ACK, 송출 상태 변경 안 함
3. 유효시간 확인 (11.5) → expires_at_ms 경과 시 EXPIRED ACK
4. 중복 확인 (11.6) → 이미 처리한 command_id면 DUPLICATE ACK, 재실행 금지
5. 송출 켜기/끄기 → command_id 저장 → OK ACK
"""
from __future__ import annotations

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from shared.constants import SCHEMA_VERSION
from shared.types import AckResult, DeviceState, DeviceStateMessage, IntentAction, MqttAck, now_ms

log = logging.getLogger(__name__)

# 최근 처리한 command_id를 이 개수만큼 기억한다. 명령 유효시간이 5초라 그보다 오래된 재전송은 EXPIRED로 걸러진다.
DEDUP_CAPACITY = 1024

# 규격 12.2에 있는 코드
ERR_INVALID_SCHEMA = "INVALID_SCHEMA"
ERR_UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
ERR_DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
ERR_COMMAND_EXPIRED = "COMMAND_EXPIRED"
ERR_COMMAND_DUPLICATE = "COMMAND_DUPLICATE"
ERR_INTERNAL = "INTERNAL_ERROR"
# 규격 12.2에 없는 코드. 통합 담당과 합의 필요 (docs/edge-stream-control.md 참고)
ERR_TIME_NOT_SYNCED = "TIME_NOT_SYNCED"

class Switch(Protocol):
    """켜고 끌 수 있는 대상. 실제로는 송출 프로세스 스위치(``switch.ProcessSwitch``)다."""

    @property
    def is_on(self) -> bool: ...
    def set(self, on: bool) -> None: ...


_REQUIRED = ("command_id", "device_id", "action", "issued_at_ms", "expires_at_ms")


@dataclass(slots=True)
class HandleResult:
    ack: MqttAck | None                 # None이면 ACK를 보낼 수 없는 메시지(command_id 없음)
    state: DeviceStateMessage | None    # 상태가 바뀌었을 때만 값이 있다 → state Topic에 retain 발행


class CommandHandler:
    def __init__(
        self,
        device_id: str,
        switch: Switch,
        *,
        time_synced: Callable[[], bool] = lambda: True,
        clock_ms: Callable[[], int] = now_ms,
        dedup_capacity: int = DEDUP_CAPACITY,
    ) -> None:
        self.device_id = device_id
        self.switch = switch
        self._time_synced = time_synced
        self._clock_ms = clock_ms
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._dedup_capacity = dedup_capacity

    def current_state(self) -> DeviceState:
        return DeviceState.ON if self.switch.is_on else DeviceState.OFF

    def state_message(self) -> DeviceStateMessage:
        return DeviceStateMessage(device_id=self.device_id, state=self.current_state(), updated_at_ms=self._clock_ms())

    def handle(self, raw: str | bytes) -> HandleResult:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            log.warning("cmd is not valid JSON; dropped")
            return HandleResult(None, None)
        if not isinstance(payload, dict) or not isinstance(payload.get("command_id"), str) or not payload["command_id"]:
            log.warning("cmd has no command_id; dropped")
            return HandleResult(None, None)

        command_id = payload["command_id"]
        correlation_id = payload.get("correlation_id") if isinstance(payload.get("correlation_id"), str) else ""

        def ack(result: AckResult, error_code: str | None = None) -> HandleResult:
            return HandleResult(
                MqttAck(
                    command_id=command_id,
                    correlation_id=correlation_id,
                    device_id=self.device_id,
                    result=result,
                    state=self.current_state(),
                    processed_at_ms=self._clock_ms(),
                    error_code=error_code,
                ),
                None,
            )

        # 1. 형식·버전
        if payload.get("schema_version") != SCHEMA_VERSION:
            return ack(AckResult.ERROR, ERR_UNSUPPORTED_VERSION)
        if any(key not in payload for key in _REQUIRED):
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        if payload["device_id"] != self.device_id:
            return ack(AckResult.ERROR, ERR_DEVICE_NOT_FOUND)
        try:
            action = IntentAction(payload["action"])
            expires_at_ms = int(payload["expires_at_ms"])
        except (TypeError, ValueError):
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        if action not in (IntentAction.ON, IntentAction.OFF):  # HELP는 MQTT로 오지 않는다 (11.2)
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)

        # 2. 시간 동기화
        if not self._time_synced():
            log.warning("clock not synchronized; command %s not executed", command_id)
            return ack(AckResult.ERROR, ERR_TIME_NOT_SYNCED)

        # 3. 유효시간
        if self._clock_ms() > expires_at_ms:
            return ack(AckResult.EXPIRED, ERR_COMMAND_EXPIRED)

        # 4. 중복
        if command_id in self._seen:
            return ack(AckResult.DUPLICATE, ERR_COMMAND_DUPLICATE)

        # 5. 실행
        before = self.switch.is_on
        try:
            self.switch.set(action is IntentAction.ON)
        except Exception:  # 프로세스 시작 실패 등. 원인은 로그로 남기고 서버에는 ERROR로 알린다.
            log.exception("switch %s failed for command %s", self.device_id, command_id)
            self._remember(command_id)
            return ack(AckResult.ERROR, ERR_INTERNAL)
        self._remember(command_id)
        result = ack(AckResult.OK)
        if self.switch.is_on != before:
            result.state = self.state_message()
        return result

    def _remember(self, command_id: str) -> None:
        self._seen[command_id] = None
        while len(self._seen) > self._dedup_capacity:
            self._seen.popitem(last=False)


def payload_of(message: Any) -> str:
    """dataclass 메시지를 MQTT 페이로드 JSON 문자열로 바꾼다."""
    return json.dumps(message.as_dict())
