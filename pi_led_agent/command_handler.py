"""Validate v1 MQTT commands and apply only safe LED ON/OFF operations."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import json
from typing import Callable

from shared.constants import SCHEMA_VERSION
from shared.types import AckResult, DeviceState, DeviceStateMessage, IntentAction, MqttAck, now_ms

from pi_led_agent.led_controller import LedController

ERR_INVALID_SCHEMA = "INVALID_SCHEMA"
ERR_UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
ERR_DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
ERR_COMMAND_EXPIRED = "COMMAND_EXPIRED"
ERR_COMMAND_DUPLICATE = "COMMAND_DUPLICATE"
ERR_TIME_NOT_SYNCED = "TIME_NOT_SYNCED"
ERR_INTERNAL = "INTERNAL_ERROR"
REQUIRED_FIELDS = frozenset({
    "schema_version", "command_id", "correlation_id", "device_id", "action",
    "issued_at_ms", "expires_at_ms", "source",
})


@dataclass(slots=True)
class HandleResult:
    ack: MqttAck | None
    state: DeviceStateMessage | None


class CommandHandler:
    def __init__(
        self,
        device_id: str,
        led: LedController,
        *,
        time_synced: Callable[[], bool] = lambda: True,
        clock_ms: Callable[[], int] = now_ms,
        dedup_capacity: int = 1024,
    ) -> None:
        self.device_id = device_id
        self.led = led
        self._time_synced = time_synced
        self._clock_ms = clock_ms
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._dedup_capacity = dedup_capacity

    def state_message(self) -> DeviceStateMessage:
        state = DeviceState.ON if self.led.is_on else DeviceState.OFF
        return DeviceStateMessage(device_id=self.device_id, state=state, updated_at_ms=self._clock_ms())

    def handle(self, raw: str | bytes) -> HandleResult:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return HandleResult(None, None)
        if not isinstance(payload, dict) or not isinstance(payload.get("command_id"), str) or not payload["command_id"]:
            return HandleResult(None, None)

        command_id = payload["command_id"]
        correlation_id = payload.get("correlation_id") if isinstance(payload.get("correlation_id"), str) else ""

        def ack(result: AckResult, error_code: str | None = None) -> HandleResult:
            state = DeviceState.ON if self.led.is_on else DeviceState.OFF
            return HandleResult(
                MqttAck(command_id=command_id, correlation_id=correlation_id, device_id=self.device_id,
                        result=result, state=state, processed_at_ms=self._clock_ms(), error_code=error_code),
                None,
            )

        if payload.get("schema_version") != SCHEMA_VERSION:
            return ack(AckResult.ERROR, ERR_UNSUPPORTED_VERSION)
        if set(payload) != REQUIRED_FIELDS:
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        if payload["device_id"] != self.device_id:
            return ack(AckResult.ERROR, ERR_DEVICE_NOT_FOUND)
        if not all(isinstance(payload[name], str) and payload[name] for name in ("correlation_id", "source")):
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        if payload["source"] not in {"GESTURE", "WEB", "SYSTEM"}:
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        try:
            action = IntentAction(payload["action"])
            issued_at_ms = int(payload["issued_at_ms"])
            expires_at_ms = int(payload["expires_at_ms"])
        except (TypeError, ValueError):
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        if action not in {IntentAction.ON, IntentAction.OFF} or issued_at_ms < 0 or expires_at_ms < issued_at_ms:
            return ack(AckResult.ERROR, ERR_INVALID_SCHEMA)
        if not self._time_synced():
            return ack(AckResult.ERROR, ERR_TIME_NOT_SYNCED)
        if self._clock_ms() > expires_at_ms:
            return ack(AckResult.EXPIRED, ERR_COMMAND_EXPIRED)
        if command_id in self._seen:
            return ack(AckResult.DUPLICATE, ERR_COMMAND_DUPLICATE)

        before = self.led.is_on
        try:
            self.led.set(action is IntentAction.ON)
        except Exception:
            self._remember(command_id)
            return ack(AckResult.ERROR, ERR_INTERNAL)
        self._remember(command_id)
        result = ack(AckResult.OK)
        if self.led.is_on != before:
            result.state = self.state_message()
        return result

    def _remember(self, command_id: str) -> None:
        self._seen[command_id] = None
        while len(self._seen) > self._dedup_capacity:
            self._seen.popitem(last=False)


def payload_of(message: object) -> str:
    return json.dumps(message.as_dict())
