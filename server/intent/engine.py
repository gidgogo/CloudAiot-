"""Convert stable gesture observations to confirmed/cancelled v1 intent messages.

consume() returns an IntentResult only when something meaningful happens
(a device is selected, an intent is confirmed or cancelled) and None otherwise.
"""
from __future__ import annotations

from server.intent.cancel_reasons import GESTURE_TIMEOUT, TARGET_NOT_FOUND
from server.intent.parameters import IntentParameters
from server.intent.state_machine import IntentState, SelectionStateMachine
from shared.types import GestureResult, GestureType, IntentAction, IntentResult, IntentStatus, now_ms

COMMAND_ACTIONS = {GestureType.THUMB_UP: IntentAction.ON, GestureType.THUMB_DOWN: IntentAction.OFF}


class IntentEngine:
    def __init__(
        self,
        state_machine: SelectionStateMachine | None = None,
        parameters: IntentParameters | None = None,
    ) -> None:
        self.parameters = parameters or IntentParameters()
        self.state = state_machine or SelectionStateMachine(timeout_ms=self.parameters.selection_timeout_ms)
        # The gesture already acted on in the current run of identical gestures.
        # It is cleared as soon as a different gesture arrives.
        self._acted_gesture: GestureType | None = None
        self._last_help_at_ms: int | None = None

    def consume(self, result: GestureResult, target_device_id: str | None = None) -> IntentResult | None:
        at_ms = result.detected_at_ms
        if self._is_stale(at_ms):
            return None
        if result.gesture is not self._acted_gesture:
            self._acted_gesture = None
        timed_out_device = self._expire_selection(at_ms)
        if timed_out_device is not None:
            return self._cancelled(result, GESTURE_TIMEOUT, target_device_id=timed_out_device)
        if not self._is_stable(result):
            return None
        if result.gesture is GestureType.HELP:
            return self._help(result)
        if result.gesture is GestureType.POINTING:
            return self._select(result, target_device_id)
        if result.gesture in COMMAND_ACTIONS:
            return self._command(result)
        return None

    def _is_stale(self, at_ms: int) -> bool:
        """A frame detected before the current selection cannot act on it."""
        return self.state.state is IntentState.TARGET_SELECTED and at_ms < self.state.selected_at_ms

    def _expire_selection(self, at_ms: int) -> str | None:
        """Return the device whose selection timed out at this frame, if any."""
        if self.state.state is not IntentState.TARGET_SELECTED:
            return None
        device_id = self.state.target_device_id
        self.state.active_target(at_ms)
        return device_id if self.state.state is IntentState.IDLE else None

    def _is_stable(self, result: GestureResult) -> bool:
        return (
            result.stable_frames >= self.parameters.min_stable_frames
            and result.hold_time_ms >= self.parameters.min_hold_ms
        )

    def _help(self, result: GestureResult) -> IntentResult | None:
        if self._acted_gesture is GestureType.HELP:
            return None
        last_at_ms = self._last_help_at_ms
        if last_at_ms is not None and result.detected_at_ms - last_at_ms < self.parameters.help_cooldown_ms:
            return None
        self._acted_gesture = GestureType.HELP
        self._last_help_at_ms = result.detected_at_ms
        return IntentResult(
            correlation_id=result.correlation_id,
            action=IntentAction.HELP,
            status=IntentStatus.CONFIRMED,
            confirmed_at_ms=now_ms(),
        )

    def _select(self, result: GestureResult, target_device_id: str | None) -> IntentResult | None:
        if not target_device_id:
            # Device matching inside the engine is not wired yet; callers pass the matched device.
            return None
        already_selected = (
            self.state.state is IntentState.TARGET_SELECTED
            and self.state.target_device_id == target_device_id
        )
        self.state.select(target_device_id, result.detected_at_ms)
        if already_selected:
            # Still pointing at the same device: keep the selection alive without a new result.
            return None
        return IntentResult(correlation_id=result.correlation_id, target_device_id=target_device_id)

    def _command(self, result: GestureResult) -> IntentResult | None:
        if self._acted_gesture is result.gesture:
            return None
        self._acted_gesture = result.gesture
        action = COMMAND_ACTIONS[result.gesture]
        target = self.state.active_target(result.detected_at_ms)
        if target is None:
            return self._cancelled(result, TARGET_NOT_FOUND, action=action)
        self.state.confirm()
        return IntentResult(
            correlation_id=result.correlation_id,
            target_device_id=target,
            action=action,
            status=IntentStatus.CONFIRMED,
            confirmed_at_ms=now_ms(),
        )

    @staticmethod
    def _cancelled(
        result: GestureResult,
        reason: str,
        *,
        target_device_id: str | None = None,
        action: IntentAction | None = None,
    ) -> IntentResult:
        cancelled = IntentResult(
            correlation_id=result.correlation_id,
            target_device_id=target_device_id,
            status=IntentStatus.CANCELLED,
            cancel_reason=reason,
        )
        if action is not None:
            cancelled.action = action
        return cancelled
