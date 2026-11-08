"""Origin 검사와 CSRF 토큰 검사(규격 8.3, 8.4)."""

from __future__ import annotations

import hmac
from collections.abc import Iterable, Mapping
from typing import Any

from server.security.jwt import CSRF_COOKIE, CSRF_HEADER, csrf_digest
from server.services.errors import web_error

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def request_origin(headers: Mapping[str, str], scheme: str) -> str | None:
    """요청이 도착한 서버 자신의 출처. Nginx 뒤에서는 X-Forwarded-* 를 따른다."""
    host = headers.get("x-forwarded-host") or headers.get("host")
    if not host:
        return None
    proto = headers.get("x-forwarded-proto") or scheme
    proto = {"ws": "http", "wss": "https"}.get(proto, proto)
    return f"{proto}://{host.split(',')[0].strip()}"


def is_allowed_origin(
    origin: str, allowed: Iterable[str], own_origin: str | None
) -> bool:
    origin = origin.rstrip("/")
    return origin == own_origin or origin in allowed


def check_origin(
    headers: Mapping[str, str],
    scheme: str,
    allowed: Iterable[str],
    *,
    required: bool = False,
) -> None:
    """Origin이 있으면 허용 목록이나 같은 출처여야 한다. required면 Origin이 꼭 있어야 한다."""
    origin = headers.get("origin")
    if origin is None:
        if required:
            raise web_error("FORBIDDEN", "Origin 헤더가 필요합니다.")
        return
    if not is_allowed_origin(origin, allowed, request_origin(headers, scheme)):
        raise web_error("FORBIDDEN", "허용되지 않은 출처의 요청입니다.")


def check_csrf(
    headers: Mapping[str, str], cookies: Mapping[str, str], claims: Mapping[str, Any]
) -> None:
    """헤더·Cookie의 CSRF 토큰이 같고, 로그인 때 JWT에 넣은 값과도 같아야 한다."""
    header_token = headers.get(CSRF_HEADER.lower()) or headers.get(CSRF_HEADER)
    cookie_token = cookies.get(CSRF_COOKIE)
    if not header_token or not cookie_token:
        raise web_error("FORBIDDEN", "CSRF 토큰이 없습니다.")
    if not hmac.compare_digest(header_token, cookie_token):
        raise web_error("FORBIDDEN", "CSRF 토큰이 올바르지 않습니다.")
    if not hmac.compare_digest(csrf_digest(header_token), str(claims.get("csrf", ""))):
        raise web_error("FORBIDDEN", "CSRF 토큰이 올바르지 않습니다.")
