"""FastAPI 애플리케이션 진입점.

실행: ``python -m uvicorn server.app:app --reload``
설정은 환경변수(``server/config.py``)로 받는다.
테스트나 다른 설정(DB 등)을 쓰려면 ``create_app(Settings(...))``로 별도 앱을 만든다.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.api import auth, control_events, devices, health, help_requests, rooms, websocket
from server.api.websocket import EventHub
from server.config import Settings
from server.db.session import Database, bootstrap
from server.security.authentication import LoginRateLimiter
from server.security.jwt import CSRF_HEADER
from server.services import web_error
from server.services.control_event_service import purge_expired
from shared.errors import InterfaceError

log = logging.getLogger(__name__)


async def _retention_loop(db: Database, settings: Settings) -> None:
    def run() -> None:
        with db.session() as session:
            purge_expired(session, settings.control_event_retention_days, settings.help_request_retention_days)

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
        if settings.control_event_retention_days or settings.help_request_retention_days:
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
    application.state.login_limiter = LoginRateLimiter(settings.login_max_attempts, settings.login_lock_seconds)
    if settings.allowed_origins:
        # 프런트엔드와 API 주소가 다를 때만 쓰인다. Cookie 인증이라 "*"는 쓰지 않는다(규격 8.3).
        application.add_middleware(
            CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", CSRF_HEADER])
    register_error_handlers(application)
    for router in (health.router, auth.router, auth.users_router, rooms.router, devices.router,
                   devices.mappings_router, control_events.router, help_requests.router, websocket.router):
        application.include_router(router)
    return application




# --- 모든 오류를 공통 규격(7.6, 12.1) 형식으로 바꾼다.

HTTP_STATUS_CODES = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


def _response(error: InterfaceError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error.as_response())


def _validation_message(error: RequestValidationError) -> str:
    details = error.errors()
    if not details:
        return web_error("INVALID_SCHEMA").message or ""
    first = details[0]
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = str(first.get("msg", "")).removeprefix("Value error, ")
    return f"{location}: {message}" if location else message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InterfaceError)
    async def _interface_error(_request: Request, error: InterfaceError) -> JSONResponse:
        return _response(error)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        return _response(web_error("INVALID_SCHEMA", _validation_message(error)))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
        code = HTTP_STATUS_CODES.get(error.status_code, "INTERNAL_ERROR")
        return _response(web_error(code))

    @app.exception_handler(Exception)
    async def _unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=error)
        return _response(web_error("INTERNAL_ERROR"))


app = create_app()
