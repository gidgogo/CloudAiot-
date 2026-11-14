"""데이터베이스 연결과 세션을 관리한다.

접속 주소는 ``Settings.database_url``(환경변수 ``DATABASE_URL``)에서 받는다.
예: ``postgresql+psycopg://cloudaiot:비밀번호@postgres:5432/cloudaiot``
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.config import Settings
from server.db.models import Base
from server.services.device_service import GestureMappingService
from server.services.user_service import UserService
from shared.types import UserRole


def create_db_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)
    options: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:") or "mode=memory" in url:
        # 메모리 DB는 연결마다 새로 생기므로 하나의 연결을 공유한다.
        options["poolclass"] = StaticPool
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


class Database:
    """엔진과 세션 팩토리를 묶어 애플리케이션 단위로 관리한다."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_db_engine(url)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


# --- 서버 시작 시 필요한 기본 데이터를 준비한다.

log = logging.getLogger(__name__)


def bootstrap(db: Database, settings: Settings) -> None:
    db.create_all()
    with db.session() as session:
        GestureMappingService(session).ensure_defaults()
        users = UserService(session)
        if users.count() == 0:
            if settings.admin_email and settings.admin_password:
                users.create(email=settings.admin_email, password=settings.admin_password,
                             name=settings.admin_name, role=UserRole.ADMIN)
                log.info("최초 관리자 계정을 만들었습니다: %s", settings.admin_email)
            else:
                log.warning("사용자가 없습니다. ADMIN_EMAIL·ADMIN_PASSWORD를 설정하거나 "
                            "python -m scripts.seed_demo_data 로 계정을 만드세요.")
