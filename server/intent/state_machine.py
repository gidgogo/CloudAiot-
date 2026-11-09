"""Target selection state machine for POINTING -> THUMB_UP/DOWN."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from server.intent.cancel_reasons import GESTURE_TIMEOUT
from server.intent.parameters import IntentParameters


class IntentState(StrEnum):
    IDLE = "IDLE"
    TARGET_SELECTED = "TARGET_SELECTED"


@dataclass
class SelectionStateMachine:
    """IDLE -> TARGET_SELECTED -> (confirm or cancel) -> IDLE.

    A cancel keeps its spec 6.2 reason in last_cancel_reason until the next select or confirm.
    """

    timeout_ms: int = IntentParameters.selection_timeout_ms
    state: IntentState = IntentState.IDLE
    target_device_id: str | None = None
    selected_at_ms: int = 0
    last_cancel_reason: str | None = None

    def select(self, device_id: str, timestamp_ms: int) -> None:
        self.state = IntentState.TARGET_SELECTED
        self.target_device_id = device_id
        self.selected_at_ms = timestamp_ms
        self.last_cancel_reason = None

    def active_target(self, timestamp_ms: int) -> str | None:
        """Return the selected device while the selection is still valid at timestamp_ms."""
        if self.state is not IntentState.TARGET_SELECTED:
            return None
        elapsed_ms = timestamp_ms - self.selected_at_ms
        if elapsed_ms < 0:
            # A frame detected before the selection cannot confirm it; ignore it and keep the selection.
            return None
        if elapsed_ms > self.timeout_ms:
            self.cancel(GESTURE_TIMEOUT)
            return None
        return self.target_device_id

    def confirm(self) -> None:
        """Call after the intent is confirmed so the same selection cannot confirm twice."""
        self._reset()
        self.last_cancel_reason = None

    def cancel(self, reason: str) -> None:
        self._reset()
        self.last_cancel_reason = reason

    def _reset(self) -> None:
        self.state = IntentState.IDLE
        self.target_device_id = None
        self.selected_at_ms = 0
