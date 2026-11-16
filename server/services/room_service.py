"""방 등록과 조회 관련 응용 로직을 처리한다."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from server.db.models import Room
from server.db.repositories import RoomRepository
from server.services import reject_unknown_fields, web_error
from server.services.user_service import UserService
from shared.types import UserRole, new_id, now_ms

UPDATABLE_FIELDS = frozenset({"name", "description", "resident_user_id"})


def room_to_dict(room: Room) -> dict[str, Any]:
    return {"room_id": room.room_id, "name": room.name, "description": room.description,
            "resident_user_id": room.resident_user_id,
            "created_at_ms": room.created_at_ms, "updated_at_ms": room.updated_at_ms}


class RoomService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.rooms = RoomRepository(session)
        self.users = UserService(session)

    def list(self) -> list[Room]:
        return self.rooms.list()

    def get(self, room_id: str, correlation_id: str | None = None) -> Room:
        room = self.rooms.get(room_id)
        if room is None:
            raise web_error("ROOM_NOT_FOUND", correlation_id=correlation_id)
        return room

    def create(self, *, name: str, room_id: str | None = None, description: str | None = None,
               resident_user_id: str | None = None) -> Room:
        if room_id and self.rooms.get(room_id) is not None:
            raise web_error("ROOM_ALREADY_EXISTS")
        self._check_resident(resident_user_id)
        timestamp = now_ms()
        room = self.rooms.add(Room(room_id=room_id or new_id(), name=name, description=description,
                                   resident_user_id=resident_user_id,
                                   created_at_ms=timestamp, updated_at_ms=timestamp))
        self.session.commit()
        return room

    def update(self, room_id: str, changes: dict[str, Any]) -> Room:
        room = self.get(room_id)
        reject_unknown_fields(changes, UPDATABLE_FIELDS)
        if "resident_user_id" in changes:
            self._check_resident(changes["resident_user_id"])
        for field, value in changes.items():
            setattr(room, field, value)
        room.updated_at_ms = now_ms()
        self.session.commit()
        return room

    def delete(self, room_id: str) -> None:
        room = self.get(room_id)
        if self.rooms.device_count(room_id):
            raise web_error("ROOM_NOT_EMPTY")
        self.rooms.delete(room)
        self.session.commit()

    def _check_resident(self, user_id: str | None) -> None:
        if user_id is not None:
            self.users.require_role(user_id, UserRole.USER, "방 사용자는 USER 역할이어야 합니다.")
