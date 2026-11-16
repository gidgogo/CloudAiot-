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
from shared.types import GestureResult, GestureType, IntentAction, IntentResult, IntentStatus, PointingVector, now_ms

log = logging.getLogger(__name__)

DEFAULT_GESTURE_ACTIONS: dict[GestureType, IntentAction] = {
    GestureType.THUMB_UP: IntentAction.ON,
    GestureType.THUMB_DOWN: IntentAction.OFF,
    GestureType.HELP: IntentAction.HELP,
}
MAPPABLE_GESTURES = frozenset(DEFAULT_GESTURE_ACTIONS)

# Returns the action mapped to a gesture, or None when that mapping is disabled.
ActionLookup = Callable[[GestureType], IntentAction | None]

_INTEGER_FIELDS = ("detected_at_ms", "stable_frames", "hold_time_ms")


class IntentEngine:
    """Decide spec 6.2 intents from spec 6.1 gesture results, one frame at a time.

    regions are the registered device pointing regions (spec 7.4); call update_regions when they change.
    frame_width and frame_height are used when consume() is not given the frame size.
    action_for returns the action mapped to a gesture, or None when that mapping is disabled
    (the same shape as the web GestureMappingService.action_for); it defaults to DEFAULT_GESTURE_ACTIONS.
    """

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
        # The correlation_id of the latest pointing frame of the current selection, used by tick().
        self._selection_correlation_id = ""

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
        if selected is not None and not self._is_enabled_device(selected):
            self.state.clear()

    def consume(
        self,
        result: GestureResult,
        *,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> IntentResult | None:
        """Process one gesture result. Pass the frame size from the frame metadata when it is known."""
        checked = _checked(result)
        if checked is None or self._is_stale(checked.detected_at_ms):
            return None
        self._start_new_runs(checked.gesture)
        timed_out_device = self._expire_selection(checked.detected_at_ms)
        if timed_out_device is not None:
            return self._cancelled(checked, GESTURE_TIMEOUT, target_device_id=timed_out_device)
        if not self._is_stable(checked):
            return None
        if checked.gesture is GestureType.POINTING:
            return self._point(checked, *self._frame_size(frame_width, frame_height))
        if checked.gesture in MAPPABLE_GESTURES and checked.gesture is not self._acted_gesture:
            return self._mapped(checked)
        return None

    def tick(self, at_ms: int | None = None) -> IntentResult | None:
        """Expire the selection by time alone, for when no frames arrive (for example the edge disconnected).

        Call this periodically. Past the selection timeout it returns one GESTURE_TIMEOUT cancellation
        (with the correlation_id of the last pointing frame) and drops the selection; otherwise None.
        at_ms defaults to the current UTC time in ms.
        """
        if self.state.state is not IntentState.TARGET_SELECTED:
            return None
        timed_out_device = self._expire_selection(now_ms() if at_ms is None else at_ms)
        if timed_out_device is None:
            return None
        return self._cancelled_for(
            self._selection_correlation_id, GESTURE_TIMEOUT, target_device_id=timed_out_device
        )

    # --- frame bookkeeping ----------------------------------------------------

    def _is_stale(self, at_ms: int) -> bool:
        """A frame detected before the current selection cannot act on it."""
        return self.state.state is IntentState.TARGET_SELECTED and at_ms < self.state.selected_at_ms

    def _start_new_runs(self, gesture: GestureType) -> None:
        """A run is a series of frames with the same gesture; a different gesture ends the current run."""
        if gesture is not self._acted_gesture:
            self._acted_gesture = None
        if gesture is not GestureType.POINTING:
            self._last_pointing_reason = None

    def _expire_selection(self, at_ms: int) -> str | None:
        """Return the device whose selection timed out at this frame, if any."""
        if self.state.state is not IntentState.TARGET_SELECTED:
            return None
        device_id = self.state.target_device_id
        self.state.active_target(at_ms)
        return device_id if self.state.state is IntentState.IDLE else None

    def _is_stable(self, result: GestureResult) -> bool:
        """Spec 15: a gesture below the stability thresholds can neither select nor confirm."""
        return (
            result.stable_frames >= self.parameters.min_stable_frames
            and result.hold_time_ms >= self.parameters.min_hold_ms
        )

    def _frame_size(self, frame_width: int | None, frame_height: int | None) -> tuple[int, int]:
        """The size sent with this frame (spec 4.3), falling back to the engine default."""
        width = self.frame_width if frame_width is None else frame_width
        height = self.frame_height if frame_height is None else frame_height
        return width, height

    def _is_enabled_device(self, device_id: str) -> bool:
        return any(region.enabled and region.device_id == device_id for region in self._regions)

    # --- POINTING: select a device ---------------------------------------------

    def _point(self, result: GestureResult, width: int, height: int) -> IntentResult | None:
        if result.pointing_vector is None:  # never true after _checked; keeps the type checker satisfied
            return None
        angle_deg = pointing_direction_deg(result.pointing_vector, width, height)
        if self.state.state is IntentState.TARGET_SELECTED:
            selected = self.state.target_device_id
            if self.state.cancel_if_direction_changed(angle_deg):
                return self._cancelled(result, DIRECTION_CHANGED, target_device_id=selected)
            # Within the allowed angle: keep the current device even if a neighbouring region matches.
            self.state.keep_alive(result.detected_at_ms)
            self._selection_correlation_id = result.correlation_id
            return None
        match = match_device_detail(angle_deg, self._regions)
        if match.device_id is None:
            if match.cancel_reason == self._last_pointing_reason:
                return None
            self._last_pointing_reason = match.cancel_reason
            return self._cancelled(result, match.cancel_reason)
        self._last_pointing_reason = None
        self.state.select(match.device_id, result.detected_at_ms, angle_deg=angle_deg)
        self._selection_correlation_id = result.correlation_id
        return IntentResult(correlation_id=result.correlation_id, target_device_id=match.device_id)

    # --- thumb and HELP: act through the gesture mapping ------------------------

    def _mapped(self, result: GestureResult) -> IntentResult | None:
        """Act once per run on a mapped gesture; a disabled mapping cancels with INVALID_GESTURE."""
        action = self._action_for(result.gesture)
        if action is IntentAction.HELP and self._in_help_cooldown(result.detected_at_ms):
            # Not marked as acted on, so the same HELP run can still confirm once the cooldown is over.
            return None
        self._acted_gesture = result.gesture
        if action is None:
            return self._invalid(result)
        if action is IntentAction.HELP:
            return self._help(result)
        return self._command(result, action)

    def _in_help_cooldown(self, at_ms: int) -> bool:
        last_at_ms = self._last_help_at_ms
        return last_at_ms is not None and at_ms - last_at_ms < self.parameters.help_cooldown_ms

    def _invalid(self, result: GestureResult) -> IntentResult:
        """The gesture's mapping is disabled: cancel the intent and any selection with INVALID_GESTURE."""
        selected = self.state.target_device_id
        if self.state.state is IntentState.TARGET_SELECTED:
            self.state.cancel(INVALID_GESTURE)
        return self._cancelled(result, INVALID_GESTURE, target_device_id=selected)

    def _help(self, result: GestureResult) -> IntentResult:
        self._last_help_at_ms = result.detected_at_ms
        # Asking for help drops any device selection so a following thumb cannot operate it.
        self.state.clear()
        return self._confirmed(result, IntentAction.HELP)

    def _command(self, result: GestureResult, action: IntentAction) -> IntentResult:
        target = self.state.active_target(result.detected_at_ms)
        if target is None:
            return self._cancelled(result, TARGET_NOT_FOUND, action=action)
        self.state.confirm()
        return self._confirmed(result, action, target_device_id=target)

    # --- results ----------------------------------------------------------------

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
        return IntentEngine._cancelled_for(
            result.correlation_id, reason, target_device_id=target_device_id, action=action
        )

    @staticmethod
    def _cancelled_for(
        correlation_id: str,
        reason: str,
        *,
        target_device_id: str | None = None,
        action: IntentAction | None = None,
    ) -> IntentResult:
        cancelled = IntentResult(
            correlation_id=correlation_id,
            target_device_id=target_device_id,
            status=IntentStatus.CANCELLED,
            cancel_reason=reason,
        )
        if action is not None:
            cancelled.action = action
        return cancelled


# --- received message checks (spec 3.3, 14.6, 14.7) -------------------------------


def _checked(result: GestureResult) -> GestureResult | None:
    """Return the result ready to use, or None after logging why it must be ignored."""
    problem = _schema_problem(result)
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
        # A plain spec string such as "THUMB_UP" is accepted and converted for the identity checks.
        result = replace(result, gesture=GestureType(result.gesture))
    return result


def _schema_problem(result: GestureResult) -> str | None:
    """The spec 12.2 error code that makes the message unusable, or None when it is valid."""
    if result.schema_version != SCHEMA_VERSION:
        return "UNSUPPORTED_VERSION"
    try:
        gesture = GestureType(result.gesture)
    except ValueError:
        return "INVALID_SCHEMA: gesture"
    for name in _INTEGER_FIELDS:
        value = getattr(result, name)
        if isinstance(value, bool) or not isinstance(value, int):
            return f"INVALID_SCHEMA: {name}"
    vector = result.pointing_vector
    if gesture is GestureType.POINTING and vector is None:
        return "INVALID_SCHEMA: pointing_vector"
    if vector is not None and not _is_normalized(vector):
        return "INVALID_SCHEMA: pointing_vector"
    return None


def _is_normalized(vector: PointingVector) -> bool:
    """Spec 4.1: every coordinate is within 0.0 to 1.0 (checked again because the vector is mutable)."""
    return all(0.0 <= value <= 1.0 for value in (vector.start_x, vector.start_y, vector.end_x, vector.end_y))
