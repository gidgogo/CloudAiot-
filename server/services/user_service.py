"""사용자·보호자 계정과 연결 관계를 관리한다.

계정·연결이 바뀌면 열려 있는 실시간 연결(EventHub)에도 바로 반영한다.
- 역할 변경·계정 삭제: 그 사용자의 연결을 닫는다(다시 로그인).
- 보호자 연결 변경: 영향받는 보호자의 열람 범위를 갱신한다.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from server.db.models import GuardianLink, User
from server.db.repositories import UserRepository
from server.security.authentication import burn_verification_time, hash_password, verify_password
from server.security.permissions import Principal, visible_user_ids
from server.services import reject_unknown_fields, web_error
from shared.types import UserRole, new_id, now_ms

if TYPE_CHECKING:
    from server.api.websocket import EventHub  # 실행 시 순환 import를 피한다.

UPDATABLE_FIELDS = frozenset({"name", "role", "password"})


def user_to_dict(user: User) -> dict[str, Any]:
    # password_hash는 절대 응답에 포함하지 않는다.
    return {"user_id": user.user_id, "email": user.email, "name": user.name,
            "role": user.role, "created_at_ms": user.created_at_ms}


def link_to_dict(link: GuardianLink) -> dict[str, Any]:
    return {"guardian_id": link.guardian_id, "user_id": link.user_id, "created_at_ms": link.created_at_ms}


def _hash(password: str) -> str:
    try:
        return hash_password(password)
    except ValueError as error:
        raise web_error("INVALID_SCHEMA", str(error)) from error


class UserService:
    def __init__(self, session: Session, events: EventHub | None = None) -> None:
        self.session = session
        self.events = events
        self.users = UserRepository(session)

    # 조회 ----------------------------------------------------------------

    def get(self, user_id: str, correlation_id: str | None = None) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise web_error("USER_NOT_FOUND", correlation_id=correlation_id)
        return user

    def require_role(self, user_id: str, role: UserRole, message: str, correlation_id: str | None = None) -> User:
        user = self.get(user_id, correlation_id)
        if user.role != role.value:
            raise web_error("INVALID_USER_ROLE", message, correlation_id=correlation_id)
        return user

    def list(self, role: UserRole | str | None = None, user_ids: Collection[str] | None = None) -> list[User]:
        return self.users.list(role=UserRole(role).value if role else None, user_ids=user_ids)

    def count(self) -> int:
        return self.users.count()

    def guardian_user_ids(self, guardian_id: str) -> list[str]:
        return self.users.guardian_user_ids(guardian_id)

    def principal(self, user: User) -> Principal:
        linked = self.guardian_user_ids(user.user_id) if user.role == UserRole.GUARDIAN.value else []
        return Principal(user.user_id, user.role, visible_user_ids(user.user_id, user.role, linked))

    def principal_for(self, user_id: str) -> Principal | None:
        user = self.users.get(user_id)
        return None if user is None else self.principal(user)

    # 인증 ----------------------------------------------------------------

    def authenticate(self, email: str, password: str) -> User | None:
        user = self.users.get_by_email(email.strip())
        if user is None:
            burn_verification_time(password)
            return None
        return user if verify_password(password, user.password_hash) else None

    # 변경 ----------------------------------------------------------------

    def create(self, *, email: str, password: str, name: str, role: UserRole | str,
               user_id: str | None = None) -> User:
        role = UserRole(role).value
        email = email.strip().lower()
        if self.users.get_by_email(email) is not None or (user_id and self.users.get(user_id)):
            raise web_error("USER_ALREADY_EXISTS")
        user = self.users.add(User(user_id=user_id or new_id(), email=email, password_hash=_hash(password),
                                   name=name, role=role, created_at_ms=now_ms()))
        self.session.commit()
        return user

    def update(self, user_id: str, changes: dict[str, Any], actor_id: str | None = None) -> User:
        user = self.get(user_id)
        reject_unknown_fields(changes, UPDATABLE_FIELDS)
        new_role = UserRole(changes["role"]).value if "role" in changes else user.role
        role_changed = new_role != user.role
        if role_changed and actor_id == user_id:
            raise web_error("CANNOT_MODIFY_SELF")
        affected_guardians: list[str] = []
        if role_changed:
            # 역할이 바뀌면 이전 역할 기준의 보호자 연결은 의미가 없어진다.
            links = self.users.list_links(guardian_id=user_id) + self.users.list_links(user_id=user_id)
            affected_guardians = [link.guardian_id for link in links if link.guardian_id != user_id]
            for link in links:
                self.session.delete(link)
            user.role = new_role
        if "name" in changes:
            user.name = changes["name"]
        if "password" in changes:
            user.password_hash = _hash(changes["password"])
        self.session.commit()
        if role_changed:
            self._close(user_id)
            self._refresh(affected_guardians)
        return user

    def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        user = self.get(user_id)
        if not verify_password(current_password, user.password_hash):
            raise web_error("INVALID_CREDENTIALS", "현재 비밀번호가 올바르지 않습니다.")
        user.password_hash = _hash(new_password)
        self.session.commit()

    def delete(self, user_id: str, actor_id: str | None = None) -> None:
        if actor_id == user_id:
            raise web_error("CANNOT_MODIFY_SELF")
        user = self.get(user_id)
        affected_guardians = [link.guardian_id for link in self.users.list_links(user_id=user_id)]
        self.users.delete(user)
        self.session.commit()
        self._close(user_id)
        self._refresh(affected_guardians)

    # 보호자 연결 -----------------------------------------------------------

    def list_links(self, guardian_id: str | None = None, user_id: str | None = None) -> list[GuardianLink]:
        return self.users.list_links(guardian_id=guardian_id, user_id=user_id)

    def link_guardian(self, guardian_id: str, user_id: str) -> GuardianLink:
        message = "보호자(GUARDIAN)와 사용자(USER)만 연결할 수 있습니다."
        self.require_role(guardian_id, UserRole.GUARDIAN, message)
        self.require_role(user_id, UserRole.USER, message)
        link = self.users.get_link(guardian_id, user_id)
        if link is None:
            link = self.users.add(GuardianLink(guardian_id=guardian_id, user_id=user_id, created_at_ms=now_ms()))
            self.session.commit()
            self._refresh([guardian_id])
        return link

    def unlink_guardian(self, guardian_id: str, user_id: str) -> None:
        link = self.users.get_link(guardian_id, user_id)
        if link is not None:
            self.users.delete(link)
            self.session.commit()
            self._refresh([guardian_id])

    # 실시간 연결 반영 -------------------------------------------------------

    def _close(self, user_id: str) -> None:
        if self.events is not None:
            self.events.close_user(user_id)

    def _refresh(self, guardian_ids: Iterable[str]) -> None:
        if self.events is None:
            return
        for guardian_id in set(guardian_ids):
            principal = self.principal_for(guardian_id)
            if principal is not None:
                self.events.update_principal(guardian_id, principal)
