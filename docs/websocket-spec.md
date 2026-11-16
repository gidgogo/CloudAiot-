# WebSocket 명세

영상 전송과 실시간 이벤트 규격을 기록한다.

- 기준 문서: [공통 인터페이스 규격 v1.0](interfaces/common-interface-spec-v1.0.md) 5장(Edge–AI), 8.5장·9장(웹 실시간 이벤트)
- 이 문서는 공통 규격을 **현재 구현 기준으로 자세히 풀어 쓴 것**이다. 공통 규격과 다르면 공통 규격을 따른다.
- 공통 규격에 없고 구현에서 정한 값은 **[구현값]**으로 표시한다. 팀 합의 전까지는 바뀔 수 있다.

---

## 1. 영상 프레임 전송 (Edge → AI 서버)

### 1.1 연결

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 프로토콜 | WebSocket (텍스트 + 바이너리 메시지) | 규격 5.1 |
| 경로 | `/ws/v1/frames` (`shared.constants.FRAME_WS_PATH`) | 규격 5.1 |
| 개발 주소 | `ws://{server}:8000/ws/v1/frames` | 규격 5.1 |
| 운영 주소 | `wss://{domain}/ws/v1/frames` (외부망은 TLS 필수) | 규격 5.1, SAD |
| 연결 수 | Edge 1대당 소켓 1개 | 구현 |
| 연결 열기 제한 시간 | 5초 | [구현값] `open_timeout_sec` |

**핸드셰이크 헤더** (규격 5.2)

```
Authorization: Bearer {edge_token}
X-Edge-ID: raspberrypi-01
```

- `edge_token`은 코드에 쓰지 않는다. 환경변수 `EDGE_TOKEN` → `edge/config.yaml`의 `edge.edge_token` 순서로 읽는다.
- 토큰과 영상은 로그에 남기지 않는다.

**핸드셰이크 거부 응답** — 현재 Mock 서버(`edge/dev/mock_frame_server.py`) 동작이며, 실제 서버도 이대로 맞추는 것을 제안한다.

| 상황 | HTTP 응답 |
| --- | --- |
| 경로가 `/ws/v1/frames`가 아님 | `404` |
| 토큰 불일치 | `401` |
| `X-Edge-ID` 없음 | `400` |

Edge는 거부 응답도 연결 실패로 보고 재접속 백오프(1.6절)를 적용한다.

### 1.2 메시지 순서 (규격 5.3)

```
Edge ──(텍스트) frame_metadata JSON──▶ AI
Edge ──(바이너리) JPEG bytes ────────▶ AI
Edge ◀─(텍스트) frame_ack JSON ─────── AI
```

- WebSocket은 순서를 보장하므로, 메타데이터 다음에 오는 바이너리 메시지를 그 `frame_id`의 영상으로 본다.
- **Stop-and-wait**: Edge는 ACK를 받거나 대기 시간이 지나야 다음 프레임을 보낸다. 동시에 전송 중인 프레임은 최대 1개다. [구현값]
- 메타데이터 다음에 바이너리 없이 다시 메타데이터가 오면, 서버는 이전 프레임을 폐기하고 `INVALID` ACK를 보낸다. (Mock 동작)
- 메타데이터 없이 바이너리만 오면 서버는 무시한다. (Mock 동작)

### 1.3 프레임 메타데이터 (텍스트 메시지, 규격 5.4)

```json
{
  "schema_version": "1.0",
  "type": "frame_metadata",
  "frame_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "edge_id": "raspberrypi-01",
  "camera_id": "camera-01",
  "captured_at_ms": 1793430000000,
  "width": 640,
  "height": 480,
  "format": "jpeg",
  "jpeg_quality": 95,
  "mirrored": false,
  "rotation_deg": 0
}
```

| 필드 | 타입 | 제약 | 값의 출처 |
| --- | --- | --- | --- |
| `schema_version` | string | `"1.0"` 고정 | `shared.constants.SCHEMA_VERSION` |
| `type` | string | `"frame_metadata"` 고정 | |
| `frame_id` | string | UUID v4, 프레임마다 새로 생성 | Edge |
| `correlation_id` | string | UUID v4. 기본값은 `frame_id`와 같음 | Edge. 이후 인식·의도·명령까지 이어지는 추적 ID |
| `edge_id` | string | 비어 있으면 안 됨. `X-Edge-ID`와 같아야 함 | `edge.edge_id` |
| `camera_id` | string | 비어 있으면 안 됨 | `edge.camera_id` |
| `captured_at_ms` | integer | UTC Unix ms, ≥ 0 | **카메라에서 읽은 시각** (인코딩 시각 아님) |
| `width` | integer | ≥ 1. JPEG의 실제 가로 크기 | `camera.width` |
| `height` | integer | ≥ 1. JPEG의 실제 세로 크기 | `camera.height` |
| `format` | string | `"jpeg"` 고정 | |
| `jpeg_quality` | integer | 1–100 | `camera.jpeg_quality` |
| `mirrored` | boolean | | `camera.mirrored` |
| `rotation_deg` | integer | `0`, `90`, `180`, `270` 중 하나 | `camera.rotation_deg` |

- 정의된 필드 외에는 보내지 않는다 (규격 14장 2번).
- `mirrored`, `rotation_deg`는 **정보로만 전달**한다. Edge는 영상을 뒤집거나 돌리지 않고, AI 서버가 좌표 해석 시 반영한다 (규격 4.4).
- 검증 기준: `shared/types.py`의 `FrameMetadata`, `shared/schemas/frame-metadata.schema.json`

### 1.4 JPEG 바이너리 (바이너리 메시지)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 형식 | 베이스라인 JPEG (OpenCV `cv2.imencode(".jpg")`), BGR 원본에서 인코딩 | 구현 |
| 시작 바이트 | `FF D8` (JPEG SOI) | Mock 서버 검사 |
| 해상도 | 메타데이터의 `width × height`. 카메라 출력이 다르면 Edge가 `INTER_AREA`로 크기를 맞춘 뒤 인코딩 | 규격 5.1 |
| 최대 크기 | **2,000,000 bytes** (`MAX_FRAME_BYTES`) | [구현값] |
| 인코딩 | 원본 바이트 그대로. base64를 쓰지 않음 | 구현 |

- Edge는 인코딩 결과가 최대 크기를 넘으면 보내지 않고 폐기한다.
- 서버는 SOI가 없거나 최대 크기를 넘으면 `INVALID` ACK를 보낸다.
- 원본 영상과 JPEG는 메모리에서만 처리하고 디스크·DB에 저장하지 않는다 (규격 5.6, NFR-03).

### 1.5 서버 ACK (텍스트 메시지, 규격 5.5)

```json
{
  "schema_version": "1.0",
  "type": "frame_ack",
  "frame_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "status": "PROCESSED",
  "received_at_ms": 1793430000030,
  "processed_at_ms": 1793430000080,
  "processing_time_ms": 50
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `schema_version` | string | `"1.0"`. 다르면 Edge는 ACK를 거부한다 |
| `type` | string | `"frame_ack"` |
| `frame_id` | string | 응답 대상 프레임의 `frame_id` |
| `status` | string | 아래 표 중 하나 |
| `received_at_ms` | integer | 서버가 바이너리를 받은 시각 (UTC ms) |
| `processed_at_ms` | integer | 처리를 마친 시각 (UTC ms) |
| `processing_time_ms` | integer | `processed_at_ms - received_at_ms` |

| `status` | 의미 | Edge 동작 |
| --- | --- | --- |
| `PROCESSED` | 정상 처리 | 전송 성공으로 집계 |
| `DROPPED` | 서버 부하 등으로 폐기 | 다음 프레임 전송 |
| `INVALID` | 메타데이터·JPEG 형식 오류 | 다음 프레임 전송 |
| `ERROR` | 서버 내부 오류 | 다음 프레임 전송 |

- Edge는 모르는 필드는 무시한다. 다만 `schema_version`, `type`, `status`, `frame_id` 중 하나라도 맞지 않으면 잘못된 ACK로 보고 그 프레임을 폐기한다.
- 보낸 `frame_id`와 다른 ACK(이전 프레임에 늦게 온 ACK)는 건너뛰고 계속 기다린다.

### 1.6 타이밍과 흐름 제어 (규격 5.6)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 촬영 FPS | 10 (`camera.fps`) | 규격 5.1 |
| 전송 대기 버퍼 | 최신 프레임 1개 (`MAX_PENDING_FRAMES = 1`). 새 프레임이 오면 대기 중인 프레임은 폐기 | 규격 5.6 |
| ACK 대기 시간 | 2.0초 (`shared.constants.FRAME_ACK_TIMEOUT_MS`, 장비별로 `edge.ack_timeout_sec`) | [구현값, shared 반영·합의 대기] |
| ACK 시간 초과 시 | 그 프레임은 폐기하고 연결은 유지 | [구현값] |
| 연속 ACK 시간 초과 | 3회 연속이면 연결을 닫고 다시 접속 | [구현값] |
| 재접속 백오프 | 1 → 2 → 4 → 8 → 16 → 30 → 30 … 초 (`EDGE_RECONNECT_DELAYS_SEC`) | 규격 5.6 |
| 끊김 감지 | websockets 라이브러리 기본 keepalive ping | 구현 |

실제 전송 FPS는 `min(촬영 FPS, 1 / (인코딩 + 왕복 + 서버 처리 시간))`이다. 서버 처리가 100ms보다 오래 걸리면 10 FPS가 나오지 않고, 그만큼 Edge 버퍼에서 프레임이 폐기된다.

### 1.7 설정값

`edge/config.example.yaml`을 `edge/config.yaml`로 복사해 수정한다. 코드는 바꾸지 않는다 (규격 5.1).

```yaml
camera:
  source: opencv        # opencv | picamera2 | synthetic
  device_index: 0
  width: 640
  height: 480
  fps: 10
  jpeg_quality: 95
  mirrored: false
  rotation_deg: 0
edge:
  edge_id: raspberrypi-01
  camera_id: camera-01
  server_url: ws://localhost:8000   # 경로(/ws/v1/frames)는 자동으로 붙음
  edge_token: CHANGE_ME
  ack_timeout_sec: 2.0
```

| 환경변수 | 덮어쓰는 설정 |
| --- | --- |
| `EDGE_TOKEN` | `edge.edge_token` |
| `EDGE_SERVER_URL` | `edge.server_url` |
| `EDGE_CAMERA_SOURCE` | `camera.source` (CLI `--source`가 더 우선) |

### 1.8 AI 서버 수신부가 지켜야 할 것

1. 핸드셰이크에서 `Authorization`과 `X-Edge-ID`를 검사하고, 실패하면 1.1절의 HTTP 응답으로 거부한다.
2. 메타데이터를 쓰기 전에 `schema_version`, `type`, 필드 제약(1.3절)을 검사한다.
3. 바이너리마다 직전 메타데이터와 짝을 맞추고, SOI와 최대 크기를 검사한다.
4. 처리한 모든 프레임에 같은 `frame_id`로 ACK를 1개 보낸다. 형식 오류여도 `frame_id`를 알면 `INVALID`를 보낸다.
5. 처리가 밀리면 오래된 프레임보다 최신 프레임을 우선하고, 버린 프레임에는 `DROPPED`를 보낸다.
6. 수신 최대 메시지 크기를 `MAX_FRAME_BYTES`보다 크게 잡는다 (Mock은 `MAX_FRAME_BYTES + 1`).
7. 영상은 메모리에서만 처리하고 로그·디스크·DB에 남기지 않는다.

서버 수신부를 개발할 때는 Pi 없이 Edge 코드로 더미 프레임을 보낼 수 있다 (`edge/README.md`의 "협업용 더미 송출").

```bash
EDGE_TOKEN=dev-token python -m edge.main --stream --file edge/tests/손동작영상.mp4   # 또는 --source synthetic / opencv
```

반대로 Edge를 개발할 때는 Mock 서버로 Edge 동작을 확인할 수 있다.

```bash
python -m edge.dev.mock_frame_server --port 8000 --token dev-token --delay-ms 50
EDGE_TOKEN=dev-token python -m edge.main --stream --source synthetic
```

### 1.9 현재 상태와 미결정 사항

- **서버 수신부 미구현**: `server/`에는 `/ws/v1/frames` 라우터가 아직 없다. 지금 동작하는 상대는 Mock 서버뿐이다.
- **해상도·FPS·품질은 임시 기본값**: 공통 규격 5.1과 SAD v1.0 미결정 사항에 따라, 실제 Raspberry Pi에서 전송량·지연·인식 성공률을 측정한 뒤 확정한다.
- **공유 스키마 갱신 (합의 대기)**: `shared/schemas/frame-metadata.schema.json`을 규격 5.4의 13개 필드로 고치고(`captured_at` → `captured_at_ms`), `frame-ack.schema.json`(5.5)을 새로 추가했다. `shared/constants.py`에는 `FRAME_ACK_TIMEOUT_MS`와 `FRAME_ACK_STATUSES`를 추가했다. 규격 14장에 따라 서버·통합 담당의 Issue 합의 후 병합한다. 스키마 위치를 규격 13장의 `shared/schemas/v1/`로 옮기는 것은 다른 스키마와 함께 별도로 정한다.
- **[구현값] 항목 합의 필요**: 최대 프레임 크기 2MB, ACK 대기 2초, 연속 시간 초과 3회, 핸드셰이크 거부 HTTP 코드는 공통 규격에 없다. 서버 담당과 합의한 뒤 공통 규격에 넣을지 결정한다.

---

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
