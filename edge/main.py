"""Raspberry Pi entry point: capture -> metadata JSON -> JPEG binary.

``--stream`` 실행 시 두 작업이 동시에 돈다.
- 촬영 작업: 설정 FPS로 카메라를 읽어 LatestFrameBuffer(대기 1개)에 넣는다. 덮어쓴 프레임은 폐기.
- 전송 작업: 버퍼의 최신 프레임을 인코딩·전송하고 ACK를 기다린다. 끊기면 백오프로 재접속.
원본 프레임과 JPEG는 메모리에서만 처리하고 저장하지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from edge.camera import BACKENDS, CameraError
from edge.config import load_config
from edge.frame_buffer import CapturedFrame, LatestFrameBuffer
from edge.frame_encoder import FrameEncoder
from edge.metrics import EdgeMetrics
from edge.websocket_client import (
    CONNECTION_ERRORS,
    DEFAULT_FRAME_ACK_TIMEOUT_SEC,
    FrameAckError,
    FrameWebSocketClient,
)
from shared.constants import MAX_FRAME_BYTES
from shared.types import now_ms

log = logging.getLogger("edge")

TOKEN_ENV = "EDGE_TOKEN"
SERVER_URL_ENV = "EDGE_SERVER_URL"
CAMERA_SOURCE_ENV = "EDGE_CAMERA_SOURCE"
CAMERA_FILE_ENV = "EDGE_CAMERA_FILE"
MAX_CONSECUTIVE_READ_FAILURES = 10  # 0.1초 간격 재시도 → 약 1초 후 카메라 재오픈
READ_RETRY_DELAY_SEC = 0.1
MAX_CONSECUTIVE_ACK_TIMEOUTS = 3  # 연속 ACK 시간 초과가 이만큼이면 연결을 새로 맺는다


def camera_settings(
    camera_cfg: dict[str, Any], source: str | None = None, file_path: str | None = None
) -> dict[str, Any]:
    """카메라 백엔드 우선순위: 인자(--source) > 환경변수 EDGE_CAMERA_SOURCE > 설정 camera.source > opencv.

    재생 파일(--file 또는 EDGE_CAMERA_FILE)을 지정하면 source를 따로 주지 않아도 ``file``로 본다.
    """
    settings = dict(camera_cfg)
    chosen_file = file_path or os.environ.get(CAMERA_FILE_ENV)
    if chosen_file:
        settings["file_path"] = chosen_file
    chosen = source or os.environ.get(CAMERA_SOURCE_ENV) or ("file" if chosen_file else None)
    if chosen:
        settings["source"] = chosen
    return settings


def check_camera(config_path: Path | None = None, source: str | None = None, file_path: str | None = None) -> None:
    from edge.camera import Camera

    config = camera_settings(load_config(config_path)["camera"], source, file_path)
    camera = Camera(**config)
    try:
        camera.open()
        frame = next(camera.frames(), None)
        if frame is None:
            raise CameraError("No camera frame received")
        print(f"Camera OK: {frame.shape[1]}x{frame.shape[0]}")
    finally:
        camera.close()


def resolve_edge_settings(edge_cfg: dict[str, Any]) -> dict[str, Any]:
    """환경변수(EDGE_TOKEN, EDGE_SERVER_URL)가 있으면 설정 파일 값보다 우선한다."""
    settings = dict(edge_cfg)
    settings["edge_token"] = os.environ.get(TOKEN_ENV) or settings.get("edge_token", "")
    settings["server_url"] = os.environ.get(SERVER_URL_ENV) or settings["server_url"]
    if not settings["edge_token"] or settings["edge_token"] == "CHANGE_ME":
        log.warning("edge_token is not set; set %s or edge.edge_token in edge/config.yaml", TOKEN_ENV)
    return settings


async def capture_loop(
    camera,
    buffer: LatestFrameBuffer,
    metrics: EdgeMetrics,
    fps: float,
    stop: asyncio.Event,
    *,
    max_read_failures: int = MAX_CONSECUTIVE_READ_FAILURES,
    retry_delay_sec: float = READ_RETRY_DELAY_SEC,
) -> None:
    """설정 FPS로 촬영한다. 일시적인 읽기 실패는 재시도하고, 계속 실패하면 카메라를 한 번 다시 연다.

    다시 열어도 읽히지 않으면 CameraError를 발생시킨다.
    """
    interval = 1.0 / fps if fps > 0 else 0.0
    next_at = time.perf_counter()
    failures, reopened = 0, False
    while not stop.is_set():
        image = await asyncio.to_thread(camera.read)
        if image is None:
            failures += 1
            if failures < max_read_failures:
                await asyncio.sleep(retry_delay_sec)
                continue
            if reopened:
                raise CameraError("camera frame read failed after reopening")
            log.warning("camera read failed %d times; reopening camera", failures)
            await asyncio.to_thread(camera.close)
            await asyncio.to_thread(camera.open)  # 열기 실패 시 CameraError 전파
            failures, reopened = 0, True
            next_at = time.perf_counter()
            continue
        failures, reopened = 0, False
        metrics.mark_captured()
        if buffer.put(CapturedFrame(image, now_ms(), time.perf_counter())):
            metrics.mark_dropped()
        next_at += interval
        delay = next_at - time.perf_counter()
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            next_at = time.perf_counter()  # 카메라가 느리면 일정을 다시 맞춘다


async def send_loop(
    client: FrameWebSocketClient,
    encoder: FrameEncoder,
    buffer: LatestFrameBuffer,
    metrics: EdgeMetrics,
    edge_cfg: dict[str, Any],
    camera_cfg: dict[str, Any],
    stop: asyncio.Event,
    *,
    max_ack_timeouts: int = MAX_CONSECUTIVE_ACK_TIMEOUTS,
) -> None:
    first_connect = True
    consecutive_timeouts = 0
    while not stop.is_set():
        if not client.connected:
            await client.connect_with_retry()
            if not first_connect:
                metrics.mark_reconnect()
            first_connect = False
            consecutive_timeouts = 0
        item = await buffer.get()
        started = time.perf_counter()
        metadata, jpeg = await asyncio.to_thread(
            encoder.encode,
            item.image,
            edge_id=edge_cfg["edge_id"],
            camera_id=edge_cfg["camera_id"],
            mirrored=bool(camera_cfg.get("mirrored", False)),
            rotation_deg=int(camera_cfg.get("rotation_deg", 0)),
            captured_at_ms=item.captured_at_ms,
        )
        metrics.mark_encoded(started)
        if len(jpeg) > MAX_FRAME_BYTES:
            log.warning("frame %s is %d bytes (> %d); dropped", metadata.frame_id, len(jpeg), MAX_FRAME_BYTES)
            metrics.mark_dropped()
            continue
        sent_at = time.perf_counter()
        try:
            ack = await client.send_frame(metadata, jpeg)
        except FrameAckError as exc:
            log.error("invalid ACK from server: %s", exc)
            metrics.mark_dropped()
            continue
        except TimeoutError:
            # 서버가 느린 것일 뿐 연결은 살아 있을 수 있으므로 바로 재접속하지 않는다.
            # 늦게 도착한 ACK는 다음 send_frame에서 건너뛴다. 끊긴 연결은 keepalive ping이 감지한다.
            metrics.mark_dropped()
            metrics.mark_ack_timeout()
            consecutive_timeouts += 1
            if consecutive_timeouts >= max_ack_timeouts:
                log.warning("%d consecutive ACK timeouts; reconnecting", consecutive_timeouts)
                await client.close()
            continue
        except CONNECTION_ERRORS as exc:
            log.warning("frame send failed (%s); reconnecting", type(exc).__name__)
            metrics.mark_dropped()
            await client.close()
            continue
        consecutive_timeouts = 0
        metrics.mark_sent()
        metrics.mark_ack(sent_at, ack.status, captured_at=item.captured_perf)
        if ack.status != "PROCESSED":
            log.debug("frame %s ACK status %s", ack.frame_id, ack.status)


async def report_loop(metrics: EdgeMetrics, interval_sec: float, stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.sleep(interval_sec)
        log.info("metrics %s", metrics.snapshot())


async def run_stream(
    camera,
    encoder: FrameEncoder,
    client: FrameWebSocketClient,
    metrics: EdgeMetrics,
    edge_cfg: dict[str, Any],
    camera_cfg: dict[str, Any],
    *,
    duration_sec: float | None = None,
    report_interval_sec: float = 10.0,
) -> EdgeMetrics:
    stop = asyncio.Event()
    buffer = LatestFrameBuffer()
    tasks = [
        asyncio.create_task(capture_loop(camera, buffer, metrics, float(camera_cfg.get("fps", 10)), stop)),
        asyncio.create_task(send_loop(client, encoder, buffer, metrics, edge_cfg, camera_cfg, stop)),
    ]
    if report_interval_sec > 0:
        tasks.append(asyncio.create_task(report_loop(metrics, report_interval_sec, stop)))
    try:
        done, _ = await asyncio.wait(tasks, timeout=duration_sec, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            task.result()  # 촬영 실패 등 예외를 호출자에게 전달
    finally:
        stop.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return metrics


async def stream_frames(
    config_path: Path | None = None,
    duration_sec: float | None = None,
    source: str | None = None,
    file_path: str | None = None,
) -> EdgeMetrics:
    from edge.camera import Camera

    config = load_config(config_path)
    camera_cfg, edge_cfg = camera_settings(config["camera"], source, file_path), resolve_edge_settings(config["edge"])
    camera, metrics = Camera(**camera_cfg), EdgeMetrics()
    log.info("camera source: %s", camera.source)
    encoder = FrameEncoder(camera_cfg["width"], camera_cfg["height"], camera_cfg["jpeg_quality"])
    client = FrameWebSocketClient(
        edge_cfg["server_url"],
        edge_cfg["edge_token"],
        edge_cfg["edge_id"],
        ack_timeout_sec=float(edge_cfg.get("ack_timeout_sec", DEFAULT_FRAME_ACK_TIMEOUT_SEC)),
    )
    try:
        camera.open()
        return await run_stream(camera, encoder, client, metrics, edge_cfg, camera_cfg, duration_sec=duration_sec)
    finally:
        await client.close()
        camera.close()
        log.info("final metrics %s", metrics.snapshot())


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudAIoT Raspberry Pi edge agent")
    parser.add_argument("--config", type=Path, help="설정 파일 경로 (기본: edge/config.yaml 또는 예제)")
    parser.add_argument("--check-camera", action="store_true", help="카메라 프레임 한 장을 읽어 확인")
    parser.add_argument("--stream", action="store_true", help="AI 서버로 프레임 스트리밍")
    parser.add_argument("--duration", type=float, help="스트리밍 시간(초). 지정하지 않으면 계속 실행")
    parser.add_argument("--source", choices=sorted(BACKENDS), help="카메라 백엔드 (설정 camera.source보다 우선)")
    parser.add_argument("--file", help="카메라 대신 반복 재생할 동영상·이미지 폴더·이미지 (source=file)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.check_camera:
        try:
            check_camera(args.config, args.source, args.file)
        except CameraError as exc:
            log.error("camera error: %s", exc)
            raise SystemExit(1) from None
    elif args.stream:
        try:
            asyncio.run(stream_frames(args.config, args.duration, args.source, args.file))
        except KeyboardInterrupt:
            pass
        except CameraError as exc:
            log.error("camera error: %s", exc)
            raise SystemExit(1) from None
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
