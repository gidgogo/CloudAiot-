"""Edge-to-AI WebSocket client: metadata JSON, then matching JPEG binary.

공통 인터페이스 v1 5장을 따른다.
- 인증: ``Authorization: Bearer {edge_token}``, ``X-Edge-ID`` 헤더
- 순서: 메타데이터 JSON → JPEG Binary → 서버 ACK
- 재접속: 1 → 2 → 4 → ... 최대 30초 지수 백오프
토큰과 영상은 로그에 남기지 않는다.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import websockets
from websockets.exceptions import InvalidHandshake, WebSocketException

from shared.constants import (
    EDGE_RECONNECT_DELAYS_SEC,
    FRAME_ACK_STATUSES,
    FRAME_ACK_TIMEOUT_MS,
    FRAME_WS_PATH,
    SCHEMA_VERSION,
)
from shared.types import FrameAck, FrameMetadata

log = logging.getLogger(__name__)

# 프레임 ACK 대기 시간 기본값. 장비별 조정은 edge 설정(edge.ack_timeout_sec)으로 한다.
# shared의 ACK_TIMEOUT_MS는 MQTT 기기 명령 ACK용이므로 쓰지 않는다.
DEFAULT_FRAME_ACK_TIMEOUT_SEC = FRAME_ACK_TIMEOUT_MS / 1000

ACK_STATUSES = FRAME_ACK_STATUSES
_ACK_FIELDS = frozenset(FrameAck.__dataclass_fields__) - {"schema_version"}

# 연결 실패/끊김으로 보고 재접속할 예외
CONNECTION_ERRORS: tuple[type[BaseException], ...] = (OSError, WebSocketException, asyncio.TimeoutError, ConnectionError)


class FrameAckError(ValueError):
    """서버 ACK가 규격에 맞지 않음."""


def parse_ack(raw: str | bytes) -> FrameAck:
    """서버 ACK JSON을 검증해 FrameAck로 변환한다."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise FrameAckError("frame ACK is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise FrameAckError("frame ACK must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise FrameAckError(f"unsupported ACK schema_version: {payload.get('schema_version')!r}")
    if payload.get("type") != "frame_ack":
        raise FrameAckError(f"unexpected message type: {payload.get('type')!r}")
    if payload.get("status") not in ACK_STATUSES:
        raise FrameAckError(f"unknown ACK status: {payload.get('status')!r}")
    if not isinstance(payload.get("frame_id"), str):
        raise FrameAckError("frame ACK has no frame_id")
    # schema_version은 FrameAck에서 init=False이므로 넘기지 않는다. 모르는 필드는 무시한다.
    return FrameAck(**{key: value for key, value in payload.items() if key in _ACK_FIELDS})


def backoff_delays(max_attempts: int | None = None):
    """1, 2, 4, 8, 16, 30, 30, ... 초. max_attempts가 None이면 무한히 생성한다."""
    attempt = 0
    while max_attempts is None or attempt < max_attempts:
        yield EDGE_RECONNECT_DELAYS_SEC[min(attempt, len(EDGE_RECONNECT_DELAYS_SEC) - 1)]
        attempt += 1


class FrameWebSocketClient:
    def __init__(
        self,
        server_url: str,
        edge_token: str,
        edge_id: str,
        *,
        ack_timeout_sec: float = DEFAULT_FRAME_ACK_TIMEOUT_SEC,
        open_timeout_sec: float = 5.0,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self.url = f"{server_url.rstrip('/')}{FRAME_WS_PATH}"
        self.headers = {"Authorization": f"Bearer {edge_token}", "X-Edge-ID": edge_id}
        self.ack_timeout_sec = ack_timeout_sec
        self.open_timeout_sec = open_timeout_sec
        self._sleep = sleep
        self._socket: Any | None = None

    @property
    def connected(self) -> bool:
        return self._socket is not None

    async def connect(self) -> None:
        await self._drop_socket()  # 기존 연결이 있으면 닫고 새로 맺는다
        self._socket = await websockets.connect(
            self.url,
            additional_headers=self.headers,
            max_size=None,
            open_timeout=self.open_timeout_sec,
        )
        log.info("connected to %s", self.url)

    async def send_frame(self, metadata: FrameMetadata, jpeg_bytes: bytes) -> FrameAck:
        """메타데이터와 JPEG를 보내고 같은 frame_id의 ACK를 기다린다.

        이전 프레임의 늦은 ACK(다른 frame_id)는 건너뛴다. ACK 대기 시간 초과 시
        TimeoutError(연결은 유지), 연결이 끊기면 websockets.ConnectionClosed가 발생한다.
        """
        if self._socket is None:
            raise ConnectionError("frame socket is not connected")
        await self._socket.send(json.dumps(metadata.as_dict()))
        await self._socket.send(jpeg_bytes)
        async with asyncio.timeout(self.ack_timeout_sec):
            while True:
                ack = parse_ack(await self._socket.recv())
                if ack.frame_id == metadata.frame_id:
                    return ack
                log.debug("ignoring stale ACK for frame %s", ack.frame_id)

    async def connect_with_retry(self, max_attempts: int | None = None) -> None:
        """연결될 때까지 지수 백오프로 재시도한다. 인증 거부(4xx 응답)도 재시도 대상이다."""
        last_error: BaseException | None = None
        for delay in backoff_delays(max_attempts):
            try:
                await self.connect()
                return
            except CONNECTION_ERRORS as exc:
                last_error = exc
                reason = "handshake rejected" if isinstance(exc, InvalidHandshake) else type(exc).__name__
                log.warning("connection to %s failed (%s); retrying in %ss", self.url, reason, delay)
                await self._sleep(delay)
        raise ConnectionError("unable to connect to AI server") from last_error

    async def reconnect(self) -> None:
        """공통 인터페이스 스켈레톤의 기존 메서드. 백오프 1회분(1~30초, 6번) 시도 후 실패하면 ConnectionError."""
        await self.connect_with_retry(max_attempts=len(EDGE_RECONNECT_DELAYS_SEC))

    async def _drop_socket(self) -> None:
        if self._socket is not None:
            try:
                await self._socket.close()
            except CONNECTION_ERRORS:
                pass
            self._socket = None

    async def close(self) -> None:
        await self._drop_socket()
