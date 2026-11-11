"""도움 요청 생성과 처리 상태 변경을 담당한다.

도움 요청은 MQTT 기기 제어와 분리된 경로로 처리한다.
상태는 CREATED → CONFIRMED → COMPLETED 순서로만 바뀐다.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from sqlalchemy.orm import Session

from server.db.models import HelpRequestRecord
from server.db.repositories import HelpRequestRepository, RoomRepository
from server.services.errors import web_error
from server.services.events import EventHub
from server.services.room_service import RoomService
from server.services.user_service import UserService
from shared.constants import SCHEMA_VERSION
from shared.types import HelpSource, HelpStatus, UserRole, new_id, now_ms

NEXT_STATUS = {
    HelpStatus.CREATED.value: HelpStatus.CONFIRMED.value,
    HelpStatus.CONFIRMED.value: HelpStatus.COMPLETED.value,
}


def help_request_to_dict(record: HelpRequestRecord) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": record.request_id,
        "correlation_id": record.correlation_id,
        "user_id": record.user_id,
        "source": record.source,
        "status": record.status,
        "created_at_ms": record.created_at_ms,
        "confirmed_at_ms": record.confirmed_at_ms,
        "confirmed_by": record.confirmed_by,
        "completed_at_ms": record.completed_at_ms,
        "completed_by": record.completed_by,
    }


def _event_data(record: HelpRequestRecord) -> dict[str, Any]:
    # 공통 규격 10.3의 필드만 보낸다.
    return {
        "request_id": record.request_id,
        "user_id": record.user_id,
        "status": record.status,
    }


class HelpService:
    def __init__(self, session: Session, events: EventHub | None = None) -> None:
        self.session = session
        self.events = events
        self.requests = HelpRequestRepository(session)
        self.users = UserService(session)
        self.rooms = RoomService(session)
        self.room_records = RoomRepository(session)

    def list(
        self,
        status: HelpStatus | str | None = None,
        user_ids: Collection[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HelpRequestRecord], int]:
        status_value = HelpStatus(status).value if status else None
        return self.requests.list(
            status=status_value, user_ids=user_ids, limit=limit, offset=offset
        )

    def get(self, request_id: str) -> HelpRequestRecord:
        record = self.requests.get(request_id)
        if record is None:
            raise web_error("HELP_REQUEST_NOT_FOUND")
        return record

    def create(
        self,
        *,
        user_id: str,
        source: HelpSource | str,
        correlation_id: str | None = None,
    ) -> HelpRequestRecord:
        """웹 요청 또는 HELP 제스처(의도 판단 모듈)에서 호출한다."""
        self.users.require_role(
            user_id,
            UserRole.USER,
            "도움 요청은 USER 역할 사용자만 만들 수 있습니다.",
            correlation_id,
        )
        request_id = new_id()
        record = self.requests.add(
            HelpRequestRecord(
                request_id=request_id,
                correlation_id=correlation_id or request_id,
                user_id=user_id,
                source=HelpSource(source).value,
                status=HelpStatus.CREATED.value,
                created_at_ms=now_ms(),
            )
        )
        self.session.commit()
        self._publish("help.created", record)
        return record

    def create_from_gesture(
        self,
        correlation_id: str,
        room_id: str | None = None,
        user_id: str | None = None,
    ) -> HelpRequestRecord:
        """HELP 의도 확정 시 의도 판단 모듈이 호출한다.

        사용자 결정 순서: user_id 지정 → room_id의 방 사용자 → 방 사용자가 한 명뿐이면 그 사용자.
        """
        if user_id is None:
            user_id = self._resolve_gesture_user(room_id, correlation_id)
        return self.create(
            user_id=user_id, source=HelpSource.GESTURE, correlation_id=correlation_id
        )

    def _resolve_gesture_user(self, room_id: str | None, correlation_id: str) -> str:
        if room_id is not None:
            room = self.rooms.get(room_id, correlation_id)
            if room.resident_user_id:
                return room.resident_user_id
            raise web_error(
                "HELP_USER_UNKNOWN",
                "방에 사용자가 지정되지 않았습니다.",
                correlation_id=correlation_id,
            )
        residents = {
            room.resident_user_id for room in self.room_records.with_resident()
        }
        if len(residents) == 1:
            return residents.pop()
        raise web_error("HELP_USER_UNKNOWN", correlation_id=correlation_id)

    def update_status(
        self, request_id: str, status: HelpStatus | str, actor_id: str | None = None
    ) -> HelpRequestRecord:
        record = self.get(request_id)
        status = HelpStatus(status).value
        if NEXT_STATUS.get(record.status) != status:
            raise web_error(
                "INVALID_STATUS_TRANSITION",
                f"{record.status} 상태에서 {status}(으)로 바꿀 수 없습니다.",
                correlation_id=record.correlation_id,
            )
        timestamp = now_ms()
        if status == HelpStatus.CONFIRMED.value:
            record.confirmed_at_ms, record.confirmed_by = timestamp, actor_id
        else:
            record.completed_at_ms, record.completed_by = timestamp, actor_id
        record.status = status
        self.session.commit()
        self._publish("help.updated", record)
        return record

    def _publish(self, event_type: str, record: HelpRequestRecord) -> None:
        if self.events is not None:
            self.events.publish(
                event_type,
                _event_data(record),
                correlation_id=record.correlation_id,
                audience_user_id=record.user_id,
            )
