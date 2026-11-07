"""데이터베이스 연결과 세션을 관리한다.

접속 주소는 ``Settings.database_url``(환경변수 ``DATABASE_URL``)에서 받는다.
예: ``postgresql+psycopg://cloudaiot:비밀번호@postgres:5432/cloudaiot``
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.db.models import Base


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
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
