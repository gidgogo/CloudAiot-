"""JWT 생성, 검증, 만료 처리를 담당한다.

- 알고리즘: HS256, 비밀키는 ``JWT_SECRET``
- JWT는 HttpOnly Cookie(``aiot_access_token``)로만 전달한다(규격 8.1).
- CSRF 토큰(``aiot_csrf_token``)의 SHA-256 값을 ``csrf`` 클레임에 넣어
  다른 세션의 CSRF 토큰으로 바꿔치기할 수 없게 한다.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections.abc import Mapping
from typing import Any

import jwt

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


def create_access_token(
    user_id: str,
    secret: str,
    expire_seconds: int,
    csrf_token: str,
    now: float | None = None,
) -> str:
    issued = int(now if now is not None else time.time())
    payload = {
        "sub": user_id,
        "iat": issued,
        "exp": issued + expire_seconds,
        "csrf": csrf_digest(csrf_token),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    """서명·만료가 잘못되면 ``InvalidTokenError``(만료는 ``ExpiredSignatureError``)를 던진다."""
    return jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp", "iat", "csrf"]},
    )


def read_access_claims(cookies: Mapping[str, str], secret: str) -> dict[str, Any]:
    """HTTP·WebSocket 공통: Cookie의 JWT를 검증한다. 없거나 잘못되면 ``InvalidTokenError``."""
    token = cookies.get(ACCESS_COOKIE)
    if not token:
        raise InvalidTokenError("missing access token")
    return decode_access_token(token, secret)
