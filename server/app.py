"""FastAPI 애플리케이션 진입점.

실행: ``python -m uvicorn server.app:app --reload``
설정은 환경변수(``server/settings.py``)로 받는다.
테스트나 다른 설정(DB 등)을 쓰려면 ``create_app(Settings(...))``로 별도 앱을 만든다.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import (
    auth,
    control_events,
    devices,
    gesture_mappings,
    health,
    help_requests,
    rooms,
    users,
    websocket,
)
from server.api.errors import register_error_handlers
from server.bootstrap import bootstrap
from server.db.session import Database
from server.security.authentication import LoginRateLimiter
from server.security.jwt import CSRF_HEADER
from server.services.events import EventHub
from server.services.retention_service import purge_expired
from server.settings import Settings

log = logging.getLogger(__name__)


async def _retention_loop(db: Database, settings: Settings) -> None:
    def run() -> None:
        with db.session() as session:
            purge_expired(
                session,
                settings.control_event_retention_days,
                settings.help_request_retention_days,
            )

    while True:
        try:
            await asyncio.to_thread(run)
        except Exception:
            log.exception("retention purge failed")
        await asyncio.sleep(settings.retention_interval_seconds)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = (settings or Settings.from_env()).resolved()
    db = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await asyncio.to_thread(bootstrap, db, settings)
        retention = None
        if (
            settings.control_event_retention_days
            or settings.help_request_retention_days
        ):
            retention = asyncio.create_task(_retention_loop(db, settings))
        yield
        if retention is not None:
            retention.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await retention
        db.dispose()

    application = FastAPI(title="CloudAIoT API", version="1.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.db = db
    application.state.events = EventHub()
    application.state.login_limiter = LoginRateLimiter(
        settings.login_max_attempts, settings.login_lock_seconds
    )
    if settings.allowed_origins:
        # 프런트엔드와 API 주소가 다를 때만 쓰인다. Cookie 인증이라 "*"는 쓰지 않는다(규격 8.3).
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type", CSRF_HEADER],
        )
    register_error_handlers(application)
    for router in (
        health.router,
        auth.router,
        users.router,
        rooms.router,
        devices.router,
        control_events.router,
        help_requests.router,
        gesture_mappings.router,
        websocket.router,
    ):
        application.include_router(router)
    return application


app = create_app()
