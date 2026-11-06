"""웹·응용 서버 환경설정. 비밀값은 환경변수(.env)로만 받는다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| DATABASE_URL | sqlite:///./cloudaiot-dev.db | PostgreSQL: postgresql+psycopg://user:pw@host:5432/db |
| JWT_SECRET | (없으면 실행마다 임의 생성) | 32자 이상 권장 |
| JWT_EXPIRE_SECONDS | 1800 | 로그인 유지 시간(규격 8.1 Max-Age) |
| COOKIE_SECURE | false | 운영(HTTPS)에서는 true |
| ALLOWED_ORIGINS | localhost:5173, localhost:8080 | 쉼표로 구분. 같은 출처는 항상 허용 |
| ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_NAME | 없음 | 사용자가 한 명도 없을 때 최초 관리자 생성 |
| CONTROL_EVENT_RETENTION_DAYS | 없음(보관) | 제어 이력 보존 기간 |
| HELP_REQUEST_RETENTION_DAYS | 없음(보관) | 완료된 도움 요청 보존 기간 |
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field, replace

log = logging.getLogger(__name__)

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
)
PLACEHOLDER_SECRETS = frozenset({"", "change-me", "changeme", "secret"})
DEFAULT_DATABASE_URL = "sqlite:///./cloudaiot-dev.db"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(value: str | None, default: int | None) -> int | None:
    if value is None or value.strip() == "":
        return default
    number = int(value)
    return number if number > 0 else None


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    jwt_secret: str = ""
    jwt_expire_seconds: int = 1800
    cookie_secure: bool = False
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    admin_email: str | None = None
    admin_password: str | None = field(default=None, repr=False)
    admin_name: str = "관리자"
    control_event_retention_days: int | None = None
    help_request_retention_days: int | None = None
    retention_interval_seconds: int = 3600
    login_max_attempts: int = 5
    login_lock_seconds: int = 300

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        origins = env.get("ALLOWED_ORIGINS")
        return cls(
            database_url=env.get("DATABASE_URL") or DEFAULT_DATABASE_URL,
            jwt_secret=env.get("JWT_SECRET", ""),
            jwt_expire_seconds=_int(env.get("JWT_EXPIRE_SECONDS"), 1800) or 1800,
            cookie_secure=_bool(env.get("COOKIE_SECURE")),
            allowed_origins=tuple(
                o.strip().rstrip("/") for o in origins.split(",") if o.strip()
            )
            if origins is not None
            else DEFAULT_ALLOWED_ORIGINS,
            admin_email=env.get("ADMIN_EMAIL") or None,
            admin_password=env.get("ADMIN_PASSWORD") or None,
            admin_name=env.get("ADMIN_NAME") or "관리자",
            control_event_retention_days=_int(
                env.get("CONTROL_EVENT_RETENTION_DAYS"), None
            ),
            help_request_retention_days=_int(
                env.get("HELP_REQUEST_RETENTION_DAYS"), None
            ),
        )

    def resolved(self) -> Settings:
        """빈 JWT 비밀키는 임의 값으로 바꾼다. 재시작하면 모든 로그인이 풀린다."""
        if self.jwt_secret.strip().lower() not in PLACEHOLDER_SECRETS:
            return self
        log.warning(
            "JWT_SECRET이 설정되지 않아 임의 키를 사용합니다. 서버를 재시작하면 다시 로그인해야 합니다."
        )
        return replace(self, jwt_secret=secrets.token_urlsafe(48))
