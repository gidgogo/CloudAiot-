"""JWT 생성, 검증, 만료 처리를 담당한다.

- 알고리즘: HS256, 비밀키는 ``JWT_SECRET``
- JWT는 HttpOnly Cookie(``aiot_access_token``)로만 전달한다(규격 8.1).
- CSRF 토큰(``aiot_csrf_token``)의 SHA-256 값을 ``csrf`` 클레임에 넣어
  다른 세션의 CSRF 토큰으로 바꿔치기할 수 없게 한다.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Iterable, Mapping
from typing import Any

import jwt

from server.services import web_error

ALGORITHM = "HS256"
ACCESS_COOKIE = "aiot_access_token"
CSRF_COOKIE = "aiot_csrf_token"
CSRF_HEADER = "X-CSRF-Token"

InvalidTokenError = jwt.InvalidTokenError
ExpiredSignatureError = jwt.ExpiredSignatureError


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, secret: str, expire_seconds: int, csrf_token: str,
                        now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = {"sub": user_id, "iat": issued, "exp": issued + expire_seconds,
               "csrf": csrf_digest(csrf_token), "jti": secrets.token_hex(8)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    """서명·만료가 잘못되면 ``InvalidTokenError``(만료는 ``ExpiredSignatureError``)를 던진다."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp", "iat", "csrf"]})


def read_access_claims(cookies: Mapping[str, str], secret: str) -> dict[str, Any]:
    """HTTP·WebSocket 공통: Cookie의 JWT를 검증한다. 없거나 잘못되면 ``InvalidTokenError``."""
    token = cookies.get(ACCESS_COOKIE)
    if not token:
        raise InvalidTokenError("missing access token")
    return decode_access_token(token, secret)


# --- Origin 검사와 CSRF 토큰 검사(규격 8.3, 8.4).

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def request_origin(headers: Mapping[str, str], scheme: str) -> str | None:
    """요청이 도착한 서버 자신의 출처. Nginx 뒤에서는 X-Forwarded-* 를 따른다."""
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host:
        return None
    proto = headers.get("x-forwarded-proto") or scheme
    proto = {"ws": "http", "wss": "https"}.get(proto, proto)
    return f"{proto}://{host.split(',')[0].strip()}"


def is_allowed_origin(origin: str, allowed: Iterable[str], own_origin: str | None) -> bool:
    origin = origin.rstrip("/")
    return origin == own_origin or origin in allowed


def check_origin(headers: Mapping[str, str], scheme: str, allowed: Iterable[str], *, required: bool = False) -> None:
    """Origin이 있으면 허용 목록이나 같은 출처여야 한다. required면 Origin이 꼭 있어야 한다."""
    origin = headers.get("origin")
    if origin is None:
        if required:
            raise web_error("FORBIDDEN", "Origin 헤더가 필요합니다.")
        return
    if not is_allowed_origin(origin, allowed, request_origin(headers, scheme)):
        raise web_error("FORBIDDEN", "허용되지 않은 출처의 요청입니다.")


def check_csrf(headers: Mapping[str, str], cookies: Mapping[str, str], claims: Mapping[str, Any]) -> None:
    """헤더·Cookie의 CSRF 토큰이 같고, 로그인 때 JWT에 넣은 값과도 같아야 한다."""
    header_token = headers.get(CSRF_HEADER.lower()) or headers.get(CSRF_HEADER)
    cookie_token = cookies.get(CSRF_COOKIE)
    if not header_token or not cookie_token:
        raise web_error("FORBIDDEN", "CSRF 토큰이 없습니다.")
    if not hmac.compare_digest(header_token, cookie_token):
        raise web_error("FORBIDDEN", "CSRF 토큰이 올바르지 않습니다.")
    if not hmac.compare_digest(csrf_digest(header_token), str(claims.get("csrf", ""))):
        raise web_error("FORBIDDEN", "CSRF 토큰이 올바르지 않습니다.")
