"""Authenticated Edge frame WebSocket: metadata JSON → JPEG binary → frame ACK."""

from __future__ import annotations

import asyncio
import json
import logging
from time import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from shared.constants import FRAME_WS_PATH, MAX_FRAME_BYTES, SCHEMA_VERSION
from shared.types import FrameMetadata

router = APIRouter()
log = logging.getLogger(__name__)
JPEG_SOI = b"\xff\xd8"
_FIELDS = frozenset(FrameMetadata.__dataclass_fields__)
_INTEGER_FIELDS = ("captured_at_ms", "width", "height", "jpeg_quality", "rotation_deg")


def _now_ms() -> int:
    return int(time() * 1000)


def parse_metadata(raw: str, expected_edge_id: str) -> FrameMetadata:
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("frame metadata is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ValueError("frame metadata fields do not match v1")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("type") != "frame_metadata":
        raise ValueError("unsupported frame metadata schema or type")
    for name in ("frame_id", "correlation_id", "edge_id", "camera_id"):
        if not isinstance(payload.get(name), str) or not payload[name]:
            raise ValueError(f"invalid {name}")
    if payload["edge_id"] != expected_edge_id:
        raise ValueError("edge_id does not match X-Edge-ID")
    for name in _INTEGER_FIELDS:
        if isinstance(payload.get(name), bool) or not isinstance(payload.get(name), int):
            raise ValueError(f"invalid {name}")
    if not isinstance(payload.get("mirrored"), bool) or payload.get("format") != "jpeg":
        raise ValueError("invalid frame format or mirrored")
    values = {key: value for key, value in payload.items() if key != "schema_version"}
    return FrameMetadata(**values)


def frame_ack(frame_id: str, status: str, received_at_ms: int) -> dict[str, Any]:
    processed_at_ms = _now_ms()
    return {
        "schema_version": SCHEMA_VERSION,
        "type": "frame_ack",
        "frame_id": frame_id,
        "status": status,
        "received_at_ms": received_at_ms,
        "processed_at_ms": processed_at_ms,
        "processing_time_ms": max(0, processed_at_ms - received_at_ms),
    }


def _recover_frame_id(raw: str) -> str | None:
    """Recover only the identifier needed to return INVALID; never use other invalid fields."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    frame_id = payload.get("frame_id") if isinstance(payload, dict) else None
    return frame_id if isinstance(frame_id, str) and frame_id else None


async def _send_ack(websocket: WebSocket, frame_id: str, status: str, received_at_ms: int) -> None:
    await websocket.send_json(frame_ack(frame_id, status, received_at_ms))


@router.websocket(FRAME_WS_PATH)
async def frame_socket(websocket: WebSocket) -> None:
    settings = websocket.app.state.settings
    edge_id = websocket.headers.get("X-Edge-ID", "")
    authorization = websocket.headers.get("Authorization", "")
    if not settings.edge_token or authorization != f"Bearer {settings.edge_token}" or not edge_id:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        processor = await asyncio.to_thread(websocket.app.state.frame_processor_factory)
    except Exception:
        log.exception("failed to initialize frame processor edge_id=%s", edge_id)
        await websocket.close(code=1011)
        return
    websocket.app.state.events.publish("edge.connected", {"edge_id": edge_id})
    pending: FrameMetadata | None = None
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.1)
            except TimeoutError:
                await asyncio.to_thread(processor.tick)
                continue
            received_at_ms = _now_ms()
            if message.get("type") == "websocket.disconnect":
                break
            text = message.get("text")
            binary = message.get("bytes")
            if text is not None:
                if pending is not None:
                    await _send_ack(websocket, pending.frame_id, "INVALID", received_at_ms)
                    pending = None
                try:
                    pending = parse_metadata(text, edge_id)
                except ValueError:
                    log.warning("invalid frame metadata from edge_id=%s", edge_id)
                    frame_id = _recover_frame_id(text)
                    if frame_id is not None:
                        await _send_ack(websocket, frame_id, "INVALID", received_at_ms)
                continue
            if binary is None or pending is None:
                continue
            metadata, pending = pending, None
            if len(binary) > MAX_FRAME_BYTES or not binary.startswith(JPEG_SOI):
                await _send_ack(websocket, metadata.frame_id, "INVALID", received_at_ms)
                continue
            try:
                await asyncio.to_thread(processor.process, binary, metadata)
            except ValueError:
                log.warning("invalid JPEG frame edge_id=%s frame_id=%s", edge_id, metadata.frame_id)
                await _send_ack(websocket, metadata.frame_id, "INVALID", received_at_ms)
            except Exception:
                log.exception("frame processing failed edge_id=%s frame_id=%s", edge_id, metadata.frame_id)
                await _send_ack(websocket, metadata.frame_id, "ERROR", received_at_ms)
            else:
                await _send_ack(websocket, metadata.frame_id, "PROCESSED", received_at_ms)
    except WebSocketDisconnect:
        pass
    finally:
        await asyncio.to_thread(processor.close)
        websocket.app.state.events.publish("edge.disconnected", {"edge_id": edge_id})
