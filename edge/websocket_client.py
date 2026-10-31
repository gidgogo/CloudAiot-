"""Edge-to-AI WebSocket client: metadata JSON, then matching JPEG binary."""
from __future__ import annotations
import asyncio, json
from typing import Any
import websockets
from shared.constants import EDGE_RECONNECT_DELAYS_SEC, FRAME_WS_PATH
from shared.types import FrameAck, FrameMetadata

class FrameWebSocketClient:
    def __init__(self, server_url: str, edge_token: str, edge_id: str) -> None:
        self.url = f"{server_url.rstrip('/')}{FRAME_WS_PATH}"
        self.headers = {"Authorization": f"Bearer {edge_token}", "X-Edge-ID": edge_id}
        self._socket: Any | None = None
    async def connect(self) -> None:
        self._socket = await websockets.connect(self.url, additional_headers=self.headers, max_size=None)
    async def send_frame(self, metadata: FrameMetadata, jpeg_bytes: bytes) -> FrameAck:
        if self._socket is None: raise ConnectionError("frame socket is not connected")
        await self._socket.send(json.dumps(metadata.as_dict()))
        await self._socket.send(jpeg_bytes)
        payload = json.loads(await self._socket.recv())
        if payload.get("frame_id") != metadata.frame_id: raise ValueError("frame ACK does not match frame_id")
        return FrameAck(**payload)
    async def reconnect(self) -> None:
        for delay in EDGE_RECONNECT_DELAYS_SEC:
            try:
                await self.connect(); return
            except OSError: await asyncio.sleep(delay)
        raise ConnectionError("unable to reconnect to AI server")
    async def close(self) -> None:
        if self._socket is not None:
            await self._socket.close(); self._socket = None
