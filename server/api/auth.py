"""로그인과 JWT 발급 API(규격 7.3, 8.1).

JWT는 응답 본문이 아니라 HttpOnly Cookie로만 보낸다.
CSRF 토큰은 JavaScript가 읽을 수 있는 별도 Cookie로 보내며,
웹은 상태 변경 요청에 ``X-CSRF-Token`` 헤더로 다시 보낸다.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response
from pydantic import Field

from server.api import (
    EMAIL_PATTERN,
    ID_PATTERN,
    AdminUser,
    CurrentUser,
    Password,
    PatchModel,
    PrincipalDep,
    SessionDep,
    SettingsDep,
    StrictModel,
    TokenClaims,
    UserServiceDep,
    ok,
)
from server.config import Settings
from server.db.models import User
from server.security.jwt import ACCESS_COOKIE, CSRF_COOKIE, check_origin, create_access_token, new_csrf_token
from server.security.permissions import GUARDIAN
from server.services import web_error
from server.services.user_service import UserService, link_to_dict, user_to_dict
from shared.constants import API_PREFIX
from shared.types import UserRole


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(StrictModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: Password


router = APIRouter(prefix=f"{API_PREFIX}/auth", tags=["auth"])


def session_body(service: UserService, user: User, expires_at: int) -> dict:
    linked = sorted(service.guardian_user_ids(user.user_id)) if user.role == GUARDIAN else []
    return {"user": user_to_dict(user), "linked_user_ids": linked, "expires_at_ms": expires_at * 1000}


def _set_cookies(response: Response, token: str, csrf: str, settings: Settings) -> None:
    common = {"max_age": settings.jwt_expire_seconds, "path": "/", "secure": settings.cookie_secure,
              "samesite": "strict"}
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)


def _clear_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in ((ACCESS_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=httponly, samesite="strict")


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, session: SessionDep,
          settings: SettingsDep) -> dict:
    check_origin(request.headers, request.url.scheme, settings.allowed_origins)
    limiter = request.app.state.login_limiter
    key = f"{body.email.strip().lower()}|{request.client.host if request.client else '-'}"
    if limiter.is_locked(key):
        raise web_error("TOO_MANY_ATTEMPTS")
    service = UserService(session)
    user = service.authenticate(body.email, body.password)
    if user is None:
        limiter.record_failure(key)
        raise web_error("INVALID_CREDENTIALS")
    limiter.reset(key)
    csrf = new_csrf_token()
    issued = int(time.time())
    token = create_access_token(user.user_id, settings.jwt_secret, settings.jwt_expire_seconds, csrf, now=issued)
    _set_cookies(response, token, csrf, settings)
    return ok(session_body(service, user, issued + settings.jwt_expire_seconds))


@router.post("/logout")
def logout(request: Request, response: Response, settings: SettingsDep) -> dict:
    # 만료된 로그인도 Cookie는 지울 수 있어야 하므로 Origin만 검사한다.
    check_origin(request.headers, request.url.scheme, settings.allowed_origins)
    _clear_cookies(response, settings)
    return ok(None)


@router.get("/me")
def me(user: CurrentUser, claims: TokenClaims, service: UserServiceDep) -> dict:
    return ok(session_body(service, user, int(claims["exp"])))


@router.post("/password")
def change_password(body: PasswordChange, user: CurrentUser, service: UserServiceDep) -> dict:
    service.change_password(user.user_id, body.current_password, body.new_password)
    return ok(None)


# --- 사용자·보호자 연결 관리 API(ADMIN). 보호자·사용자는 자신이 볼 수 있는 범위만 조회한다.

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


users_router = APIRouter(prefix=API_PREFIX, tags=["users"])


@users_router.get("/users")
def list_users(principal: PrincipalDep, service: UserServiceDep, role: UserRole | None = None) -> dict:
    visible = principal.visible_user_ids
    users = service.list(role=role, user_ids=None if visible is None else visible | {principal.user_id})
    return ok([user_to_dict(user) for user in users])


@users_router.post("/users", status_code=201)
def create_user(body: UserCreate, _admin: AdminUser, service: UserServiceDep) -> dict:
    return ok(user_to_dict(service.create(**body.model_dump())))


@users_router.get("/users/{user_id}")
def get_user(user_id: str, principal: PrincipalDep, service: UserServiceDep) -> dict:
    if not principal.can_view_profile(user_id):
        raise web_error("FORBIDDEN")
    return ok(user_to_dict(service.get(user_id)))


@users_router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate, admin: AdminUser, service: UserServiceDep) -> dict:
    return ok(user_to_dict(service.update(user_id, body.model_dump(exclude_unset=True), actor_id=admin.user_id)))


@users_router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, admin: AdminUser, service: UserServiceDep) -> Response:
    service.delete(user_id, actor_id=admin.user_id)
    return Response(status_code=204)


@users_router.get("/guardian-links")
def list_links(_admin: AdminUser, service: UserServiceDep, guardian_id: str | None = None,
               user_id: str | None = None) -> dict:
    return ok([link_to_dict(link) for link in service.list_links(guardian_id=guardian_id, user_id=user_id)])


@users_router.post("/guardian-links", status_code=201)
def create_link(body: GuardianLinkCreate, _admin: AdminUser, service: UserServiceDep) -> dict:
    return ok(link_to_dict(service.link_guardian(body.guardian_id, body.user_id)))


@users_router.delete("/guardian-links/{guardian_id}/{user_id}", status_code=204)
def delete_link(guardian_id: str, user_id: str, _admin: AdminUser, service: UserServiceDep) -> Response:
    service.unlink_guardian(guardian_id, user_id)
    return Response(status_code=204)
