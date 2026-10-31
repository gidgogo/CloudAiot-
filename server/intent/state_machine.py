"""Target selection state machine for POINTING -> THUMB_UP/DOWN."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
class IntentState(StrEnum): IDLE="IDLE"; TARGET_SELECTED="TARGET_SELECTED"; CANCELLED="CANCELLED"
@dataclass
class SelectionStateMachine:
    timeout_ms: int = 3000
    state: IntentState = IntentState.IDLE
    target_device_id: str | None = None
    selected_at_ms: int = 0
    def select(self, device_id: str, timestamp_ms: int) -> None:
        self.state, self.target_device_id, self.selected_at_ms = IntentState.TARGET_SELECTED, device_id, timestamp_ms
    def active_target(self, timestamp_ms: int) -> str | None:
        if self.state is IntentState.TARGET_SELECTED and timestamp_ms-self.selected_at_ms <= self.timeout_ms: return self.target_device_id
        self.cancel(); return None
    def cancel(self) -> None:
        self.state, self.target_device_id, self.selected_at_ms = IntentState.CANCELLED, None, 0
