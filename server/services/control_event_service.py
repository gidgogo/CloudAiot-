"""제어 명령과 ACK 결과 이력을 관리한다.

IoT 모듈(server/iot)이 MQTT 명령 발행·ACK 수신·ACK 제한시간 초과 시 이 서비스를 호출한다.
지연시간(NFR-01)은 제스처 확정 시각(없으면 명령 발행 시각)부터 ACK 수신 시각까지로 계산한다.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from server.db.models import CommandStatus, ControlEvent
from server.db.repositories import ControlEventRepository
from server.services.device_service import DeviceService
from server.services.errors import web_error
from server.services.events import EventHub
from shared.types import (
    AckResult,
    CommandSource,
    DeviceState,
    IntentAction,
    MqttAck,
    MqttCommand,
    now_ms,
)

log = logging.getLogger(__name__)
SUCCESS_RESULTS = frozenset({AckResult.OK.value, AckResult.DUPLICATE.value})


def control_event_to_dict(event: ControlEvent) -> dict[str, Any]:
    return {
        "command_id": event.command_id,
        "correlation_id": event.correlation_id,
        "device_id": event.device_id,
        "action": event.action,
        "source": event.source,
        "status": event.status,
        "result": event.result,
        "error_code": event.error_code,
        "gesture_confirmed_at_ms": event.gesture_confirmed_at_ms,
        "command_published_at_ms": event.command_published_at_ms,
        "ack_received_at_ms": event.ack_received_at_ms,
        "latency_ms": event.latency_ms,
    }


def _event_data(event: ControlEvent) -> dict[str, Any]:
    return {
        "command_id": event.command_id,
        "device_id": event.device_id,
        "action": event.action,
        "status": event.status,
        "result": event.result,
        "error_code": event.error_code,
        "latency_ms": event.latency_ms,
    }


class ControlEventService:
    def __init__(self, session: Session, events: EventHub | None = None) -> None:
        self.session = session
        self.events = events
        self.records = ControlEventRepository(session)
        self.devices = DeviceService(session, events)

    def list(
        self, device_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[ControlEvent], int]:
        return self.records.list(device_id=device_id, limit=limit, offset=offset)

    def get(self, command_id: str) -> ControlEvent:
        record = self.records.get(command_id)
        if record is None:
            raise web_error("COMMAND_NOT_FOUND")
        return record

    def record_command(
        self,
        command: MqttCommand,
        gesture_confirmed_at_ms: int | None = None,
        published_at_ms: int | None = None,
    ) -> ControlEvent:
        """MQTT 명령을 발행한 직후 호출한다."""
        self.devices.get(command.device_id, correlation_id=command.correlation_id)
        if self.records.get(command.command_id) is not None:
            raise web_error(
                "COMMAND_ALREADY_EXISTS", correlation_id=command.correlation_id
            )
        record = self.records.add(
            ControlEvent(
                command_id=command.command_id,
                correlation_id=command.correlation_id or command.command_id,
                device_id=command.device_id,
                action=IntentAction(command.action).value,
                source=CommandSource(command.source).value,
                status=CommandStatus.PENDING.value,
                gesture_confirmed_at_ms=gesture_confirmed_at_ms,
                command_published_at_ms=published_at_ms or command.issued_at_ms,
            )
        )
        self.session.commit()
        log.info(
            "control command command_id=%s device_id=%s action=%s source=%s",
            record.command_id,
            record.device_id,
            record.action,
            record.source,
        )
        self._publish("command.created", record)
        return record

    def record_ack(
        self, ack: MqttAck, received_at_ms: int | None = None
    ) -> ControlEvent:
        """ESP32 ACK 수신 시 호출한다. 이미 끝난 명령(타임아웃 후 늦은 ACK 등)은 상태를 바꾸지 않는다."""
        record = self.get(ack.command_id)
        if record.status != CommandStatus.PENDING.value:
            return record
        received = received_at_ms or now_ms()
        record.result = AckResult(ack.result).value
        record.ack_received_at_ms = received
        record.latency_ms = max(
            0,
            received
            - (record.gesture_confirmed_at_ms or record.command_published_at_ms),
        )
        device_change = None
        if record.result in SUCCESS_RESULTS:
            record.status = CommandStatus.COMPLETED.value
            if ack.state != DeviceState.UNKNOWN:
                # 이력과 기기 상태를 한 번에 커밋한다(ACK 처리 경로는 지연시간에 민감하다).
                device_change = self.devices.apply_state(
                    record.device_id, state=ack.state, updated_at_ms=ack.processed_at_ms
                )
        else:
            record.status = CommandStatus.FAILED.value
            record.error_code = ack.error_code or (
                "COMMAND_EXPIRED"
                if record.result == AckResult.EXPIRED.value
                else "INTERNAL_ERROR"
            )
        self.session.commit()
        log.info(
            "control ack command_id=%s device_id=%s result=%s status=%s latency_ms=%s",
            record.command_id,
            record.device_id,
            record.result,
            record.status,
            record.latency_ms,
        )
        if device_change is not None and device_change[1]:
            self.devices.publish_state(device_change[0])
        completed = record.status == CommandStatus.COMPLETED.value
        self._publish("command.completed" if completed else "command.failed", record)
        return record

    def mark_timeout(self, command_id: str) -> ControlEvent:
        """ACK 제한시간(2초) 안에 응답이 없을 때 호출한다."""
        record = self.get(command_id)
        if record.status != CommandStatus.PENDING.value:
            return record
        record.status = CommandStatus.FAILED.value
        record.error_code = "ACK_TIMEOUT"
        self.session.commit()
        log.warning(
            "control ack timeout command_id=%s device_id=%s",
            record.command_id,
            record.device_id,
        )
        self._publish("command.failed", record)
        return record

    def _publish(self, event_type: str, record: ControlEvent) -> None:
        if self.events is not None:
            self.events.publish(
                event_type, _event_data(record), correlation_id=record.correlation_id
            )
