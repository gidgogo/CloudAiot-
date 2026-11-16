"""Edge 영상 프레임 수신 WebSocket(``/ws/v1/frames``, 규격 5장) → 손동작 인식 → 의도 판단 → 웹 이벤트.

로컬 통합 확인용 연결부다. 프레임마다
1. 메타데이터 JSON(텍스트) 다음 JPEG(바이너리)를 받아
2. ``GesturePipeline.process_jpeg``로 손동작을 판정하고 (영상은 메모리에서만 처리, 규격 5.6)
3. ``IntentEngine.consume``으로 의도를 판단한 뒤
4. ``frame_ack``를 돌려주고, 의미 있는 결과는 EventHub로 웹에 보낸다.

웹 이벤트: ``edge.connected`` / ``edge.disconnected`` / ``device.selected`` / ``gesture.confirmed``
아직 하지 않는 것: MQTT 명령 발행, HELP 제스처로 도움 요청 생성(대상 사용자 결정 필요).

인증: 환경변수 ``EDGE_TOKEN``이 있으면 ``Authorization: Bearer`` 값과 비교한다. 없으면 검사하지 않는다(개발용).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.api import debug_live  # DEBUG-LIVE
from server.services.device_service import DeviceService
from shared.constants import FRAME_WS_PATH, MAX_FRAME_BYTES, SCHEMA_VERSION
from shared.types import FrameMetadata, IntentResult, IntentStatus, now_ms

router = APIRouter()
log = logging.getLogger(__name__)

EDGE_TOKEN_ENV = "EDGE_TOKEN"
REGION_REFRESH_SEC = 5.0  # 웹에서 바꾼 기기 방향 영역을 이 주기로 다시 읽는다
CLOSE_POLICY = 1008
_META_FIELDS = {f.name for f in dataclasses.fields(FrameMetadata) if f.init}


def _ack(frame_id: str, status: str, received_at_ms: int) -> str:
    processed = now_ms()
    return json.dumps({
        "schema_version": SCHEMA_VERSION, "type": "frame_ack", "frame_id": frame_id, "status": status,
        "received_at_ms": received_at_ms, "processed_at_ms": processed,
        "processing_time_ms": max(0, processed - received_at_ms),
    })


def _token_ok(websocket: WebSocket) -> bool:
    expected = os.environ.get(EDGE_TOKEN_ENV)
    return not expected or websocket.headers.get("authorization") == f"Bearer {expected}"


def _load_devices(app) -> tuple[list, dict[str, str]]:
    with app.state.db.session() as session:
        service = DeviceService(session)
        regions = service.pointing_regions()
        names = {device.device_id: device.name for device in service.list(enabled=True)}
    return regions, names


class _EdgeSession:
    """Edge 연결 하나. 손 추적·안정화·선택 상태가 영상 하나를 따라가므로 연결마다 새로 만든다."""

    def __init__(self, app, edge_id: str) -> None:
        from server.intent.engine import IntentEngine
        from server.vision.pipeline import GesturePipeline  # mediapipe는 이 연결부를 쓸 때만 필요

        self.app = app
        self.edge_id = edge_id
        self.pipeline = GesturePipeline()
        self.engine = IntentEngine()
        self.device_names: dict[str, str] = {}
        self._regions_loaded_at = float("-inf")

    def refresh_regions(self) -> None:
        if time.monotonic() - self._regions_loaded_at < REGION_REFRESH_SEC:
            return
        regions, self.device_names = _load_devices(self.app)
        self.engine.update_regions(regions)
        self._regions_loaded_at = time.monotonic()

    def process(self, jpeg: bytes, metadata: FrameMetadata) -> IntentResult | None:
        """동기 처리(스레드에서 호출). ValueError면 INVALID 프레임."""
        self.refresh_regions()
        started = time.perf_counter()
        gesture = self.pipeline.process_jpeg(jpeg, metadata)
        from server.vision.landmark_processor import oriented_frame_size

        width, height = oriented_frame_size(metadata.width, metadata.height, metadata.rotation_deg)
        intent = self.engine.consume(gesture, frame_width=width, frame_height=height)
        debug_live.record(self.app, jpeg, metadata, gesture, intent, (time.perf_counter() - started) * 1000)  # DEBUG-LIVE
        return intent

    def publish(self, intent: IntentResult) -> None:
        events = self.app.state.events
        if intent.status is IntentStatus.PENDING and intent.target_device_id:
            device_id = intent.target_device_id
            events.publish("device.selected",
                           {"device_id": device_id, "device_name": self.device_names.get(device_id, device_id)},
                           correlation_id=intent.correlation_id)
        elif intent.status is IntentStatus.CONFIRMED:
            events.publish("gesture.confirmed",
                           {"intent_id": intent.intent_id, "action": intent.action.value,
                            "target_device_id": intent.target_device_id},
                           correlation_id=intent.correlation_id)
        else:
            log.info("[%s] intent %s (%s)", self.edge_id, intent.status.value, intent.cancel_reason)

    def close(self) -> None:
        self.pipeline.close()


@router.websocket(FRAME_WS_PATH)
async def frames(websocket: WebSocket) -> None:
    edge_id = websocket.headers.get("x-edge-id")
    if not edge_id or not _token_ok(websocket):
        await websocket.close(code=CLOSE_POLICY)
        return
    await websocket.accept()
    app = websocket.app
    session = await asyncio.to_thread(_EdgeSession, app, edge_id)
    connected = app.state.connected_edges  # 새 대시보드 연결에 현재 상태를 알릴 때 쓴다
    connected.add(edge_id)
    app.state.events.publish("edge.connected", {"edge_id": edge_id})
    log.info("edge connected: %s", edge_id)
    pending: dict[str, Any] | None = None
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            received = now_ms()
            if message.get("text") is not None:
                if pending is not None:  # 바이너리 없이 다음 메타데이터 → 이전 프레임 폐기
                    await websocket.send_text(_ack(str(pending.get("frame_id", "")), "INVALID", received))
                try:
                    pending = json.loads(message["text"])
                    if not isinstance(pending, dict) or pending.get("type") != "frame_metadata":
                        raise ValueError
                except ValueError:
                    pending = None
                continue
            jpeg = message.get("bytes")
            if pending is None or jpeg is None:
                continue
            raw, pending = pending, None
            frame_id = str(raw.get("frame_id", ""))
            try:
                if len(jpeg) > MAX_FRAME_BYTES:
                    raise ValueError("frame too large")
                metadata = FrameMetadata(**{k: v for k, v in raw.items() if k in _META_FIELDS})
                intent = await asyncio.to_thread(session.process, jpeg, metadata)
            except (ValueError, TypeError) as error:
                log.warning("[%s] INVALID frame %s: %s", edge_id, frame_id, error)
                await websocket.send_text(_ack(frame_id, "INVALID", received))
                continue
            except Exception:
                log.exception("[%s] frame %s failed", edge_id, frame_id)
                await websocket.send_text(_ack(frame_id, "ERROR", received))
                continue
            await websocket.send_text(_ack(frame_id, "PROCESSED", received))
            if intent is not None:
                session.publish(intent)
    except WebSocketDisconnect:
        pass
    finally:
        # 연결이 취소(cancel)되는 중에도 확실히 남도록 await 없이 먼저 발행하고 정리한다
        connected.discard(edge_id)
        app.state.events.publish("edge.disconnected", {"edge_id": edge_id})
        log.info("edge disconnected: %s", edge_id)
        debug_live.clear(app)  # DEBUG-LIVE
        session.close()
