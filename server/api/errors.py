"""모든 오류를 공통 규격(7.6, 12.1) 형식으로 바꾼다."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.services.errors import web_error
from shared.errors import InterfaceError

log = logging.getLogger(__name__)

HTTP_STATUS_CODES = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


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
    async def _interface_error(
        _request: Request, error: InterfaceError
    ) -> JSONResponse:
        return _response(error)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return _response(web_error("INVALID_SCHEMA", _validation_message(error)))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(
        _request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        code = HTTP_STATUS_CODES.get(error.status_code, "INTERNAL_ERROR")
        return _response(web_error(code))

    @app.exception_handler(Exception)
    async def _unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=error)
        return _response(web_error("INTERNAL_ERROR"))
