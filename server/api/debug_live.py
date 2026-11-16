"""[임시·개발용] 실시간 동작 확인: Edge 영상 + 손동작 판정 결과를 관리자 웹에서 본다.

제거 방법: 이 파일과 ``web/src/pages/DebugLivePage.tsx``를 지우고, ``DEBUG-LIVE`` 표시가 붙은 줄을 지운다.
    grep -rn "DEBUG-LIVE" server web/src

- 환경변수 ``DEBUG_LIVE=1``일 때만 켜진다. 꺼져 있으면 프레임을 들고 있지 않고 API는 404다.
- 가장 최근 프레임 1장만 메모리에 둔다. 디스크·DB에는 저장하지 않는다(규격 5.6, NFR-03).
- ADMIN만 볼 수 있다.

API
- ``GET /api/v1/debug/live/stream``  판정 결과를 겹친 MJPEG (``<img src>``로 바로 보기)
- ``GET /api/v1/debug/live/state``   최근 판정 결과·FPS·처리 시간 JSON
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from server.api import AdminUser, ok
from server.services import web_error

router = APIRouter(prefix="/api/v1/debug/live", tags=["debug-live"])

ENV = "DEBUG_LIVE"
BOUNDARY = "frame"
STREAM_POLL_SEC = 0.03


def enabled() -> bool:
    return os.environ.get(ENV, "").lower() in ("1", "true", "yes", "on")


class LiveView:
    """가장 최근 프레임 1장과 판정 결과. 프레임 수신 스레드가 쓰고 HTTP 요청이 읽는다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.seq = 0
        self.jpeg: bytes | None = None
        self.state: dict[str, Any] = {}
        self._times: deque[float] = deque(maxlen=60)
        self._last_intent: dict[str, Any] | None = None  # 마지막으로 나온 의도 결과(선택·확정·취소)

    def record(self, jpeg: bytes, metadata: Any, gesture: Any, intent: Any, proc_ms: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._times.append(now)
            span = self._times[-1] - self._times[0] if len(self._times) > 1 else 0
            fps = (len(self._times) - 1) / span if span > 0 else 0.0
            vector = gesture.pointing_vector
            self.jpeg = jpeg
            self.seq += 1
            self.state = {
                "edge_id": metadata.edge_id,
                "frame_id": metadata.frame_id,
                "width": metadata.width,
                "height": metadata.height,
                "mirrored": metadata.mirrored,
                "rotation_deg": metadata.rotation_deg,
                "gesture": gesture.gesture.value,
                "handedness": gesture.handedness.value,
                "stable_frames": gesture.stable_frames,
                "hold_time_ms": gesture.hold_time_ms,
                "pointing_vector": None if vector is None else {
                    "start_x": vector.start_x, "start_y": vector.start_y,
                    "end_x": vector.end_x, "end_y": vector.end_y},
                "intent": None if intent is None else {
                    "status": intent.status.value, "action": intent.action.value,
                    "target_device_id": intent.target_device_id, "cancel_reason": intent.cancel_reason},
                "fps": round(fps, 1),
                "ai_ms": round(proc_ms, 1),
                "edge_to_server_ms": int(time.time() * 1000) - metadata.captured_at_ms,
                "updated_at_ms": int(time.time() * 1000),
            }
            if intent is not None:
                self._last_intent = self.state["intent"]
            self.state["last_intent"] = self._last_intent

    def snapshot(self) -> tuple[int, bytes | None, dict[str, Any]]:
        with self._lock:
            return self.seq, self.jpeg, dict(self.state)

    def clear(self) -> None:
        with self._lock:
            self.jpeg, self.state = None, {}


def install(app) -> None:
    """앱 생성 시 한 번 호출. 꺼져 있으면 아무것도 하지 않는다."""
    app.state.debug_live = LiveView() if enabled() else None


def record(app, jpeg: bytes, metadata: Any, gesture: Any, intent: Any, proc_ms: float) -> None:
    view = getattr(app.state, "debug_live", None)
    if view is not None:
        view.record(jpeg, metadata, gesture, intent, proc_ms)


def clear(app) -> None:
    view = getattr(app.state, "debug_live", None)
    if view is not None:
        view.clear()


def _view(app) -> LiveView:
    view = getattr(app.state, "debug_live", None)
    if view is None:
        raise web_error("NOT_FOUND", "DEBUG_LIVE가 꺼져 있습니다")
    return view


def annotate(jpeg: bytes, state: dict[str, Any]) -> bytes:
    """판정 결과를 영상에 겹친다. 좌표는 '똑바로 선 화면' 기준이므로 영상도 같은 방향으로 돌린다."""
    import cv2
    import numpy as np

    frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jpeg
    if state.get("mirrored"):
        frame = cv2.flip(frame, 1)
    rotate = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    if state.get("rotation_deg") in rotate:
        frame = cv2.rotate(frame, rotate[state["rotation_deg"]])
    h, w = frame.shape[:2]
    vector = state.get("pointing_vector")
    if vector:
        start = (int(vector["start_x"] * w), int(vector["start_y"] * h))
        end = (int(vector["end_x"] * w), int(vector["end_y"] * h))
        cv2.arrowedLine(frame, start, end, (0, 0, 255), 3, tipLength=0.25)
    lines = [
        f"{state.get('gesture', '-')}  {state.get('handedness', '')}",
        f"stable {state.get('stable_frames', 0)}f / {state.get('hold_time_ms', 0)}ms",
    ]
    for i, text in enumerate(lines):
        y = 28 + 28 * i
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 255, 80), 2)
    ok_, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return encoded.tobytes() if ok_ else jpeg


@router.get("/state")
def live_state(request: Request, _admin: AdminUser) -> dict:
    _, _, state = _view(request.app).snapshot()
    return ok({"connected_edges": sorted(request.app.state.connected_edges), **state})


@router.get("/stream")
async def live_stream(request: Request, _admin: AdminUser) -> StreamingResponse:
    view = _view(request.app)

    async def frames():
        last = -1
        while not await request.is_disconnected():
            seq, jpeg, state = view.snapshot()
            if jpeg is not None and seq != last:
                last = seq
                body = await asyncio.to_thread(annotate, jpeg, state)
                yield (f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(body)}\r\n\r\n"
                       .encode() + body + b"\r\n")
            await asyncio.sleep(STREAM_POLL_SEC)

    return StreamingResponse(frames(), media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
                             headers={"Cache-Control": "no-store"})
