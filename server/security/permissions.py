"""USER, GUARDIAN, ADMIN 역할별 접근 권한을 검사한다(SAD 6.1).

| 역할 | 허용 범위 |
| --- | --- |
| USER | 본인 도움 요청 생성·조회, 기기·상태·이력 조회 |
| GUARDIAN | 연결된 사용자의 도움 요청 조회·확인·완료, 기기·상태·이력 조회 |
| ADMIN | 전체. 사용자·보호자 연결, 방·기기·방향 영역, 제스처·명령 매핑 관리 |
"""

from __future__ import annotations

from dataclasses import dataclass

from server.services import web_error
from shared.types import UserRole

USER, GUARDIAN, ADMIN = UserRole.USER.value, UserRole.GUARDIAN.value, UserRole.ADMIN.value


@dataclass(frozen=True)
class Principal:
    """권한 판단에 필요한 로그인 사용자 정보."""

    user_id: str
    role: str
    # None이면 모든 사용자의 도움 요청을 볼 수 있다(ADMIN).
    visible_user_ids: frozenset[str] | None

    def can_view_user(self, user_id: str) -> bool:
        """그 사용자의 도움 요청을 볼 수 있는가."""
        return self.visible_user_ids is None or user_id in self.visible_user_ids

    def can_view_profile(self, user_id: str) -> bool:
        """그 사용자의 계정 정보를 볼 수 있는가(본인 포함)."""
        return user_id == self.user_id or self.can_view_user(user_id)

    def can_change_help_status(self, request_user_id: str) -> bool:
        return self.role == ADMIN or (self.role == GUARDIAN and self.can_view_user(request_user_id))


def visible_user_ids(user_id: str, role: str, linked_user_ids: list[str]) -> frozenset[str] | None:
    if role == ADMIN:
        return None
    if role == GUARDIAN:
        return frozenset(linked_user_ids)
    return frozenset({user_id})


def require_role(role: str, *allowed: str) -> None:
    if role not in allowed:
        raise web_error("FORBIDDEN")


def help_request_owner(principal: Principal, requested_user_id: str | None) -> str:
    """웹 도움 요청을 누구의 요청으로 만들지 정한다. USER는 본인, ADMIN은 지정한 사용자."""
    if principal.role == USER:
        if requested_user_id not in (None, principal.user_id):
            raise web_error("FORBIDDEN", "본인의 도움 요청만 만들 수 있습니다.")
        return principal.user_id
    if principal.role == ADMIN:
        if requested_user_id is None:
            raise web_error("INVALID_SCHEMA", "user_id: 관리자는 요청할 사용자를 지정해야 합니다.")
        return requested_user_id
    raise web_error("FORBIDDEN")
