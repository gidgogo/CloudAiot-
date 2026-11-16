"""Edge–AI 프레임 전송 계약·동작 테스트 (공통 인터페이스 v1 5장, 15장 Edge–AI)."""
import asyncio
import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest
from websockets.asyncio.server import serve

from edge.camera import CameraError
from edge.dev.mock_frame_server import make_server_handlers
from edge.frame_buffer import CapturedFrame, LatestFrameBuffer
from edge.frame_encoder import FrameEncoder
from edge.main import capture_loop, run_stream, send_loop
from edge.metrics import FPS_WINDOW_SEC, EdgeMetrics
from edge.websocket_client import FrameAckError, FrameWebSocketClient, backoff_delays, parse_ack
from shared.constants import FRAME_WS_PATH

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "shared" / "schemas"
EDGE_CFG = {"edge_id": "raspberrypi-01", "camera_id": "camera-01"}
CAMERA_CFG = {"width": 320, "height": 240, "fps": 20, "jpeg_quality": 80, "mirrored": True, "rotation_deg": 90}


def schema(name):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def frame(width=640, height=480):
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, (height, width, 3), dtype=np.uint8)


class FakeCamera:
    """fail_reads: 실패로 응답할 read 번호 집합. broken_after: 이 횟수 이후 영구 고장(재오픈도 실패)."""

    def __init__(self, fail_reads=(), broken_after=None):
        self.reads, self.opens, self.closes = 0, 0, 0
        self.fail_reads, self.broken_after = set(fail_reads), broken_after

    @property
    def broken(self):
        return self.broken_after is not None and self.reads >= self.broken_after

    def open(self):
        self.opens += 1
        if self.broken:
            raise CameraError("cannot open camera 0")

    def close(self):
        self.closes += 1

    def read(self):
        self.reads += 1
        if self.broken or self.reads in self.fail_reads:
            return None
        return frame(320, 240)


def valid_ack(frame_id, status="PROCESSED"):
    return json.dumps({"schema_version": "1.0", "type": "frame_ack", "frame_id": frame_id, "status": status,
                       "received_at_ms": 1, "processed_at_ms": 2, "processing_time_ms": 1, "extra": "ignored"})


# --- 인코딩·메타데이터 ------------------------------------------------------

def test_encoded_metadata_matches_v1_schema():
    encoder = FrameEncoder(320, 240, 80)
    metadata, jpeg = encoder.encode(frame(), edge_id="raspberrypi-01", camera_id="camera-01",
                                    mirrored=True, rotation_deg=90, captured_at_ms=1793430000000)
    payload = metadata.as_dict()
    jsonschema.validate(payload, schema("frame-metadata.schema.json"))
    assert payload["width"] == 320 and payload["height"] == 240
    assert payload["mirrored"] is True and payload["rotation_deg"] == 90
    assert payload["captured_at_ms"] == 1793430000000
    assert payload["correlation_id"] == payload["frame_id"]
    assert jpeg[:2] == b"\xff\xd8"

    import cv2
    decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (240, 320, 3)


@pytest.mark.parametrize("kwargs", [{"jpeg_quality": 0}, {"jpeg_quality": 101}, {"width": 0}])
def test_encoder_rejects_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        FrameEncoder(**kwargs)


# --- 적체 방지 -------------------------------------------------------------

def test_buffer_keeps_only_latest_frame():
    async def scenario():
        buffer = LatestFrameBuffer()
        assert buffer.put(CapturedFrame(frame(), 1, 0.0)) is False
        assert buffer.put(CapturedFrame(frame(), 2, 0.0)) is True
        assert len(buffer) == 1
        assert (await buffer.get()).captured_at_ms == 2
        assert len(buffer) == 0
        waiter = asyncio.create_task(buffer.get())
        await asyncio.sleep(0)
        assert not waiter.done()
        buffer.put(CapturedFrame(frame(), 3, 0.0))
        assert (await asyncio.wait_for(waiter, 1)).captured_at_ms == 3

    asyncio.run(scenario())


# --- ACK·재접속 -------------------------------------------------------------

def test_parse_ack_accepts_spec_payload():
    ack = parse_ack(valid_ack("f1"))
    assert ack.frame_id == "f1" and ack.status == "PROCESSED"
    jsonschema.validate(json.loads(valid_ack("e17d8451-59dd-4c45-92e0-3fdc018e72ab")), schema("frame-ack.schema.json"))


@pytest.mark.parametrize("raw", [
    "not json",
    "[]",
    json.dumps({"schema_version": "2.0", "type": "frame_ack", "frame_id": "f", "status": "PROCESSED"}),
    json.dumps({"schema_version": "1.0", "type": "frame_ack", "frame_id": "f", "status": "OK"}),
    json.dumps({"schema_version": "1.0", "type": "other", "frame_id": "f", "status": "PROCESSED"}),
])
def test_parse_ack_rejects_invalid_payload(raw):
    with pytest.raises(FrameAckError):
        parse_ack(raw)


def test_backoff_is_exponential_and_capped_at_30s():
    assert list(backoff_delays(8)) == [1, 2, 4, 8, 16, 30, 30, 30]


async def start_server(handler, process_request=None):
    server = await serve(handler, "127.0.0.1", 0, process_request=process_request)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}"


def test_send_frame_order_headers_and_stale_ack():
    received = {}

    async def handler(connection):
        received["headers"] = dict(connection.request.headers)
        received["path"] = connection.request.path
        metadata = json.loads(await connection.recv())
        received["binary"] = await connection.recv()
        await connection.send(valid_ack("previous-frame"))  # 늦게 도착한 이전 ACK
        await connection.send(valid_ack(metadata["frame_id"], "DROPPED"))
        await connection.wait_closed()

    async def scenario():
        server, url = await start_server(handler)
        async with server:
            client = FrameWebSocketClient(url, "secret-token", "raspberrypi-01")
            await client.connect()
            metadata, jpeg = FrameEncoder(320, 240).encode(frame(), edge_id="raspberrypi-01", camera_id="camera-01")
            ack = await client.send_frame(metadata, jpeg)
            await client.close()
        return metadata, jpeg, ack

    metadata, jpeg, ack = asyncio.run(scenario())
    assert received["path"] == FRAME_WS_PATH
    assert received["headers"]["authorization"] == "Bearer secret-token"
    assert received["headers"]["x-edge-id"] == "raspberrypi-01"
    assert received["binary"] == jpeg
    assert ack.frame_id == metadata.frame_id and ack.status == "DROPPED"


def test_ack_timeout_raises():
    async def handler(connection):
        await connection.recv(); await connection.recv()
        await connection.wait_closed()  # ACK를 보내지 않음

    async def scenario():
        server, url = await start_server(handler)
        async with server:
            client = FrameWebSocketClient(url, "t", "e", ack_timeout_sec=0.1)
            await client.connect()
            metadata, jpeg = FrameEncoder(320, 240).encode(frame(), edge_id="e", camera_id="c")
            with pytest.raises(TimeoutError):
                await client.send_frame(metadata, jpeg)
            await client.close()

    asyncio.run(scenario())


def test_rejected_token_retries_with_backoff_then_fails():
    process_request, handler = make_server_handlers(token="right")
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def scenario():
        server, url = await start_server(handler, process_request)
        async with server:
            client = FrameWebSocketClient(url, "wrong", "raspberrypi-01", sleep=fake_sleep)
            with pytest.raises(ConnectionError):
                await client.connect_with_retry(max_attempts=3)

    asyncio.run(scenario())
    assert sleeps == [1, 2, 4]


def test_skeleton_reconnect_tries_one_backoff_cycle():
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def scenario():
        client = FrameWebSocketClient("ws://127.0.0.1:1", "t", "e", open_timeout_sec=0.2, sleep=fake_sleep)
        with pytest.raises(ConnectionError):
            await client.reconnect()

    asyncio.run(scenario())
    assert sleeps == [1, 2, 4, 8, 16, 30]


def test_connect_closes_previous_socket():
    connections = []

    async def handler(connection):
        connections.append(connection)
        await connection.wait_closed()

    async def scenario():
        server, url = await start_server(handler)
        async with server:
            client = FrameWebSocketClient(url, "t", "e")
            await client.connect()
            await client.connect()
            await asyncio.wait_for(connections[0].wait_closed(), 1)
            await client.close()

    asyncio.run(scenario())
    assert len(connections) == 2


# --- 전체 스트리밍 루프 ------------------------------------------------------

def test_stream_drops_stale_frames_when_server_is_slow():
    stats = {}
    process_request, handler = make_server_handlers(token="dev", processing_delay_ms=150, stats=stats)

    async def scenario():
        server, url = await start_server(handler, process_request)
        async with server:
            client = FrameWebSocketClient(url, "dev", EDGE_CFG["edge_id"])
            metrics = await run_stream(FakeCamera(), FrameEncoder(320, 240, 80), client, EdgeMetrics(),
                                       EDGE_CFG, CAMERA_CFG, duration_sec=2.0, report_interval_sec=0)
            await client.close()
        return metrics

    metrics = asyncio.run(scenario())
    snap = metrics.snapshot()
    # 20 FPS로 촬영하지만 서버가 프레임당 150ms 걸리므로 대부분 폐기되고 최신 프레임만 전송된다.
    # 시간에 민감한 CI(Windows 등)에서도 깨지지 않도록 하한만 느슨하게 검사한다.
    assert snap["sent_frames"] >= 2
    assert snap["dropped_frames"] > snap["sent_frames"]
    assert snap["ack_counts"] == {"PROCESSED": snap["sent_frames"]}
    assert stats["frames"] >= snap["sent_frames"]
    assert snap["captured_frames"] >= snap["sent_frames"] + snap["dropped_frames"] - 1
    assert snap["mean_round_trip_ms"] >= 100


def test_stream_reconnects_after_server_closes_connection():
    connections = []

    async def handler(connection):
        connections.append(connection)
        async for message in connection:
            if isinstance(message, str):
                frame_id = json.loads(message)["frame_id"]
                continue
            await connection.send(valid_ack(frame_id))
            if len(connections) == 1:
                await connection.close()  # 첫 연결은 프레임 하나 처리 후 끊음
                return

    async def scenario():
        server, url = await start_server(handler)
        async with server:
            client = FrameWebSocketClient(url, "t", EDGE_CFG["edge_id"], sleep=lambda _: asyncio.sleep(0))
            metrics = await run_stream(FakeCamera(), FrameEncoder(320, 240, 80), client, EdgeMetrics(),
                                       EDGE_CFG, CAMERA_CFG, duration_sec=1.5, report_interval_sec=0)
            await client.close()
        return metrics

    metrics = asyncio.run(scenario())
    assert len(connections) >= 2
    assert metrics.reconnects >= 1
    assert metrics.sent_frames >= 2


def test_ack_timeout_keeps_connection_until_threshold():
    connections = []

    async def handler(connection):
        connections.append(connection)
        async for _ in connection:  # ACK를 절대 보내지 않음
            pass

    async def scenario():
        server, url = await start_server(handler)
        async with server:
            client = FrameWebSocketClient(url, "t", "e", ack_timeout_sec=0.05, sleep=lambda _: asyncio.sleep(0))
            buffer, metrics, stop = LatestFrameBuffer(), EdgeMetrics(), asyncio.Event()
            task = asyncio.create_task(send_loop(client, FrameEncoder(320, 240), buffer, metrics,
                                                 EDGE_CFG, CAMERA_CFG, stop, max_ack_timeouts=3))
            for i in range(2):
                buffer.put(CapturedFrame(frame(320, 240), i, 0.0))
                await asyncio.sleep(0.15)
            two_timeouts = (len(connections), metrics.ack_timeouts, metrics.reconnects)
            buffer.put(CapturedFrame(frame(320, 240), 2, 0.0))
            await asyncio.sleep(0.2)
            stop.set(); task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()
            return two_timeouts, metrics

    (conns, timeouts, reconnects), metrics = asyncio.run(scenario())
    assert (conns, timeouts, reconnects) == (1, 2, 0)  # 타임아웃 2번까지는 같은 연결 유지
    assert metrics.ack_timeouts == 3
    assert metrics.reconnects == 1  # 3번째 연속 타임아웃 후 재접속


def test_stream_stops_when_camera_fails():
    async def handler(connection):
        await connection.wait_closed()

    async def scenario():
        server, url = await start_server(handler)
        async with server:
            client = FrameWebSocketClient(url, "t", "e", ack_timeout_sec=0.05)
            with pytest.raises(CameraError):
                await run_stream(camera, FrameEncoder(320, 240), client, EdgeMetrics(),
                                 EDGE_CFG, CAMERA_CFG, duration_sec=5, report_interval_sec=0)
            await client.close()

    camera = FakeCamera(broken_after=2)
    asyncio.run(scenario())
    assert camera.closes == 1 and camera.opens == 1  # 한 번 다시 열어 보고 포기


def run_capture(camera, duration=0.6, **kwargs):
    async def scenario():
        buffer, metrics, stop = LatestFrameBuffer(), EdgeMetrics(), asyncio.Event()
        task = asyncio.create_task(capture_loop(camera, buffer, metrics, 50, stop, retry_delay_sec=0.001, **kwargs))
        await asyncio.sleep(duration)
        stop.set()
        await asyncio.wait_for(task, 1)
        return metrics

    return asyncio.run(scenario())


def test_capture_survives_transient_read_failures():
    camera = FakeCamera(fail_reads={2, 3, 4})
    metrics = run_capture(camera)
    assert metrics.captured_frames > 3
    assert camera.opens == 0  # 일시 실패는 재오픈 없이 재시도로 회복


def test_capture_reopens_camera_after_repeated_failures():
    camera = FakeCamera(fail_reads=set(range(2, 8)))
    metrics = run_capture(camera, max_read_failures=5)
    assert camera.closes == 1 and camera.opens == 1
    assert metrics.captured_frames > 3


# --- 메트릭 ---------------------------------------------------------------

def test_send_fps_drops_to_zero_when_sending_stops():
    metrics = EdgeMetrics()
    start = metrics._started_at
    for i in range(50):
        metrics._sent_times.append(start + 1 + i * 0.1)  # 1~6초 구간 10 FPS
    assert metrics.send_fps(now=start + 6) == pytest.approx(10, rel=0.05)
    assert metrics.send_fps(now=start + 6 + FPS_WINDOW_SEC + 1) == 0.0


def test_metrics_window_is_bounded():
    metrics = EdgeMetrics()
    for _ in range(1000):
        metrics.mark_encoded(0.0)
        metrics.mark_sent()
    assert len(metrics.encoding_ms) == 300
    assert metrics.sent_frames == 1000
