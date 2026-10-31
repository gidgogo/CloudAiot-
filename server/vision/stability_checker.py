"""Require consecutive matching frames and a hold duration before confirmation."""
from __future__ import annotations
from dataclasses import dataclass
from shared.types import GestureType, now_ms
@dataclass
class StabilityChecker:
    min_frames: int = 6
    min_hold_ms: int = 500
    _gesture: GestureType = GestureType.UNKNOWN
    _count: int = 0
    _started_at_ms: int = 0
    def update(self, gesture: GestureType, detected_at_ms: int | None = None) -> tuple[int, int, bool]:
        timestamp = detected_at_ms or now_ms()
        if gesture != self._gesture:
            self._gesture, self._count, self._started_at_ms = gesture, 1, timestamp
        else: self._count += 1
        hold_ms = timestamp - self._started_at_ms
        return self._count, hold_ms, gesture is not GestureType.UNKNOWN and self._count >= self.min_frames and hold_ms >= self.min_hold_ms
