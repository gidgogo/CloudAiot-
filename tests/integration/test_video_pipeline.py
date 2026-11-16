"""Edge WebSocket에서 AI 프레임 처리기까지의 실제 연결 계약."""

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.app import create_app
from shared.types import FrameMetadata
from tests.server.test_auth_api import TEST_SETTINGS


class FakeFrameProcessor:
    def __init__(self) -> None:
        self.frames = []
        self.closed = False

    def process(self, jpeg, metadata) -> None:
        self.frames.append((jpeg, metadata))

    def close(self) -> None:
        self.closed = True

    def tick(self):
        return None


def test_edge_frame_websocket_processes_metadata_then_jpeg_and_returns_ack():
    app = create_app(replace(TEST_SETTINGS, edge_token="edge-secret"))
    processor = FakeFrameProcessor()
    events = []
    app.state.frame_processor_factory = lambda: processor
    app.state.events.subscribe(events.append)
    metadata = FrameMetadata(edge_id="edge-01", camera_id="camera-01", captured_at_ms=123)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/v1/frames",
            headers={"Authorization": "Bearer edge-secret", "X-Edge-ID": "edge-01"},
        ) as socket:
            socket.send_text(json.dumps(metadata.as_dict()))
            socket.send_bytes(b"\xff\xd8jpeg")
            ack = socket.receive_json()

    assert ack["status"] == "PROCESSED"
    assert ack["frame_id"] == metadata.frame_id
    assert processor.frames[0][0] == b"\xff\xd8jpeg"
    assert processor.frames[0][1].captured_at_ms == 123
    assert processor.closed
    assert [event.event_type for event in events] == ["edge.connected", "edge.disconnected"]


def test_edge_frame_websocket_rejects_bad_token():
    app = create_app(replace(TEST_SETTINGS, edge_token="edge-secret"))
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect(
                "/ws/v1/frames",
                headers={"Authorization": "Bearer wrong", "X-Edge-ID": "edge-01"},
            ):
                pass
    assert closed.value.code == 4401


def test_edge_frame_websocket_marks_invalid_jpeg_without_processing():
    app = create_app(replace(TEST_SETTINGS, edge_token="edge-secret"))
    processor = FakeFrameProcessor()
    app.state.frame_processor_factory = lambda: processor
    metadata = FrameMetadata(edge_id="edge-01", camera_id="camera-01")

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/v1/frames",
            headers={"Authorization": "Bearer edge-secret", "X-Edge-ID": "edge-01"},
        ) as socket:
            socket.send_json(metadata.as_dict())
            socket.send_bytes(b"not-jpeg")
            assert socket.receive_json()["status"] == "INVALID"

    assert processor.frames == []


def test_edge_frame_websocket_acks_invalid_metadata_when_frame_id_is_known():
    app = create_app(replace(TEST_SETTINGS, edge_token="edge-secret"))
    processor = FakeFrameProcessor()
    app.state.frame_processor_factory = lambda: processor
    metadata = FrameMetadata(edge_id="different-edge", camera_id="camera-01").as_dict()

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/v1/frames",
            headers={"Authorization": "Bearer edge-secret", "X-Edge-ID": "edge-01"},
        ) as socket:
            socket.send_json(metadata)
            ack = socket.receive_json()

    assert ack["frame_id"] == metadata["frame_id"] and ack["status"] == "INVALID"

