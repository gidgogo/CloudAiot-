"""Track NFR-01 timestamps per correlation_id without putting them in MQTT topics."""
from __future__ import annotations

from dataclasses import dataclass, field

GESTURE_DETECTED = "gesture_detected"
INTENT_CONFIRMED = "intent_confirmed"


@dataclass
class LatencyTracker:
    """Keeps the newest max_entries correlation_ids; older ones are dropped so memory stays bounded."""

    timestamps: dict[str, dict[str, int]] = field(default_factory=dict)
    max_entries: int = 1000

    def __post_init__(self) -> None:
        if self.max_entries < 1:
            raise ValueError("max_entries must be at least 1")

    def mark(self, correlation_id: str, name: str, timestamp_ms: int) -> None:
        if correlation_id not in self.timestamps:
            self.timestamps[correlation_id] = {}
            while len(self.timestamps) > self.max_entries:
                del self.timestamps[next(iter(self.timestamps))]
        self.timestamps[correlation_id][name] = timestamp_ms

    def elapsed_ms(self, correlation_id: str, start: str, end: str) -> int | None:
        values = self.timestamps.get(correlation_id, {})
        return values[end] - values[start] if start in values and end in values else None
