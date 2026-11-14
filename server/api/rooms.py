"""방 등록·조회·수정·삭제 API. 조회는 로그인 사용자, 변경은 ADMIN."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import Field

from server.api import ID_PATTERN, AdminUser, CurrentUser, PatchModel, RoomServiceDep, StrictModel, ok
from server.services.room_service import room_to_dict
from shared.constants import API_PREFIX

# --- x

class RoomCreate(StrictModel):
    room_id: str | None = Field(default=None, pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    resident_user_id: str | None = Field(default=None, pattern=ID_PATTERN)


class RoomUpdate(PatchModel):
    NON_NULLABLE = frozenset({"name"})
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    resident_user_id: str | None = Field(default=None, pattern=ID_PATTERN)


router = APIRouter(prefix=f"{API_PREFIX}/rooms", tags=["rooms"])


@router.get("")
def list_rooms(_user: CurrentUser, service: RoomServiceDep) -> dict:
    return ok([room_to_dict(room) for room in service.list()])


@router.post("", status_code=201)
def create_room(body: RoomCreate, _admin: AdminUser, service: RoomServiceDep) -> dict:
    return ok(room_to_dict(service.create(**body.model_dump())))


@router.get("/{room_id}")
def get_room(room_id: str, _user: CurrentUser, service: RoomServiceDep) -> dict:
    return ok(room_to_dict(service.get(room_id)))


@router.patch("/{room_id}")
def update_room(room_id: str, body: RoomUpdate, _admin: AdminUser, service: RoomServiceDep) -> dict:
    return ok(room_to_dict(service.update(room_id, body.model_dump(exclude_unset=True))))


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: str, _admin: AdminUser, service: RoomServiceDep) -> Response:
    service.delete(room_id)
    return Response(status_code=204)
