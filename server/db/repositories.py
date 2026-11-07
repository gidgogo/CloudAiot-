"""데이터베이스 조회와 저장 작업을 담당한다.

리포지토리는 SQL 접근만 맡고, 검증·상태 전이·이벤트 발행은 services 계층에서 처리한다.
커밋은 서비스가 한 작업 단위가 끝났을 때 수행한다.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.orm import Session

from server.db.models import (
    Base,
    CommandStatus,
    ControlEvent,
    Device,
    GestureMapping,
    GuardianLink,
    HelpRequestRecord,
    Room,
    User,
)
from shared.types import HelpStatus

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: Any) -> ModelT | None:
        return self.session.get(self.model, key)

    def add(self, item: ModelT) -> ModelT:
        self.session.add(item)
        self.session.flush()
        return item

    def delete(self, item: ModelT) -> None:
        self.session.delete(item)
        self.session.flush()

    def _all(
        self, conditions: list[ColumnElement[bool]], *order_by: Any
    ) -> list[ModelT]:
        return list(
            self.session.scalars(
                select(self.model).where(*conditions).order_by(*order_by)
            )
        )

    def _page(
        self,
        conditions: list[ColumnElement[bool]],
        order_by: Any,
        limit: int,
        offset: int,
    ) -> tuple[list[ModelT], int]:
        """같은 조건으로 한 페이지와 전체 개수를 함께 구한다."""
        rows = self.session.scalars(
            select(self.model)
            .where(*conditions)
            .order_by(order_by)
            .limit(limit)
            .offset(offset)
        )
        total = (
            self.session.scalar(
                select(func.count()).select_from(self.model).where(*conditions)
            )
            or 0
        )
        return list(rows), total


class UserRepository(Repository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(
            select(User).where(func.lower(User.email) == email.lower())
        )

    def list(
        self, role: str | None = None, user_ids: Collection[str] | None = None
    ) -> list[User]:
        conditions = []
        if role:
            conditions.append(User.role == role)
        if user_ids is not None:
            conditions.append(User.user_id.in_(user_ids))
        return self._all(conditions, User.created_at_ms)

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(User)) or 0

    def guardian_user_ids(self, guardian_id: str) -> list[str]:
        return list(
            self.session.scalars(
                select(GuardianLink.user_id).where(
                    GuardianLink.guardian_id == guardian_id
                )
            )
        )

    def get_link(self, guardian_id: str, user_id: str) -> GuardianLink | None:
        return self.session.get(GuardianLink, (guardian_id, user_id))

    def list_links(
        self, guardian_id: str | None = None, user_id: str | None = None
    ) -> list[GuardianLink]:
        query = select(GuardianLink).order_by(GuardianLink.created_at_ms)
        if guardian_id is not None:
            query = query.where(GuardianLink.guardian_id == guardian_id)
        if user_id is not None:
            query = query.where(GuardianLink.user_id == user_id)
        return list(self.session.scalars(query))


class RoomRepository(Repository[Room]):
    model = Room

    def list(self) -> list[Room]:
        return self._all([], Room.created_at_ms, Room.room_id)

    def with_resident(self) -> list[Room]:
        return self._all([Room.resident_user_id.is_not(None)])

    def device_count(self, room_id: str) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Device)
                .where(Device.room_id == room_id)
            )
            or 0
        )


class DeviceRepository(Repository[Device]):
    model = Device

    def list(
        self, room_id: str | None = None, enabled: bool | None = None
    ) -> list[Device]:
        conditions = []
        if room_id is not None:
            conditions.append(Device.room_id == room_id)
        if enabled is not None:
            conditions.append(Device.enabled == enabled)
        return self._all(conditions, Device.created_at_ms, Device.device_id)


class ControlEventRepository(Repository[ControlEvent]):
    model = ControlEvent

    def list(
        self, device_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[ControlEvent], int]:
        conditions = [] if device_id is None else [ControlEvent.device_id == device_id]
        return self._page(
            conditions, ControlEvent.command_published_at_ms.desc(), limit, offset
        )

    def delete_finished_before(self, cutoff_ms: int) -> int:
        result = self.session.execute(
            delete(ControlEvent).where(
                ControlEvent.status != CommandStatus.PENDING.value,
                ControlEvent.command_published_at_ms < cutoff_ms,
            )
        )
        return result.rowcount or 0


class HelpRequestRepository(Repository[HelpRequestRecord]):
    model = HelpRequestRecord

    def list(
        self,
        status: str | None = None,
        user_ids: Collection[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[HelpRequestRecord], int]:
        conditions = []
        if status is not None:
            conditions.append(HelpRequestRecord.status == status)
        if user_ids is not None:
            conditions.append(HelpRequestRecord.user_id.in_(user_ids))
        return self._page(
            conditions, HelpRequestRecord.created_at_ms.desc(), limit, offset
        )

    def delete_completed_before(self, cutoff_ms: int) -> int:
        result = self.session.execute(
            delete(HelpRequestRecord).where(
                HelpRequestRecord.status == HelpStatus.COMPLETED.value,
                HelpRequestRecord.created_at_ms < cutoff_ms,
            )
        )
        return result.rowcount or 0


class GestureMappingRepository(Repository[GestureMapping]):
    model = GestureMapping

    def list(self) -> list[GestureMapping]:
        return self._all([], GestureMapping.gesture)
