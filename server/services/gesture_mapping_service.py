"""제스처와 명령의 연결 관계를 관리한다(SAD 4.1 제스처·명령 매핑 모듈).

POINTING은 대상 기기 선택용이므로 매핑 대상이 아니다.
의도 판단 모듈은 ``action_for(gesture)``로 현재 설정된 명령을 얻는다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from server.db.models import GestureMapping
from server.db.repositories import GestureMappingRepository
from server.services.errors import web_error
from shared.types import GestureType, IntentAction, now_ms

MAPPABLE_GESTURES = (
    GestureType.THUMB_UP.value,
    GestureType.THUMB_DOWN.value,
    GestureType.HELP.value,
)
DEFAULT_MAPPINGS = {
    GestureType.THUMB_UP.value: IntentAction.ON.value,
    GestureType.THUMB_DOWN.value: IntentAction.OFF.value,
    GestureType.HELP.value: IntentAction.HELP.value,
}


def mapping_to_dict(mapping: GestureMapping) -> dict[str, Any]:
    return {
        "gesture": mapping.gesture,
        "action": mapping.action,
        "enabled": mapping.enabled,
        "updated_at_ms": mapping.updated_at_ms,
    }


class GestureMappingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.mappings = GestureMappingRepository(session)

    def ensure_defaults(self) -> None:
        timestamp = now_ms()
        for gesture, action in DEFAULT_MAPPINGS.items():
            if self.mappings.get(gesture) is None:
                self.session.add(
                    GestureMapping(
                        gesture=gesture,
                        action=action,
                        enabled=True,
                        updated_at_ms=timestamp,
                    )
                )
        self.session.commit()

    def list(self) -> list[GestureMapping]:
        return self.mappings.list()

    def get(self, gesture: str) -> GestureMapping:
        mapping = self.mappings.get(gesture)
        if mapping is None:
            raise web_error("MAPPING_NOT_FOUND")
        return mapping

    def update(self, gesture: str, changes: dict[str, Any]) -> GestureMapping:
        mapping = self.get(gesture)
        if "action" in changes:
            mapping.action = IntentAction(changes["action"]).value
        if "enabled" in changes:
            mapping.enabled = bool(changes["enabled"])
        active = [m.action for m in self.mappings.list() if m.enabled]
        if len(active) != len(set(active)):
            self.session.rollback()
            raise web_error("MAPPING_CONFLICT")
        mapping.updated_at_ms = now_ms()
        self.session.commit()
        return mapping

    def action_for(self, gesture: GestureType | str) -> IntentAction | None:
        """제스처에 연결된 명령. 매핑이 없거나 꺼져 있으면 None."""
        mapping = self.mappings.get(GestureType(gesture).value)
        if mapping is None or not mapping.enabled:
            return None
        return IntentAction(mapping.action)
