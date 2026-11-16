"""Edge 개발용 Mock AI 프레임 서버 (공통 인터페이스 v1 5장).

AI 서버의 /ws/v1/frames가 준비되기 전에 Edge 전송을 확인하기 위한 도구이다.
메타데이터 JSON → JPEG Binary 순서와 인증 헤더를 검사하고 frame_ack를 돌려준다.
받은 영상은 저장하지 않는다.

    python -m edge.dev.mock_frame_server --port 8000 --token dev-token
    EDGE_TOKEN=dev-token python -m edge.main --stream --source synthetic
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Request, Response

from shared.constants import FRAME_WS_PATH, MAX_FRAME_BYTES, SCHEMA_VERSION

log = logging.getLogger("mock_frame_server")
JPEG_SOI = b"\xff\xd8"


def now_ms() -> int:
    return int(time.time() * 1000)


def ack(frame_id: str, status: str, received_at_ms: int) -> str:
    processed = now_ms()
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "type": "frame_ack",
        "frame_id": frame_id,
        "status": status,
        "received_at_ms": received_at_ms,
        "processed_at_ms": processed,
        "processing_time_ms": max(0, processed - received_at_ms),
    })


def make_server_handlers(token: str | None, processing_delay_ms: int = 0, stats: dict | None = None):
    stats = stats if stats is not None else {}

    def process_request(connection: ServerConnection, request: Request) -> Response | None:
        if request.path != FRAME_WS_PATH:
            return connection.respond(404, "unknown path\n")
        if token is not None and request.headers.get("Authorization") != f"Bearer {token}":
            return connection.respond(401, "invalid edge token\n")
        if not request.headers.get("X-Edge-ID"):
            return connection.respond(400, "missing X-Edge-ID\n")
        return None

    async def handler(connection: ServerConnection) -> None:
        edge_id = connection.request.headers.get("X-Edge-ID")
        log.info("edge connected: %s", edge_id)
        stats["connections"] = stats.get("connections", 0) + 1
        pending: dict | None = None
        try:
            async for message in connection:
                received = now_ms()
                if isinstance(message, str):
                    if pending is not None:  # Binary 없이 다음 메타데이터 → 이전 프레임 폐기
                        await connection.send(ack(pending["frame_id"], "INVALID", received))
                    try:
                        pending = json.loads(message)
                        assert pending.get("schema_version") == SCHEMA_VERSION and pending.get("type") == "frame_metadata"
                        assert isinstance(pending.get("frame_id"), str)
                    except (ValueError, AssertionError):
                        log.warning("invalid metadata")
                        pending = None
                    continue
                if pending is None:
                    log.warning("binary without metadata; ignored")
                    continue
                frame_id = pending["frame_id"]
                pending = None
                if not message.startswith(JPEG_SOI) or len(message) > MAX_FRAME_BYTES:
                    await connection.send(ack(frame_id, "INVALID", received))
                    stats["invalid"] = stats.get("invalid", 0) + 1
                    continue
                if processing_delay_ms:
                    await asyncio.sleep(processing_delay_ms / 1000)
                await connection.send(ack(frame_id, "PROCESSED", received))
                stats["frames"] = stats.get("frames", 0) + 1
                stats["bytes"] = stats.get("bytes", 0) + len(message)
                if stats["frames"] % 50 == 0:
                    log.info("received %d frames (%.1f KB avg)", stats["frames"], stats["bytes"] / stats["frames"] / 1024)
        finally:
            log.info("edge disconnected: %s", edge_id)

    return process_request, handler


async def run(host: str, port: int, token: str | None, processing_delay_ms: int) -> None:
    process_request, handler = make_server_handlers(token, processing_delay_ms)
    async with serve(handler, host, port, process_request=process_request, max_size=MAX_FRAME_BYTES + 1):
        log.info("mock frame server on ws://%s:%d%s", host, port, FRAME_WS_PATH)
        await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", help="허용할 edge 토큰. 생략하면 인증을 검사하지 않음")
    parser.add_argument("--delay-ms", type=int, default=0, help="AI 처리 시간 흉내(ms)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(run(args.host, args.port, args.token, args.delay_ms))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
