"""Target selection state machine for POINTING -> THUMB_UP/DOWN."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from server.intent.cancel_reasons import DIRECTION_CHANGED, GESTURE_TIMEOUT
from server.intent.parameters import IntentParameters


def angle_difference_deg(a_deg: float, b_deg: float) -> float:
    """Smallest absolute difference between two angles, so 170° and -170° are 20° apart."""
    return abs((a_deg - b_deg + 180.0) % 360.0 - 180.0)


class IntentState(StrEnum):
    IDLE = "IDLE"
    TARGET_SELECTED = "TARGET_SELECTED"


@dataclass
class SelectionStateMachine:
    """IDLE -> TARGET_SELECTED -> (confirm or cancel) -> IDLE.

    A cancel keeps its spec 6.2 reason in last_cancel_reason until the next select or confirm.
    """

    timeout_ms: int = IntentParameters.selection_timeout_ms
    max_angle_delta_deg: float = IntentParameters.max_angle_delta_deg
    state: IntentState = IntentState.IDLE
    target_device_id: str | None = None
    selected_at_ms: int = 0
    selected_angle_deg: float | None = None
    last_cancel_reason: str | None = None

    def select(self, device_id: str, timestamp_ms: int, angle_deg: float | None = None) -> None:
        """Start a new selection. angle_deg is the pointing angle used to detect a direction change."""
        self.state = IntentState.TARGET_SELECTED
        self.target_device_id = device_id
        self.selected_at_ms = timestamp_ms
        self.selected_angle_deg = angle_deg
        self.last_cancel_reason = None

    def keep_alive(self, timestamp_ms: int) -> None:
        """Still pointing at the selected device: restart the timer, keep the target and reference angle."""
        if self.state is IntentState.TARGET_SELECTED and timestamp_ms > self.selected_at_ms:
            self.selected_at_ms = timestamp_ms

    def cancel_if_direction_changed(self, angle_deg: float) -> bool:
        """Cancel with DIRECTION_CHANGED when the pointing angle moved more than max_angle_delta_deg."""
        if self.state is not IntentState.TARGET_SELECTED or self.selected_angle_deg is None:
            return False
        if angle_difference_deg(angle_deg, self.selected_angle_deg) <= self.max_angle_delta_deg:
            return False
        self.cancel(DIRECTION_CHANGED)
        return True

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
        self.selected_angle_deg = None
