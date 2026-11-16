"""웹 응용 서비스 로직 패키지."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from shared.errors import ERROR_MESSAGES, InterfaceError

# --- 웹·응용 서버 전용 오류 코드.

WEB_ERRORS: dict[str, tuple[int, str]] = {
    "INVALID_SCHEMA": (422, ERROR_MESSAGES["INVALID_SCHEMA"]),
    "UNAUTHORIZED": (401, ERROR_MESSAGES["UNAUTHORIZED"]),
    "FORBIDDEN": (403, ERROR_MESSAGES["FORBIDDEN"]),
    "DEVICE_NOT_FOUND": (404, ERROR_MESSAGES["DEVICE_NOT_FOUND"]),
    "INTERNAL_ERROR": (500, ERROR_MESSAGES["INTERNAL_ERROR"]),
    "NOT_FOUND": (404, "요청한 경로를 찾을 수 없습니다."),
    "METHOD_NOT_ALLOWED": (405, "허용되지 않는 요청 방식입니다."),
    "ROOM_NOT_FOUND": (404, "요청한 방을 찾을 수 없습니다."),
    "ROOM_ALREADY_EXISTS": (409, "이미 등록된 방 ID입니다."),
    "ROOM_NOT_EMPTY": (409, "기기가 등록된 방은 삭제할 수 없습니다."),
    "DEVICE_ALREADY_EXISTS": (409, "이미 등록된 기기 ID입니다."),
    "USER_NOT_FOUND": (404, "사용자를 찾을 수 없습니다."),
    "USER_ALREADY_EXISTS": (409, "이미 등록된 사용자입니다."),
    "HELP_REQUEST_NOT_FOUND": (404, "도움 요청을 찾을 수 없습니다."),
    "INVALID_STATUS_TRANSITION": (409, "허용되지 않는 상태 변경입니다."),
    "COMMAND_NOT_FOUND": (404, "제어 명령을 찾을 수 없습니다."),
    "COMMAND_ALREADY_EXISTS": (409, "이미 기록된 제어 명령입니다."),
    "INVALID_CREDENTIALS": (401, "이메일 또는 비밀번호가 올바르지 않습니다."),
    "TOO_MANY_ATTEMPTS": (429, "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요."),
    "MAPPING_NOT_FOUND": (404, "제스처 매핑을 찾을 수 없습니다."),
    "MAPPING_CONFLICT": (409, "같은 명령이 여러 제스처에 연결되어 있습니다."),
    "INVALID_USER_ROLE": (409, "해당 역할의 사용자만 지정할 수 있습니다."),
    "CANNOT_MODIFY_SELF": (409, "자신의 계정 역할을 바꾸거나 삭제할 수 없습니다."),
    "HELP_USER_UNKNOWN": (409, "도움 요청을 기록할 사용자를 정할 수 없습니다."),
}


def web_error(code: str, message: str | None = None, correlation_id: str | None = None) -> InterfaceError:
    status_code, default_message = WEB_ERRORS.get(code, WEB_ERRORS["INTERNAL_ERROR"])
    return InterfaceError(code=code, message=message or default_message,
                          correlation_id=correlation_id, status_code=status_code)


def reject_unknown_fields(changes: Mapping[str, Any], allowed: Collection[str]) -> None:
    """서비스를 직접 호출하는 코드(다른 모듈·스크립트)가 바꿀 수 없는 필드를 넘기면 거부한다."""
    unknown = set(changes) - set(allowed)
    if unknown:
        raise web_error("INVALID_SCHEMA", f"수정할 수 없는 필드입니다: {', '.join(sorted(unknown))}")
