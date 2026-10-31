"""In-memory Edge metrics; callers export these values to logs or monitoring."""
from __future__ import annotations
from dataclasses import dataclass, field
from time import perf_counter

@dataclass
class EdgeMetrics:
    sent_frames: int = 0
    dropped_frames: int = 0
    encoding_ms: list[float] = field(default_factory=list)
    round_trip_ms: list[float] = field(default_factory=list)
    def mark_sent(self, started_at: float) -> None:
        self.sent_frames += 1
        self.encoding_ms.append((perf_counter() - started_at) * 1000)
    def mark_ack(self, started_at: float) -> None:
        self.round_trip_ms.append((perf_counter() - started_at) * 1000)
    def snapshot(self) -> dict[str, float | int]:
        mean = lambda values: sum(values) / len(values) if values else 0.0
        return {"sent_frames": self.sent_frames, "dropped_frames": self.dropped_frames, "mean_encoding_ms": mean(self.encoding_ms), "mean_round_trip_ms": mean(self.round_trip_ms)}
