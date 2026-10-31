"""Track NFR-01 timestamps without putting them in MQTT topics."""
from __future__ import annotations
from dataclasses import dataclass, field
@dataclass
class LatencyTracker:
    timestamps: dict[str, dict[str, int]] = field(default_factory=dict)
    def mark(self, correlation_id: str, name: str, timestamp_ms: int) -> None:
        self.timestamps.setdefault(correlation_id, {})[name] = timestamp_ms
    def elapsed_ms(self, correlation_id: str, start: str, end: str) -> int | None:
        values=self.timestamps.get(correlation_id, {})
        return values[end]-values[start] if start in values and end in values else None
