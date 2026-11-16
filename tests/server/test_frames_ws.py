"""Edge 프레임 수신(/ws/v1/frames) → 손동작 → 의도 → 웹 이벤트 연결 테스트 (MediaPipe 없이 가짜 파이프라인)."""

import json
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from server.vision import pipeline as vision_pipeline
from shared.types import FrameMetadata, GestureResult, GestureType, PointingVector, now_ms
from tests.server.test_auth_api import (  # noqa: F401 (pytest 공통 fixture)
    TEST_SETTINGS,
    anon,
    app,
    client,
    device,
    device_payload,
    events,
    fast_bcrypt,
    login,
    make_user,
    room,
    settings,
)

JPEG = b"\xff\xd8fake-jpeg"
HEADERS = {"X-Edge-ID": "raspberrypi-01", "Authorization": "Bearer dev-token"}


class FakePipeline:
    """process_jpeg가 미리 정한 제스처를 차례로 돌려준다."""

    script: list[GestureResult] = []

    def __init__(self, *args, **kwargs):
        self.closed = False

    def process_jpeg(self, jpeg, metadata):
        if not jpeg.startswith(b"\xff\xd8"):
            raise ValueError("frame is not a JPEG image")
        result = FakePipeline.script.pop(0)
        result.frame_id, result.correlation_id = metadata.frame_id, metadata.correlation_id
        return result

    def close(self):
        self.closed = True


def stable(gesture, vector=None):
    return GestureResult(gesture=gesture, pointing_vector=vector, stable_frames=10, hold_time_ms=1000,
                         detected_at_ms=now_ms())


@pytest.fixture
def fake_pipeline(monkeypatch):
    monkeypatch.setattr(vision_pipeline, "GesturePipeline", FakePipeline)
    FakePipeline.script = []
    return FakePipeline


def send_frame(ws, jpeg=JPEG):
    meta = FrameMetadata(edge_id="raspberrypi-01", camera_id="camera-01").as_dict()
    ws.send_text(json.dumps(meta))
    ws.send_bytes(jpeg)
    return json.loads(ws.receive_text())


def event_types(events):
    return [getattr(e, "event_type", None) or e["event_type"] for e in events]


def event_data(events, event_type):
    for e in events:
        if (getattr(e, "event_type", None) or e["event_type"]) == event_type:
            return getattr(e, "data", None) or e["data"]
    return None


def test_pointing_then_thumb_up_selects_and_confirms(client, device, events, fake_pipeline, monkeypatch):
    monkeypatch.setenv("EDGE_TOKEN", "dev-token")
    right = PointingVector(start_x=0.4, start_y=0.5, end_x=0.6, end_y=0.5)  # 0° → fan-01 영역(-15~15°)
    fake_pipeline.script = [stable(GestureType.POINTING, right), stable(GestureType.THUMB_UP)]

    with client.websocket_connect("/ws/v1/frames", headers=HEADERS) as ws:
        assert send_frame(ws)["status"] == "PROCESSED"
        assert send_frame(ws)["status"] == "PROCESSED"

    assert event_types(events)[0] == "edge.connected"
    assert event_data(events, "device.selected") == {"device_id": "fan-01", "device_name": "선풍기"}
    confirmed = event_data(events, "gesture.confirmed")
    assert confirmed["action"] == "ON" and confirmed["target_device_id"] == "fan-01"
    for _ in range(50):  # 연결 종료 처리는 서버 쪽에서 조금 늦게 끝난다
        if "edge.disconnected" in event_types(events):
            break
        time.sleep(0.02)
    assert event_types(events)[-1] == "edge.disconnected"


def test_non_jpeg_frame_gets_invalid_ack(anon, events, fake_pipeline):
    with anon.websocket_connect("/ws/v1/frames", headers=HEADERS) as ws:
        assert send_frame(ws, b"not-a-jpeg")["status"] == "INVALID"


def test_wrong_token_and_missing_edge_id_are_rejected(anon, fake_pipeline, monkeypatch):
    monkeypatch.setenv("EDGE_TOKEN", "dev-token")
    for headers in ({"X-Edge-ID": "raspberrypi-01", "Authorization": "Bearer wrong"}, {"Authorization": "Bearer dev-token"}):
        with pytest.raises(WebSocketDisconnect):
            with anon.websocket_connect("/ws/v1/frames", headers=headers) as ws:
                ws.receive_text()
