"""기기 등록, 위치 매핑, 상태 조회 로직을 처리한다.

방향 영역(pointing_region)은 AI 의도 판단 모듈의 ``device_matcher``와 같은 기준을 쓴다.
각도는 화면 좌표 기준 ``atan2(dy, dx)``이며 오른쪽 0°, 아래 +90°, 위 -90°이다.
``min_angle_deg <= 각도 <= max_angle_deg``이면 해당 기기 영역으로 본다.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from server.db.models import Device
from server.db.repositories import DeviceRepository
from server.intent.device_matcher import DeviceRegion
from server.services.errors import reject_unknown_fields, web_error
from server.services.events import EventHub
from server.services.room_service import RoomService
from shared.types import DeviceConnectionStatus, DeviceState, new_id, now_ms

# 배치도 좌표와 포인팅 각도의 허용 범위. API 스키마(server/api/schemas.py)도 이 값을 쓴다.
MAP_MIN, MAP_MAX = 0.0, 1.0
ANGLE_MIN, ANGLE_MAX = -180.0, 180.0
GEOMETRY_FIELDS = ("map_x", "map_y", "min_angle_deg", "max_angle_deg")
UPDATABLE_FIELDS = frozenset(
    {"room_id", "name", "device_type", "enabled", *GEOMETRY_FIELDS}
)


def device_to_dict(device: Device) -> dict[str, Any]:
    return {
        "device_id": device.device_id,
        "room_id": device.room_id,
        "name": device.name,
        "device_type": device.device_type,
        "map_position": {"x": device.map_x, "y": device.map_y},
        "pointing_region": {
            "min_angle_deg": device.min_angle_deg,
            "max_angle_deg": device.max_angle_deg,
        },
        "enabled": device.enabled,
        "state": device.state,
        "connection_status": device.connection_status,
        "state_updated_at_ms": device.state_updated_at_ms,
        "created_at_ms": device.created_at_ms,
        "updated_at_ms": device.updated_at_ms,
    }


def _state_event_data(device: Device) -> dict[str, Any]:
    return {
        "device_id": device.device_id,
        "state": device.state,
        "connection_status": device.connection_status,
        "updated_at_ms": device.state_updated_at_ms,
    }


def _validate_geometry(values: Mapping[str, float]) -> None:
    """API를 거치지 않고 서비스를 직접 부르는 경우까지 같은 범위를 지킨다."""
    if not (
        MAP_MIN <= values["map_x"] <= MAP_MAX and MAP_MIN <= values["map_y"] <= MAP_MAX
    ):
        raise web_error("INVALID_SCHEMA", "map_position은 0.0~1.0 범위여야 합니다.")
    if not (
        ANGLE_MIN <= values["min_angle_deg"] < values["max_angle_deg"] <= ANGLE_MAX
    ):
        raise web_error(
            "INVALID_SCHEMA",
            "pointing_region은 -180~180 범위에서 min_angle_deg < max_angle_deg여야 합니다.",
        )


class DeviceService:
    def __init__(self, session: Session, events: EventHub | None = None) -> None:
        self.session = session
        self.events = events
        self.devices = DeviceRepository(session)
        self.rooms = RoomService(session)

    def list(
        self, room_id: str | None = None, enabled: bool | None = None
    ) -> list[Device]:
        return self.devices.list(room_id=room_id, enabled=enabled)

    def get(self, device_id: str, correlation_id: str | None = None) -> Device:
        device = self.devices.get(device_id)
        if device is None:
            raise web_error("DEVICE_NOT_FOUND", correlation_id=correlation_id)
        return device

    def create(
        self,
        *,
        room_id: str,
        name: str,
        device_type: str,
        map_x: float,
        map_y: float,
        min_angle_deg: float,
        max_angle_deg: float,
        enabled: bool = True,
        device_id: str | None = None,
    ) -> Device:
        if device_id and self.devices.get(device_id) is not None:
            raise web_error("DEVICE_ALREADY_EXISTS")
        self.rooms.get(room_id)
        geometry = {
            "map_x": map_x,
            "map_y": map_y,
            "min_angle_deg": min_angle_deg,
            "max_angle_deg": max_angle_deg,
        }
        _validate_geometry(geometry)
        timestamp = now_ms()
        device = self.devices.add(
            Device(
                device_id=device_id or new_id(),
                room_id=room_id,
                name=name,
                device_type=device_type,
                enabled=enabled,
                state=DeviceState.UNKNOWN.value,
                connection_status=DeviceConnectionStatus.OFFLINE.value,
                created_at_ms=timestamp,
                updated_at_ms=timestamp,
                **geometry,
            )
        )
        self.session.commit()
        return device

    def update(self, device_id: str, changes: dict[str, Any]) -> Device:
        device = self.get(device_id)
        reject_unknown_fields(changes, UPDATABLE_FIELDS)
        if "room_id" in changes:
            self.rooms.get(changes["room_id"])
        # 바꾼 뒤의 값으로 먼저 검사해, 잘못된 값이 세션에 남지 않게 한다.
        _validate_geometry(
            {
                field: changes.get(field, getattr(device, field))
                for field in GEOMETRY_FIELDS
            }
        )
        for field, value in changes.items():
            setattr(device, field, value)
        device.updated_at_ms = now_ms()
        self.session.commit()
        return device

    def delete(self, device_id: str) -> None:
        self.devices.delete(self.get(device_id))
        self.session.commit()

    # MQTT 상태 반영 ---------------------------------------------------------

    def apply_state(
        self,
        device_id: str,
        *,
        state: DeviceState | str | None = None,
        connection_status: DeviceConnectionStatus | str | None = None,
        updated_at_ms: int | None = None,
    ) -> tuple[Device, bool]:
        """커밋하지 않고 상태만 바꾼다. 값이 실제로 바뀌었는지도 돌려준다(다른 서비스와 한 번에 커밋할 때)."""
        device = self.get(device_id)
        before = (device.state, device.connection_status)
        if state is not None:
            device.state = DeviceState(state).value
        if connection_status is not None:
            device.connection_status = DeviceConnectionStatus(connection_status).value
        device.state_updated_at_ms = updated_at_ms or now_ms()
        return device, (device.state, device.connection_status) != before

    def update_state(
        self, device_id: str, state: DeviceState | str, updated_at_ms: int | None = None
    ) -> Device:
        """MQTT state 수신 시 호출한다. 값이 바뀐 경우에만 이벤트를 보낸다."""
        return self._commit(
            *self.apply_state(device_id, state=state, updated_at_ms=updated_at_ms)
        )

    def update_connection_status(
        self,
        device_id: str,
        status: DeviceConnectionStatus | str,
        timestamp_ms: int | None = None,
    ) -> Device:
        """MQTT status(LWT) 수신 시 호출한다."""
        return self._commit(
            *self.apply_state(
                device_id, connection_status=status, updated_at_ms=timestamp_ms
            )
        )

    def publish_state(self, device: Device) -> None:
        if self.events is not None:
            self.events.publish("device.state_changed", _state_event_data(device))

    def pointing_regions(self) -> list[DeviceRegion]:
        """의도 판단 모듈에 넘길 사용 중인 기기의 방향 영역."""
        return [
            DeviceRegion(device.device_id, device.min_angle_deg, device.max_angle_deg)
            for device in self.devices.list(enabled=True)
        ]

    def _commit(self, device: Device, changed: bool) -> Device:
        self.session.commit()
        if changed:
            self.publish_state(device)
        return device
