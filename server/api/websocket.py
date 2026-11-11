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
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.security.csrf import check_origin
from server.security.jwt import InvalidTokenError, read_access_claims
from server.security.permissions import Principal
from server.services.events import CLOSE_FORBIDDEN, CLOSE_TIMEOUT, CLOSE_UNAUTHORIZED
from server.services.user_service import UserService
from shared.constants import EVENT_WS_PATH
from shared.errors import InterfaceError

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
        check_origin(
            websocket.headers,
            websocket.url.scheme,
            settings.allowed_origins,
            required=True,
        )
    except InterfaceError as error:
        raise _Reject(CLOSE_FORBIDDEN) from error
    try:
        claims = read_access_claims(websocket.cookies, settings.jwt_secret)
    except InvalidTokenError as error:
        raise _Reject(CLOSE_UNAUTHORIZED) from error
    try:
        principal = await asyncio.wait_for(
            asyncio.to_thread(_load_principal, websocket.app, str(claims["sub"])),
            AUTH_TIMEOUT_SECONDS,
        )
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
