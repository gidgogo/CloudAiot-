"""REST 요청 본문 검증 모델.

응답은 각 서비스의 ``*_to_dict`` 함수가 만든다. 모든 응답은
``{"success": true, "data": ...}`` 형식이며, 목록 응답은 ``meta``에 페이지 정보를 담는다.
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.security.authentication import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH
from server.services.device_service import ANGLE_MAX, ANGLE_MIN, MAP_MAX, MAP_MIN
from shared.types import HelpStatus, IntentAction, UserRole

ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
DEVICE_TYPE_PATTERN = r"^[A-Z][A-Z0-9_]{0,31}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+$"
# 바이트 길이(72)는 서비스의 validate_password가 다시 검사한다.
Password = Annotated[
    str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_BYTES)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PatchModel(StrictModel):
    """PATCH 본문. 보낸 필드만 반영하며, NON_NULLABLE 필드에는 null을 허용하지 않는다."""

    NON_NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls(self):
        nulls = [
            name
            for name in self.model_fields_set
            if name in self.NON_NULLABLE and getattr(self, name) is None
        ]
        if nulls:
            raise ValueError(
                f"null로 바꿀 수 없는 필드입니다: {', '.join(sorted(nulls))}"
            )
        if not self.model_fields_set:
            raise ValueError("수정할 필드가 없습니다.")
        return self


def ok(data: Any, **meta: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"success": True, "data": data}
    if meta:
        body["meta"] = meta
    return body


# 방 ---------------------------------------------------------------------


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


# 기기 -------------------------------------------------------------------


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
        return {
            "device_id": self.device_id,
            "room_id": self.room_id,
            "name": self.name,
            "device_type": self.device_type,
            "enabled": self.enabled,
            **_geometry_fields(self.map_position, self.pointing_region),
        }


class DeviceUpdate(PatchModel):
    NON_NULLABLE = frozenset(
        {"room_id", "name", "device_type", "map_position", "pointing_region", "enabled"}
    )
    room_id: str | None = Field(default=None, pattern=ID_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    device_type: str | None = Field(default=None, pattern=DEVICE_TYPE_PATTERN)
    map_position: MapPosition | None = None
    pointing_region: PointingRegion | None = None
    enabled: bool | None = None

    def to_changes(self) -> dict[str, Any]:
        changes = {
            name: getattr(self, name)
            for name in self.model_fields_set
            if name not in ("map_position", "pointing_region")
        }
        changes.update(_geometry_fields(self.map_position, self.pointing_region))
        return changes


def _geometry_fields(
    position: MapPosition | None, region: PointingRegion | None
) -> dict[str, float]:
    fields: dict[str, float] = {}
    if position is not None:
        fields.update(map_x=position.x, map_y=position.y)
    if region is not None:
        fields.update(
            min_angle_deg=region.min_angle_deg, max_angle_deg=region.max_angle_deg
        )
    return fields


# 도움 요청 --------------------------------------------------------------


class HelpRequestCreate(StrictModel):
    # USER는 생략(본인). ADMIN이 대신 만들 때만 지정한다.
    user_id: str | None = Field(default=None, pattern=ID_PATTERN)
    correlation_id: str | None = Field(default=None, pattern=ID_PATTERN)


class HelpRequestUpdate(StrictModel):
    status: Literal[HelpStatus.CONFIRMED, HelpStatus.COMPLETED]


# 인증·사용자 --------------------------------------------------------------


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(StrictModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: Password


class UserCreate(StrictModel):
    user_id: str | None = Field(default=None, pattern=ID_PATTERN)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: Password
    name: str = Field(min_length=1, max_length=100)
    role: UserRole


class UserUpdate(PatchModel):
    NON_NULLABLE = frozenset({"name", "role", "password"})
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    password: Password | None = None


class GuardianLinkCreate(StrictModel):
    guardian_id: str = Field(pattern=ID_PATTERN)
    user_id: str = Field(pattern=ID_PATTERN)


# 제스처·명령 매핑 ---------------------------------------------------------


class GestureMappingUpdate(PatchModel):
    NON_NULLABLE = frozenset({"action", "enabled"})
    action: IntentAction | None = None
    enabled: bool | None = None
