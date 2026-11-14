"""기기·배치도 위치·포인팅 방향 영역 API. 조회는 로그인 사용자, 변경은 ADMIN."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import Field, model_validator

from server.api import (
    DEVICE_TYPE_PATTERN,
    ID_PATTERN,
    AdminUser,
    CurrentUser,
    DeviceServiceDep,
    GestureMappingServiceDep,
    PatchModel,
    StrictModel,
    ok,
)
from server.services.device_service import ANGLE_MAX, ANGLE_MIN, MAP_MAX, MAP_MIN, device_to_dict, mapping_to_dict
from shared.constants import API_PREFIX
from shared.types import IntentAction


class MapPosition(StrictModel):
    x: float = Field(ge=MAP_MIN, le=MAP_MAX)
    y: float = Field(ge=MAP_MIN, le=MAP_MAX)


class PointingRegion(StrictModel):
    min_angle_deg: float = Field(ge=ANGLE_MIN, le=ANGLE_MAX)
    max_angle_deg: float = Field(ge=ANGLE_MIN, le=ANGLE_MAX)

    @model_validator(mode="after")
    def _check_order(self):
        if self.min_angle_deg >= self.max_angle_deg:
            raise ValueError("min_angle_deg는 max_angle_deg보다 작아야 합니다.")
        return self


class DeviceCreate(StrictModel):
    device_id: str | None = Field(default=None, pattern=ID_PATTERN)
    room_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    device_type: str = Field(pattern=DEVICE_TYPE_PATTERN)
    map_position: MapPosition
    pointing_region: PointingRegion
    enabled: bool = True

    def to_fields(self) -> dict[str, Any]:
        return {"device_id": self.device_id, "room_id": self.room_id, "name": self.name,
                "device_type": self.device_type, "enabled": self.enabled,
                **_geometry_fields(self.map_position, self.pointing_region)}


class DeviceUpdate(PatchModel):
    NON_NULLABLE = frozenset({"room_id", "name", "device_type", "map_position", "pointing_region", "enabled"})
    room_id: str | None = Field(default=None, pattern=ID_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    device_type: str | None = Field(default=None, pattern=DEVICE_TYPE_PATTERN)
    map_position: MapPosition | None = None
    pointing_region: PointingRegion | None = None
    enabled: bool | None = None

    def to_changes(self) -> dict[str, Any]:
        changes = {name: getattr(self, name) for name in self.model_fields_set
                   if name not in ("map_position", "pointing_region")}
        changes.update(_geometry_fields(self.map_position, self.pointing_region))
        return changes


def _geometry_fields(position: MapPosition | None, region: PointingRegion | None) -> dict[str, float]:
    fields: dict[str, float] = {}
    if position is not None:
        fields.update(map_x=position.x, map_y=position.y)
    if region is not None:
        fields.update(min_angle_deg=region.min_angle_deg, max_angle_deg=region.max_angle_deg)
    return fields


router = APIRouter(prefix=f"{API_PREFIX}/devices", tags=["devices"])


@router.get("")
def list_devices(_user: CurrentUser, service: DeviceServiceDep, room_id: str | None = None,
                 enabled: bool | None = None) -> dict:
    return ok([device_to_dict(device) for device in service.list(room_id=room_id, enabled=enabled)])


@router.post("", status_code=201)
def create_device(body: DeviceCreate, _admin: AdminUser, service: DeviceServiceDep) -> dict:
    return ok(device_to_dict(service.create(**body.to_fields())))


@router.get("/{device_id}")
def get_device(device_id: str, _user: CurrentUser, service: DeviceServiceDep) -> dict:
    return ok(device_to_dict(service.get(device_id)))


@router.patch("/{device_id}")
def update_device(device_id: str, body: DeviceUpdate, _admin: AdminUser, service: DeviceServiceDep) -> dict:
    return ok(device_to_dict(service.update(device_id, body.to_changes())))


@router.delete("/{device_id}", status_code=204)
def delete_device(device_id: str, _admin: AdminUser, service: DeviceServiceDep) -> Response:
    service.delete(device_id)
    return Response(status_code=204)


# --- 제스처·명령 매핑 조회(모든 로그인 사용자)·수정(ADMIN) API.

class GestureMappingUpdate(PatchModel):
    NON_NULLABLE = frozenset({"action", "enabled"})
    action: IntentAction | None = None
    enabled: bool | None = None


mappings_router = APIRouter(prefix=f"{API_PREFIX}/gesture-mappings", tags=["gesture-mappings"])


@mappings_router.get("")
def list_mappings(_user: CurrentUser, service: GestureMappingServiceDep) -> dict:
    return ok([mapping_to_dict(mapping) for mapping in service.list()])


@mappings_router.patch("/{gesture}")
def update_mapping(gesture: str, body: GestureMappingUpdate, _admin: AdminUser,
                   service: GestureMappingServiceDep) -> dict:
    return ok(mapping_to_dict(service.update(gesture, body.model_dump(exclude_unset=True))))
