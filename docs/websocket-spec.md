## 2. 웹 실시간 이벤트 (`/ws/v1/events`)

서버가 웹 대시보드로 보내는 단방향 채널이다. 클라이언트가 보낸 메시지는 무시한다.
기준: [공통 인터페이스 규격 v1.0](interfaces/common-interface-spec-v1.0.md) 8.5장(WebSocket 인증), 9장(이벤트).
구현: `server/api/websocket.py`(연결·인증), `server/services/events.py`(EventHub).

### 2.1 연결과 인증 (규격 8.5)

| 순서 | 검사 | 실패 시 종료 코드 |
| --- | --- | --- |
| 1 | `Origin`이 `ALLOWED_ORIGINS` 또는 같은 출처인지(헤더 필수) | 4403 |
| 2 | HttpOnly Cookie `aiot_access_token`의 JWT 서명·만료 | 4401 |
| 3 | JWT의 사용자 확인(5초 안에 끝나지 않으면 4408) | 4401 / 4408 |
| - | 로그인 만료 시각 도달 | 4401 |
| - | 관리자가 계정 삭제·역할 변경 | 4401 |

브라우저가 종료 코드를 받을 수 있도록 검사에 실패하면 연결을 수락한 직후 바로 닫는다.
검사를 통과하기 전에는 어떤 이벤트도 보내지 않는다.

웹(`web/src/websocket/eventClient.ts`)은 끊기면 1·2·4·8·16·30초 간격으로 다시 연결하고,
4401·4403을 받으면 다시 연결하지 않고 로그인 화면으로 돌아간다.

### 2.2 Envelope (규격 9.1)

```json
{
  "schema_version": "1.0",
  "event_id": "68069bdd-b523-4702-b960-c0257886d358",
  "event_type": "help.created",
  "correlation_id": "e17d8451-b94c-48e8-bc60-dc57893d5247",
  "timestamp_ms": 1793430000100,
  "data": {}
}
```

### 2.3 받는 범위

- `help.*`: 그 요청을 볼 수 있는 사용자에게만 보낸다(`audience_user_id`). USER는 본인, GUARDIAN은 연결된 사용자, ADMIN은 전체.
  보호자 연결이 바뀌거나 연결된 사용자가 삭제·역할 변경되면 열려 있는 연결에도 바로 반영된다.
- 그 밖의 이벤트: 로그인한 모든 사용자에게 보낸다.

### 2.4 웹 서버가 보내는 이벤트

| 이벤트 | 보내는 시점 | `data` |
| --- | --- | --- |
| `help.created` | 도움 요청 생성 | `request_id`, `user_id`, `status` |
| `help.updated` | 도움 요청 상태 변경 | `request_id`, `user_id`, `status` |
| `device.state_changed` | 기기 `state` 또는 `connection_status`가 실제로 바뀜 | `device_id`, `state`, `connection_status`, `updated_at_ms` |
| `command.created` | 제어 명령 기록 | `command_id`, `device_id`, `action`, `status`, `result`, `error_code`, `latency_ms` |
| `command.completed` | 성공 ACK 수신 | 위와 같음 |
| `command.failed` | 실패 ACK 또는 ACK 제한시간 초과 | 위와 같음 |

`help.*`의 `data`는 규격 10.3과 같다. `device.state_changed`와 `command.*`의 `data`는 규격에 정의되지 않아
웹 서버가 정한 형식이며, 공통 규격에 올릴지 통합 담당자와 합의한다.

### 2.5 다른 모듈이 보내는 이벤트

`edge.connected`, `edge.disconnected`, `device.selected`, `gesture.confirmed`는 엣지·AI 모듈이 보낸다.
웹은 다음 필드를 사용한다.

| 이벤트 | 웹이 쓰는 `data` | 화면 |
| --- | --- | --- |
| `edge.connected` / `edge.disconnected` | 없음 | 대시보드 "카메라" 상태 |
| `device.selected` | `device_id` (규격 9.3) | 배치도·기기 카드에 6초간 "선택됨" 표시 |
| `gesture.confirmed` | 없음 | 실시간 활동 목록 |

```python
hub = app.state.events  # server.services.events.EventHub
hub.publish("device.selected", {"device_id": "fan-01", "device_name": "선풍기"}, correlation_id=frame_id)
# 특정 사용자에 관한 이벤트는 그 사용자를 볼 수 있는 연결에만 보낸다.
hub.publish("help.created", data, correlation_id=cid, audience_user_id="user-01")
```

`publish`는 동기 코드(스레드풀)와 비동기 코드 어디서나 호출할 수 있다. 정의되지 않은 `event_type`은 `ValueError`다.
