"""Convert stable gesture observations to confirmed/cancelled v1 intent messages."""
from __future__ import annotations
from shared.types import GestureResult, GestureType, IntentAction, IntentResult, IntentStatus, now_ms
from server.intent.state_machine import SelectionStateMachine
class IntentEngine:
    def __init__(self, state_machine: SelectionStateMachine | None = None) -> None: self.state = state_machine or SelectionStateMachine()
    def consume(self, result: GestureResult, target_device_id: str | None = None) -> IntentResult:
        if result.gesture is GestureType.HELP:
            return IntentResult(correlation_id=result.correlation_id, action=IntentAction.HELP, status=IntentStatus.CONFIRMED, confirmed_at_ms=now_ms())
        if result.gesture is GestureType.POINTING and target_device_id:
            self.state.select(target_device_id, result.detected_at_ms)
            return IntentResult(correlation_id=result.correlation_id, target_device_id=target_device_id)
        target = self.state.active_target(result.detected_at_ms)
        actions={GestureType.THUMB_UP: IntentAction.ON, GestureType.THUMB_DOWN: IntentAction.OFF}
        if target and result.gesture in actions:
            return IntentResult(correlation_id=result.correlation_id, target_device_id=target, action=actions[result.gesture], status=IntentStatus.CONFIRMED, confirmed_at_ms=now_ms())
        return IntentResult(correlation_id=result.correlation_id, status=IntentStatus.CANCELLED, cancel_reason="TARGET_NOT_FOUND")
