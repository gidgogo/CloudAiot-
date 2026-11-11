"""로그인과 JWT 발급 API(규격 7.3, 8.1).

JWT는 응답 본문이 아니라 HttpOnly Cookie로만 보낸다.
CSRF 토큰은 JavaScript가 읽을 수 있는 별도 Cookie로 보내며,
웹은 상태 변경 요청에 ``X-CSRF-Token`` 헤더로 다시 보낸다.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response

from server.api.deps import (
    CurrentUser,
    SessionDep,
    SettingsDep,
    TokenClaims,
    UserServiceDep,
)
from server.api.schemas import LoginRequest, PasswordChange, ok
from server.db.models import User
from server.security.csrf import check_origin
from server.security.jwt import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    create_access_token,
    new_csrf_token,
)
from server.security.permissions import GUARDIAN
from server.services.errors import web_error
from server.services.user_service import UserService, user_to_dict
from server.settings import Settings
from shared.constants import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/auth", tags=["auth"])


def session_body(service: UserService, user: User, expires_at: int) -> dict:
    linked = (
        sorted(service.guardian_user_ids(user.user_id)) if user.role == GUARDIAN else []
    )
    return {
        "user": user_to_dict(user),
        "linked_user_ids": linked,
        "expires_at_ms": expires_at * 1000,
    }


def _set_cookies(response: Response, token: str, csrf: str, settings: Settings) -> None:
    common = {
        "max_age": settings.jwt_expire_seconds,
        "path": "/",
        "secure": settings.cookie_secure,
        "samesite": "strict",
    }
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)


def _clear_cookies(response: Response, settings: Settings) -> None:
    for name, httponly in ((ACCESS_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.cookie_secure,
            httponly=httponly,
            samesite="strict",
        )


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> dict:
    check_origin(request.headers, request.url.scheme, settings.allowed_origins)
    limiter = request.app.state.login_limiter
    key = (
        f"{body.email.strip().lower()}|{request.client.host if request.client else '-'}"
    )
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
    token = create_access_token(
        user.user_id, settings.jwt_secret, settings.jwt_expire_seconds, csrf, now=issued
    )
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
def change_password(
    body: PasswordChange, user: CurrentUser, service: UserServiceDep
) -> dict:
    service.change_password(user.user_id, body.current_password, body.new_password)
    return ok(None)
