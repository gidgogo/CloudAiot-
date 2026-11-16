"""전송 대기 프레임 버퍼 (공통 인터페이스 v1 5.6 프레임 적체 방지).

전송 대기 프레임은 최대 1개(MAX_PENDING_FRAMES)이며, 새 프레임이 들어오면 대기 중인
오래된 프레임을 폐기한다. 같은 이벤트 루프 안에서만 사용한다.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np

from shared.constants import MAX_PENDING_FRAMES

assert MAX_PENDING_FRAMES == 1, "LatestFrameBuffer는 대기 프레임 1개만 지원한다"


@dataclass(slots=True)
class CapturedFrame:
    image: np.ndarray
    captured_at_ms: int  # UTC Unix ms, 메타데이터 captured_at_ms로 전달
    captured_perf: float  # time.perf_counter() 값, 엣지 내부 지연 측정용


class LatestFrameBuffer:
    def __init__(self) -> None:
        self._item: CapturedFrame | None = None
        self._ready = asyncio.Event()

    def put(self, item: CapturedFrame) -> bool:
        """프레임을 넣는다. 대기 중이던 프레임을 덮어써 폐기했으면 True."""
        replaced = self._item is not None
        self._item = item
        self._ready.set()
        return replaced

    async def get(self) -> CapturedFrame:
        """가장 최신 프레임을 꺼낸다. 비어 있으면 새 프레임이 들어올 때까지 기다린다."""
        while self._item is None:
            self._ready.clear()
            await self._ready.wait()
        item, self._item = self._item, None
        self._ready.clear()
        return item

    def __len__(self) -> int:
        return 0 if self._item is None else 1
