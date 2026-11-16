"""REST API·WebSocket 패키지. 라우터가 함께 쓰는 요청 본문 기본 모델, 응답 형식, 의존성(DB 세션·로그인 사용자·서비스)을 둔다."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any, ClassVar

from fastapi import Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from server.api.websocket import EventHub
from server.config import Settings
from server.db.models import User
from server.db.repositories import UserRepository
from server.security.authentication import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH
from server.security.jwt import (
    SAFE_METHODS,
    ExpiredSignatureError,
    InvalidTokenError,
    check_csrf,
    check_origin,
    read_access_claims,
)
from server.security.permissions import ADMIN, Principal, require_role
from server.services import web_error
from server.services.control_event_service import ControlEventService
from server.services.device_service import DeviceService, GestureMappingService
from server.services.help_service import HelpService
from server.services.room_service import RoomService
from server.services.user_service import UserService

# --- REST 공통: 요청 본문 기본 모델과 응답 형식.

ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
DEVICE_TYPE_PATTERN = r"^[A-Z][A-Z0-9_]{0,31}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+$"
# 바이트 길이(72)는 서비스의 validate_password가 다시 검사한다.
Password = Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_BYTES)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PatchModel(StrictModel):
    """PATCH 본문. 보낸 필드만 반영하며, NON_NULLABLE 필드에는 null을 허용하지 않는다."""

    NON_NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls(self):
        nulls = [name for name in self.model_fields_set if name in self.NON_NULLABLE and getattr(self, name) is None]
        if nulls:
            raise ValueError(f"null로 바꿀 수 없는 필드입니다: {', '.join(sorted(nulls))}")
        if not self.model_fields_set:
            raise ValueError("수정할 필드가 없습니다.")
        return self


def ok(data: Any, **meta: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"success": True, "data": data}
    if meta:
        body["meta"] = meta
    return body


# --- 라우터에서 공통으로 쓰는 의존성(DB 세션, 이벤트 허브, 로그인 사용자, 서비스).

def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.db.session() as session:
        yield session


async def get_events(request: Request) -> EventHub:
    return request.app.state.events


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SessionDep = Annotated[Session, Depends(get_session)]
EventsDep = Annotated[EventHub, Depends(get_events)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

# 페이지 단위 목록의 공통 쿼리 파라미터
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


# 로그인 사용자 -----------------------------------------------------------

async def get_token_claims(request: Request, settings: SettingsDep) -> dict:
    try:
        claims = read_access_claims(request.cookies, settings.jwt_secret)
    except ExpiredSignatureError as error:
        raise web_error("UNAUTHORIZED", "로그인이 만료되었습니다. 다시 로그인하세요.") from error
    except InvalidTokenError as error:
        raise web_error("UNAUTHORIZED") from error
    if request.method not in SAFE_METHODS:
        check_origin(request.headers, request.url.scheme, settings.allowed_origins)
        check_csrf(request.headers, request.cookies, claims)
    return claims


TokenClaims = Annotated[dict, Depends(get_token_claims)]


def get_current_user(claims: TokenClaims, session: SessionDep) -> User:
    user = UserRepository(session).get(str(claims["sub"]))
    if user is None:
        raise web_error("UNAUTHORIZED")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_admin(user: CurrentUser) -> User:
    require_role(user.role, ADMIN)
    return user


AdminUser = Annotated[User, Depends(get_admin)]


# 서비스 -----------------------------------------------------------------

async def get_room_service(session: SessionDep) -> RoomService:
    return RoomService(session)


async def get_device_service(session: SessionDep, events: EventsDep) -> DeviceService:
    return DeviceService(session, events)


async def get_help_service(session: SessionDep, events: EventsDep) -> HelpService:
    return HelpService(session, events)


async def get_control_event_service(session: SessionDep, events: EventsDep) -> ControlEventService:
    return ControlEventService(session, events)


async def get_user_service(session: SessionDep, events: EventsDep) -> UserService:
    return UserService(session, events)


async def get_gesture_mapping_service(session: SessionDep) -> GestureMappingService:
    return GestureMappingService(session)


RoomServiceDep = Annotated[RoomService, Depends(get_room_service)]
DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]
HelpServiceDep = Annotated[HelpService, Depends(get_help_service)]
ControlEventServiceDep = Annotated[ControlEventService, Depends(get_control_event_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
GestureMappingServiceDep = Annotated[GestureMappingService, Depends(get_gesture_mapping_service)]


def get_principal(user: CurrentUser, users: UserServiceDep) -> Principal:
    return users.principal(user)


PrincipalDep = Annotated[Principal, Depends(get_principal)]
