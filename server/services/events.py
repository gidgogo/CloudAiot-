"""웹 대시보드로 보내는 실시간 이벤트(``/ws/v1/events``) 허브.

- 서비스 계층은 동기 코드(스레드풀)에서 ``publish``를 호출하고,
  허브가 WebSocket 연결이 속한 이벤트 루프로 전송을 넘긴다.
- 연결마다 로그인 사용자(Principal)를 기억한다. 특정 사용자에 관한 이벤트
  (``audience_user_id``, 예: 도움 요청)는 그 사용자를 볼 수 있는 연결에만 보낸다.
- 로그인 만료는 연결 쪽(``api/websocket.py``)이 처리한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from starlette.websockets import WebSocket

from server.security.permissions import Principal
from shared.constants import EVENT_TYPES
from shared.types import RealtimeEvent

log = logging.getLogger(__name__)

Listener = Callable[[RealtimeEvent], None]
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_TIMEOUT = 4408


@dataclass
class Subscription:
    websocket: WebSocket
    principal: Principal

    def accepts(self, audience_user_id: str | None) -> bool:
        return audience_user_id is None or self.principal.can_view_user(
            audience_user_id
        )


class EventHub:
    def __init__(self) -> None:
        self._subscriptions: dict[int, Subscription] = {}
        self._listeners: list[Listener] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    @property
    def client_count(self) -> int:
        return len(self._subscriptions)

    async def connect(self, websocket: WebSocket, principal: Principal) -> None:
        self._loop = asyncio.get_running_loop()
        with self._lock:
            self._subscriptions[id(websocket)] = Subscription(websocket, principal)

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._subscriptions.pop(id(websocket), None)

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """같은 프로세스 안에서 이벤트를 받는다(테스트·다른 모듈 연동용)."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        correlation_id: str = "",
        audience_user_id: str | None = None,
    ) -> RealtimeEvent:
        """``audience_user_id``를 주면 그 사용자를 볼 수 있는 연결에만 보낸다."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")
        event = RealtimeEvent(
            event_type=event_type, correlation_id=correlation_id, data=data
        )
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:  # 리스너 오류가 요청 처리를 막지 않도록 한다.
                log.exception("event listener failed: %s", event_type)
        self._run(
            self._broadcast(
                json.dumps(event.as_dict(), ensure_ascii=False), audience_user_id
            )
        )
        return event

    def update_principal(self, user_id: str, principal: Principal) -> None:
        """보호자 연결이 바뀌면 열려 있는 연결의 열람 범위도 바꾼다."""
        with self._lock:
            for subscription in self._subscriptions.values():
                if subscription.principal.user_id == user_id:
                    subscription.principal = principal

    def close_user(self, user_id: str, code: int = CLOSE_UNAUTHORIZED) -> None:
        """계정이 삭제되거나 역할이 바뀐 사용자의 연결을 닫는다."""
        with self._lock:
            targets = [
                s
                for s in self._subscriptions.values()
                if s.principal.user_id == user_id
            ]
        for subscription in targets:
            self.disconnect(subscription.websocket)
            self._run(self._close(subscription.websocket, code))

    def _run(self, coroutine: Coroutine[Any, Any, None]) -> None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._subscriptions:
            coroutine.close()
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(coroutine)
        else:
            asyncio.run_coroutine_threadsafe(coroutine, loop)

    async def _broadcast(self, text: str, audience_user_id: str | None) -> None:
        with self._lock:
            targets = [
                s for s in self._subscriptions.values() if s.accepts(audience_user_id)
            ]
        results = await asyncio.gather(
            *(s.websocket.send_text(text) for s in targets), return_exceptions=True
        )
        for subscription, result in zip(targets, results):
            if isinstance(result, Exception):
                self.disconnect(subscription.websocket)

    @staticmethod
    async def _close(websocket: WebSocket, code: int) -> None:
        try:
            await websocket.close(code=code)
        except Exception:
            pass
