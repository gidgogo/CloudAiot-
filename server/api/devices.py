"""기기·배치도 위치·포인팅 방향 영역 API. 조회는 로그인 사용자, 변경은 ADMIN."""

from fastapi import APIRouter, Response

from server.api.deps import AdminUser, CurrentUser, DeviceServiceDep
from server.api.schemas import DeviceCreate, DeviceUpdate, ok
from server.services.device_service import device_to_dict
from shared.constants import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/devices", tags=["devices"])


@router.get("")
def list_devices(
    _user: CurrentUser,
    service: DeviceServiceDep,
    room_id: str | None = None,
    enabled: bool | None = None,
) -> dict:
    return ok(
        [
            device_to_dict(device)
            for device in service.list(room_id=room_id, enabled=enabled)
        ]
    )


@router.post("", status_code=201)
def create_device(
    body: DeviceCreate, _admin: AdminUser, service: DeviceServiceDep
) -> dict:
    return ok(device_to_dict(service.create(**body.to_fields())))


@router.get("/{device_id}")
def get_device(device_id: str, _user: CurrentUser, service: DeviceServiceDep) -> dict:
    return ok(device_to_dict(service.get(device_id)))


@router.patch("/{device_id}")
def update_device(
    device_id: str, body: DeviceUpdate, _admin: AdminUser, service: DeviceServiceDep
) -> dict:
    return ok(device_to_dict(service.update(device_id, body.to_changes())))


@router.delete("/{device_id}", status_code=204)
def delete_device(
    device_id: str, _admin: AdminUser, service: DeviceServiceDep
) -> Response:
    service.delete(device_id)
    return Response(status_code=204)
