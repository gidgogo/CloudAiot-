"""In-memory Edge metrics; callers export these values to logs or monitoring.

장시간 실행되는 Raspberry Pi에서 메모리가 늘지 않도록 최근 WINDOW개 측정값만 유지한다.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from time import perf_counter

WINDOW = 300  # 10 FPS 기준 약 30초
FPS_WINDOW_SEC = 5.0  # 최근 이 시간 동안의 전송 수로 FPS를 계산한다


def _mean(values) -> float:
    return sum(values) / len(values) if values else 0.0


def _p95(values) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


@dataclass
class EdgeMetrics:
    captured_frames: int = 0
    sent_frames: int = 0
    dropped_frames: int = 0  # 적체로 덮어쓴 프레임 + 전송 실패·용량 초과 프레임
    reconnects: int = 0
    ack_timeouts: int = 0
    ack_counts: Counter = field(default_factory=Counter)
    encoding_ms: deque = field(default_factory=lambda: deque(maxlen=WINDOW))
    round_trip_ms: deque = field(default_factory=lambda: deque(maxlen=WINDOW))  # 전송 시작 → ACK
    capture_to_ack_ms: deque = field(default_factory=lambda: deque(maxlen=WINDOW))  # 촬영 → ACK
    _sent_times: deque = field(default_factory=deque, repr=False)  # 최근 FPS_WINDOW_SEC 동안의 전송 시각
    _started_at: float = field(default_factory=perf_counter, repr=False)

    def mark_captured(self) -> None:
        self.captured_frames += 1

    def mark_dropped(self, count: int = 1) -> None:
        self.dropped_frames += count

    def mark_encoded(self, started_at: float) -> None:
        self.encoding_ms.append((perf_counter() - started_at) * 1000)

    def mark_sent(self, started_at: float | None = None) -> None:
        """전송 완료를 기록한다. started_at을 주면 이전 버전처럼 인코딩 시간도 기록한다."""
        self.sent_frames += 1
        now = perf_counter()
        self._sent_times.append(now)
        self._prune(now)
        if started_at is not None:
            self.mark_encoded(started_at)

    def mark_ack(self, started_at: float, status: str = "PROCESSED", captured_at: float | None = None) -> None:
        now = perf_counter()
        self.ack_counts[status] += 1
        self.round_trip_ms.append((now - started_at) * 1000)
        if captured_at is not None:
            self.capture_to_ack_ms.append((now - captured_at) * 1000)

    def mark_reconnect(self) -> None:
        self.reconnects += 1

    def mark_ack_timeout(self) -> None:
        self.ack_timeouts += 1

    def _prune(self, now: float) -> None:
        while self._sent_times and now - self._sent_times[0] > FPS_WINDOW_SEC:
            self._sent_times.popleft()

    def send_fps(self, now: float | None = None) -> float:
        """현재 시각 기준 최근 FPS_WINDOW_SEC 동안의 전송 FPS. 전송이 멈추면 0으로 떨어진다."""
        now = perf_counter() if now is None else now
        self._prune(now)
        window = min(FPS_WINDOW_SEC, now - self._started_at)
        return len(self._sent_times) / window if window > 0 else 0.0

    def snapshot(self) -> dict[str, float | int | dict[str, int]]:
        return {
            "captured_frames": self.captured_frames,
            "sent_frames": self.sent_frames,
            "dropped_frames": self.dropped_frames,
            "reconnects": self.reconnects,
            "ack_timeouts": self.ack_timeouts,
            "send_fps": round(self.send_fps(), 2),
            "mean_encoding_ms": round(_mean(self.encoding_ms), 2),
            "mean_round_trip_ms": round(_mean(self.round_trip_ms), 2),
            "p95_round_trip_ms": round(_p95(self.round_trip_ms), 2),
            "mean_capture_to_ack_ms": round(_mean(self.capture_to_ack_ms), 2),
            "ack_counts": dict(self.ack_counts),
        }
