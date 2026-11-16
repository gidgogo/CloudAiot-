"""Count consecutive frames and hold time of the same gesture (spec 6.1 stable_frames, hold_time_ms)."""
from __future__ import annotations

from dataclasses import dataclass

from shared.types import GestureType


@dataclass(frozen=True)
class Stability:
    frames: int
    hold_ms: int
    stable: bool


NOT_STABLE = Stability(frames=0, hold_ms=0, stable=False)


@dataclass
class StabilityChecker:
    """One checker per camera. min_frames and min_hold_ms match server/intent IntentParameters."""

    min_frames: int = 6
    min_hold_ms: int = 500
    max_gap_ms: int = 500  # a longer pause between frames starts the count again
    _gesture: GestureType = GestureType.UNKNOWN
    _count: int = 0
    _started_at_ms: int = 0
    _last_at_ms: int | None = None

    def update(self, gesture: GestureType, at_ms: int) -> Stability:
        """UNKNOWN (including no hand) always reports zero so the next gesture starts a new run."""
        if gesture is GestureType.UNKNOWN:
            self.reset()
            return NOT_STABLE
        if gesture is not self._gesture or self._is_interrupted(at_ms):
            self._gesture, self._count, self._started_at_ms = gesture, 0, at_ms
        self._count += 1
        self._last_at_ms = at_ms
        hold_ms = at_ms - self._started_at_ms
        return Stability(self._count, hold_ms, self._count >= self.min_frames and hold_ms >= self.min_hold_ms)

    def reset(self) -> None:
        self._gesture, self._count, self._started_at_ms, self._last_at_ms = GestureType.UNKNOWN, 0, 0, None

    def _is_interrupted(self, at_ms: int) -> bool:
        last = self._last_at_ms
        return last is None or at_ms < last or at_ms - last > self.max_gap_ms
