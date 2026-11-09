"""Turn stable gesture observations into v1 intent results (common interface spec 6.2).

consume() returns an IntentResult only when something meaningful happens
(a device is selected, an intent is confirmed or cancelled) and None otherwise.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import replace

from server.intent.cancel_reasons import DIRECTION_CHANGED, GESTURE_TIMEOUT, INVALID_GESTURE, TARGET_NOT_FOUND
from server.intent.device_matcher import DeviceRegion, match_device_detail, pointing_direction_deg
from server.intent.latency_tracker import GESTURE_DETECTED, INTENT_CONFIRMED, LatencyTracker
from server.intent.parameters import IntentParameters
from server.intent.state_machine import IntentState, SelectionStateMachine
from shared.constants import DEFAULT_FRAME_HEIGHT, DEFAULT_FRAME_WIDTH, SCHEMA_VERSION
from shared.types import GestureResult, GestureType, IntentAction, IntentResult, IntentStatus, now_ms

log = logging.getLogger(__name__)

DEFAULT_GESTURE_ACTIONS: dict[GestureType, IntentAction] = {
    GestureType.THUMB_UP: IntentAction.ON,
    GestureType.THUMB_DOWN: IntentAction.OFF,
    GestureType.HELP: IntentAction.HELP,
}
MAPPABLE_GESTURES = frozenset(DEFAULT_GESTURE_ACTIONS)

# Returns the action mapped to a gesture, or None when that mapping is disabled.
ActionLookup = Callable[[GestureType], "IntentAction | None"]


class IntentEngine:
    def __init__(
        self,
        regions: Iterable[DeviceRegion] = (),
        *,
        parameters: IntentParameters | None = None,
        state_machine: SelectionStateMachine | None = None,
        frame_width: int = DEFAULT_FRAME_WIDTH,
        frame_height: int = DEFAULT_FRAME_HEIGHT,
        action_for: ActionLookup | None = None,
        latency_tracker: LatencyTracker | None = None,
    ) -> None:
        self.parameters = parameters or IntentParameters()
        self.latency = latency_tracker or LatencyTracker()
        self.state = state_machine or SelectionStateMachine(
            timeout_ms=self.parameters.selection_timeout_ms,
            max_angle_delta_deg=self.parameters.max_angle_delta_deg,
        )
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._regions: list[DeviceRegion] = list(regions)
        self._action_for: ActionLookup = action_for or DEFAULT_GESTURE_ACTIONS.get
        # The gesture already acted on in the current run of identical gestures.
        # It is cleared as soon as a different gesture arrives.
        self._acted_gesture: GestureType | None = None
        # The last "no single device" reason reported while pointing, so it is reported once per run.
        self._last_pointing_reason: str | None = None
        self._last_help_at_ms: int | None = None

    @property
    def regions(self) -> tuple[DeviceRegion, ...]:
        return tuple(self._regions)

    def latency_ms(self, correlation_id: str) -> int | None:
        """NFR-01: time from detecting the confirming gesture to confirming the intent, or None if unknown."""
        return self.latency.elapsed_ms(correlation_id, GESTURE_DETECTED, INTENT_CONFIRMED)

    def update_regions(self, regions: Iterable[DeviceRegion]) -> None:
        """Replace the device regions, for example after the web dashboard edits a device."""
        self._regions = list(regions)
        selected = self.state.target_device_id
        if selected is not None and not any(
            region.enabled and region.device_id == selected for region in self._regions
        ):
            self.state.clear()

    def consume(
        self,
        result: GestureResult,
        *,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> IntentResult | None:
        """Process one gesture result. Pass the frame size from the frame metadata when it is known."""
        checked = self._checked(result)
        if checked is None:
            return None
        result = checked
        at_ms = result.detected_at_ms
        if self._is_stale(at_ms):
            return None
        if result.gesture is not self._acted_gesture:
            self._acted_gesture = None
        if result.gesture is not GestureType.POINTING:
            self._last_pointing_reason = None
        timed_out_device = self._expire_selection(at_ms)
        if timed_out_device is not None:
            return self._cancelled(result, GESTURE_TIMEOUT, target_device_id=timed_out_device)
        if not self._is_stable(result):
            return None
        if result.gesture is GestureType.POINTING:
            width = self.frame_width if frame_width is None else frame_width
            height = self.frame_height if frame_height is None else frame_height
            return self._point(result, width, height)
        if result.gesture in MAPPABLE_GESTURES and result.gesture is not self._acted_gesture:
            return self._mapped(result)
        return None

    def _checked(self, result: GestureResult) -> GestureResult | None:
        """Spec 3.3, 14.6, 14.7: check the version and schema before use; ignore and log bad messages."""
        problem = self._schema_problem(result)
        if problem is not None:
            # Only identifiers and the reason are logged, never coordinates or frame contents.
            log.warning(
                "gesture result ignored: %s (frame_id=%s, correlation_id=%s)",
                problem,
                getattr(result, "frame_id", None),
                getattr(result, "correlation_id", None),
            )
            return None
        if not isinstance(result.gesture, GestureType):
            result = replace(result, gesture=GestureType(result.gesture))
        return result

    @staticmethod
    def _schema_problem(result: GestureResult) -> str | None:
        if result.schema_version != SCHEMA_VERSION:
            return "UNSUPPORTED_VERSION"
        try:
            gesture = GestureType(result.gesture)
        except ValueError:
            return "INVALID_SCHEMA: gesture"
        for name in ("detected_at_ms", "stable_frames", "hold_time_ms"):
            value = getattr(result, name)
            if isinstance(value, bool) or not isinstance(value, int):
                return f"INVALID_SCHEMA: {name}"
        vector = result.pointing_vector
        if gesture is GestureType.POINTING and vector is None:
            return "INVALID_SCHEMA: pointing_vector"
        if vector is not None and not all(
            0.0 <= value <= 1.0 for value in (vector.start_x, vector.start_y, vector.end_x, vector.end_y)
        ):
            return "INVALID_SCHEMA: pointing_vector"
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

    def _point(self, result: GestureResult, width: int, height: int) -> IntentResult | None:
        if result.pointing_vector is None:
            return None
        angle_deg = pointing_direction_deg(result.pointing_vector, width, height)
        if self.state.state is IntentState.TARGET_SELECTED:
            selected = self.state.target_device_id
            if self.state.cancel_if_direction_changed(angle_deg):
                return self._cancelled(result, DIRECTION_CHANGED, target_device_id=selected)
            # Within the allowed angle: keep the current device even if a neighbouring region matches.
            self.state.keep_alive(result.detected_at_ms)
            return None
        match = match_device_detail(angle_deg, self._regions)
        if match.device_id is None:
            if match.cancel_reason == self._last_pointing_reason:
                return None
            self._last_pointing_reason = match.cancel_reason
            return self._cancelled(result, match.cancel_reason)
        self._last_pointing_reason = None
        self.state.select(match.device_id, result.detected_at_ms, angle_deg=angle_deg)
        return IntentResult(correlation_id=result.correlation_id, target_device_id=match.device_id)

    def _mapped(self, result: GestureResult) -> IntentResult | None:
        action = self._action_for(result.gesture)
        if action is None:
            return self._invalid(result)
        if action is IntentAction.HELP:
            return self._help(result)
        return self._command(result, action)

    def _invalid(self, result: GestureResult) -> IntentResult:
        """The gesture's mapping is disabled: cancel the intent and any selection with INVALID_GESTURE."""
        self._acted_gesture = result.gesture
        selected = self.state.target_device_id
        if self.state.state is IntentState.TARGET_SELECTED:
            self.state.cancel(INVALID_GESTURE)
        return self._cancelled(result, INVALID_GESTURE, target_device_id=selected)

    def _help(self, result: GestureResult) -> IntentResult | None:
        last_at_ms = self._last_help_at_ms
        if last_at_ms is not None and result.detected_at_ms - last_at_ms < self.parameters.help_cooldown_ms:
            return None
        self._acted_gesture = result.gesture
        self._last_help_at_ms = result.detected_at_ms
        # Asking for help drops any device selection so a following thumb cannot operate it.
        self.state.clear()
        return self._confirmed(result, IntentAction.HELP)

    def _command(self, result: GestureResult, action: IntentAction) -> IntentResult:
        self._acted_gesture = result.gesture
        target = self.state.active_target(result.detected_at_ms)
        if target is None:
            return self._cancelled(result, TARGET_NOT_FOUND, action=action)
        self.state.confirm()
        return self._confirmed(result, action, target_device_id=target)

    def _confirmed(
        self,
        result: GestureResult,
        action: IntentAction,
        *,
        target_device_id: str | None = None,
    ) -> IntentResult:
        confirmed_at_ms = now_ms()
        if result.correlation_id:
            self.latency.mark(result.correlation_id, GESTURE_DETECTED, result.detected_at_ms)
            self.latency.mark(result.correlation_id, INTENT_CONFIRMED, confirmed_at_ms)
        return IntentResult(
            correlation_id=result.correlation_id,
            target_device_id=target_device_id,
            action=action,
            status=IntentStatus.CONFIRMED,
            confirmed_at_ms=confirmed_at_ms,
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
