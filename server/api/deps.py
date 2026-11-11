"""라우터에서 공통으로 쓰는 의존성(DB 세션, 이벤트 허브, 로그인 사용자, 서비스).

로그인 확인(``CurrentUser``)은 다음을 한 번에 검사한다.
1. HttpOnly Cookie의 JWT 서명·만료 → 실패 시 401 UNAUTHORIZED
2. 상태 변경 요청(POST·PATCH·DELETE)이면 Origin과 CSRF 토큰 → 실패 시 403 FORBIDDEN
3. 토큰의 사용자가 아직 존재하는지 → 없으면 401

I/O가 없는 의존성은 ``async def``로 두어 스레드풀을 거치지 않게 한다.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from server.db.models import User
from server.db.repositories import UserRepository
from server.security.csrf import SAFE_METHODS, check_csrf, check_origin
from server.security.jwt import (
    ExpiredSignatureError,
    InvalidTokenError,
    read_access_claims,
)
from server.security.permissions import ADMIN, Principal, require_role
from server.services.control_event_service import ControlEventService
from server.services.device_service import DeviceService
from server.services.errors import web_error
from server.services.events import EventHub
from server.services.gesture_mapping_service import GestureMappingService
from server.services.help_service import HelpService
from server.services.room_service import RoomService
from server.services.user_service import UserService
from server.settings import Settings


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
        raise web_error(
            "UNAUTHORIZED", "로그인이 만료되었습니다. 다시 로그인하세요."
        ) from error
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


async def get_control_event_service(
    session: SessionDep, events: EventsDep
) -> ControlEventService:
    return ControlEventService(session, events)


async def get_user_service(session: SessionDep, events: EventsDep) -> UserService:
    return UserService(session, events)


async def get_gesture_mapping_service(session: SessionDep) -> GestureMappingService:
    return GestureMappingService(session)


RoomServiceDep = Annotated[RoomService, Depends(get_room_service)]
DeviceServiceDep = Annotated[DeviceService, Depends(get_device_service)]
HelpServiceDep = Annotated[HelpService, Depends(get_help_service)]
ControlEventServiceDep = Annotated[
    ControlEventService, Depends(get_control_event_service)
]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
GestureMappingServiceDep = Annotated[
    GestureMappingService, Depends(get_gesture_mapping_service)
]


def get_principal(user: CurrentUser, users: UserServiceDep) -> Principal:
    return users.principal(user)


PrincipalDep = Annotated[Principal, Depends(get_principal)]
