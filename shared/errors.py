"""공통 인터페이스 v1 오류 형식과 예외."""

from dataclasses import dataclass
from typing import Any

ERROR_MESSAGES = {
    "INVALID_SCHEMA": "메시지 형식이 올바르지 않습니다.",
    "UNSUPPORTED_VERSION": "지원하지 않는 인터페이스 버전입니다.",
    "UNAUTHORIZED": "인증이 필요합니다.",
    "FORBIDDEN": "접근 권한이 없습니다.",
    "DEVICE_NOT_FOUND": "요청한 기기를 찾을 수 없습니다.",
    "TARGET_NOT_FOUND": "포인팅 대상 기기를 찾을 수 없습니다.",
    "COMMAND_EXPIRED": "명령 유효시간이 지났습니다.",
    "COMMAND_DUPLICATE": "이미 처리한 명령입니다.",
    "ACK_TIMEOUT": "기기 응답 시간이 초과되었습니다.",
    "INTERNAL_ERROR": "서버 내부 오류가 발생했습니다.",
}

@dataclass(slots=True)
class InterfaceError(Exception):
    code: str
    message: str | None = None
    correlation_id: str | None = None
    status_code: int = 400

    def __post_init__(self) -> None:
        if self.message is None:
            self.message = ERROR_MESSAGES.get(self.code, ERROR_MESSAGES["INTERNAL_ERROR"])

    def as_response(self) -> dict[str, Any]:
        return {"success": False, "error": {
            "code": self.code, "message": self.message, "correlation_id": self.correlation_id,
        }}
