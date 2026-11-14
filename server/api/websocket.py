"""웹 대시보드 실시간 이벤트 WebSocket(``/ws/v1/events``, 규격 8.5).

연결 순서
1. Origin 허용 목록(또는 같은 출처) 검사 → 실패 4403
2. HttpOnly Cookie에서 JWT 추출, 서명·만료 검사 → 실패 4401
3. 사용자·역할 확인(제한 시간 초과 4408, 사용자 없음 4401)
4. 통과하면 이벤트 전송 시작

브라우저가 종료 코드를 받을 수 있도록 검사에 실패하면 연결을 수락한 직후 바로 닫는다.
검사를 통과하기 전에는 어떤 이벤트도 보내지 않는다.
로그인 만료 시각이 되면 4401로 닫는다. 클라이언트가 보낸 메시지는 무시한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.security.jwt import InvalidTokenError, check_origin, read_access_claims
from server.security.permissions import Principal
from server.services.user_service import UserService
from shared.constants import EVENT_TYPES, EVENT_WS_PATH
from shared.errors import InterfaceError
from shared.types import RealtimeEvent

router = APIRouter()
AUTH_TIMEOUT_SECONDS = 5.0


class _Reject(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _load_principal(app, user_id: str) -> Principal | None:
    with app.state.db.session() as session:
        return UserService(session).principal_for(user_id)


async def _authenticate(websocket: WebSocket) -> tuple[Principal, float]:
    """(로그인 사용자, 로그인 만료 Unix 초)를 돌려준다. 실패하면 종료 코드를 담은 _Reject."""
    settings = websocket.app.state.settings
    try:
        check_origin(websocket.headers, websocket.url.scheme, settings.allowed_origins, required=True)
    except InterfaceError as error:
        raise _Reject(CLOSE_FORBIDDEN) from error
    try:
        claims = read_access_claims(websocket.cookies, settings.jwt_secret)
    except InvalidTokenError as error:
        raise _Reject(CLOSE_UNAUTHORIZED) from error
    try:
        principal = await asyncio.wait_for(
            asyncio.to_thread(_load_principal, websocket.app, str(claims["sub"])), AUTH_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise _Reject(CLOSE_TIMEOUT) from error
    if principal is None:
        raise _Reject(CLOSE_UNAUTHORIZED)
    return principal, float(claims["exp"])


@router.websocket(EVENT_WS_PATH)
async def event_socket(websocket: WebSocket) -> None:
    try:
        principal, expires_at = await _authenticate(websocket)
    except _Reject as reject:
        await websocket.accept()
        await websocket.close(code=reject.code)
        return

    await websocket.accept()
    hub = websocket.app.state.events
    await hub.connect(websocket, principal)
    try:
        async with asyncio.timeout(max(0.0, expires_at - time.time())):
            while True:
                await websocket.receive_text()
    except TimeoutError:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(websocket)


# --- 웹 대시보드로 보내는 실시간 이벤트(``/ws/v1/events``) 허브.

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
        return audience_user_id is None or self.principal.can_view_user(audience_user_id)


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

    def publish(self, event_type: str, data: dict[str, Any], correlation_id: str = "",
                audience_user_id: str | None = None) -> RealtimeEvent:
        """``audience_user_id``를 주면 그 사용자를 볼 수 있는 연결에만 보낸다."""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type}")
        event = RealtimeEvent(event_type=event_type, correlation_id=correlation_id, data=data)
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:  # 리스너 오류가 요청 처리를 막지 않도록 한다.
                log.exception("event listener failed: %s", event_type)
        self._run(self._broadcast(json.dumps(event.as_dict(), ensure_ascii=False), audience_user_id))
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
            targets = [s for s in self._subscriptions.values() if s.principal.user_id == user_id]
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
            targets = [s for s in self._subscriptions.values() if s.accepts(audience_user_id)]
        results = await asyncio.gather(*(s.websocket.send_text(text) for s in targets), return_exceptions=True)
        for subscription, result in zip(targets, results):
            if isinstance(result, Exception):
                self.disconnect(subscription.websocket)

    @staticmethod
    async def _close(websocket: WebSocket, code: int) -> None:
        try:
            await websocket.close(code=code)
        except Exception:
            pass
