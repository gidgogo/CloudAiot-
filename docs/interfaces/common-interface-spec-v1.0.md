# CloudAIoT 공통 인터페이스 규격 v1.0

> 본 문서는 팀 개발 및 AI 도구 사용 시 기준으로 삼아야 하는 공식 인터페이스 레퍼런스이다.

## 1. 목적

본 문서는 CloudAIoT 프로젝트에서 다음 모듈이 공통으로 따라야 하는 인터페이스 규격을 정의한다.

- Edge–AI 영상 전송
- AI "담당 A – AI" / "담당 B 인식 결과 전달"
- AI –웹 REST API 및 실시간 이벤트
- AI–MQTT–ESP32 기기 제어
- 도움 요청 처리
- 공통 인증·오류·버전 관리

모든 담당자는 본 규격에 정의된 필드명, 자료형, 상태값, Topic 및 API 경로를 사용해야 한다. 인터페이스 변경은 송신 담당자, 수신 담당자, 통합 담당자가 합의한 후 반영한다.

---

# 2. 전체 연결 구조

```
Raspberry Pi Edge
        │
        │ WebSocket
        │ Metadata JSON → JPEG Binary
        ▼
AI·응용 서버
        │
        ├─ MediaPipe Hands
        ├─ 규칙 기반 제스처 인식
        ├─ 2차원 포인팅
        └─ 의도 판단
        │
        ├─ REST API / WebSocket
        ▼
React 통합 웹 대시보드
---------------------------------------------------------
AI·응용 서버
        │
        │ MQTT QoS 1
        ▼
Mosquitto Broker
        │
        ▼
ESP32·릴레이·IoT 기기
        │
        └─ ACK·상태 → Mosquitto → AI·응용 서버
```

도움 요청은 MQTT 기기 제어 경로와 분리한다.

```
HELP 제스처 또는 웹 요청
        ↓
FastAPI 도움 요청 생성
        ↓
PostgreSQL 저장
        ↓
WebSocket 실시간 이벤트
        ↓
보호자 웹 대시보드
```

---

# 3. 공통 데이터 규칙

## 3.1 기본 규칙

| 항목 | 규칙 |
| --- | --- |
| 인터페이스 버전 | `v1` |
| JSON Schema 버전 | `schema_version: "1.0"` |
| 문자 인코딩 | UTF-8 |
| JSON 필드명 | `snake_case` |
| 시간 | UTC Unix 밀리초 정수 |
| ID | UUID v4 문자열 |
| 좌표 | `0.0~1.0` 정규화 좌표 |
| 열거형 값 | 영문 대문자 |
| 오류 코드 | 영문 대문자와 밑줄 |
| 원본 영상 | 메모리 처리 후 즉시 폐기 |
| 규격 관리 위치 | `shared/schemas/v1/` |

## 3.2 공통 식별자

```
{
  "schema_version": "1.0",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "correlation_id": "d0f54b8a-b94c-48e8-bc60-dc57893d5247",
  "timestamp_ms": 1793430000000
}
```

| 필드 | 설명 |
| --- | --- |
| `message_id` | 개별 메시지를 구분하는 고유 ID |
| `correlation_id` | 영상 입력부터 기기 동작 또는 도움 요청 완료까지 하나의 흐름을 추적하는 ID |
| `timestamp_ms` | UTC 기준 Unix 밀리초 시각 |

## 3.3 버전 관리

v1 규격은 수정하지 않고 유지한다. 호환되지 않는 변경이 필요하면 v2 규격을 별도로 생성한다.

```
shared/schemas/
├── v1/
│   ├── frame-metadata.schema.json
│   ├── gesture-result.schema.json
│   ├── intent-result.schema.json
│   ├── mqtt-command.schema.json
│   ├── mqtt-ack.schema.json
│   └── help-request.schema.json
└── v2/
    └── ...
```

MQTT Topic도 같은 버전을 사용한다.

```
aiot/v1/{home_id}/{device_id}/cmd
aiot/v2/{home_id}/{device_id}/cmd
```

Topic의 버전과 페이로드의 `schema_version`이 일치하지 않으면 해당 메시지를 처리하지 않는다.

---

# 4. 좌표계 규격

## 4.1 정규화 좌표

화면 좌표는 해상도와 무관하도록 `0.0~1.0` 범위로 통일한다.

```
좌측 상단: (0.0, 0.0)
우측 하단: (1.0, 1.0)
x 증가 방향: 오른쪽
y 증가 방향: 아래쪽
```

예시:

```
{
  "x": 0.42,
  "y": 0.61
}
```

## 4.2 실제 픽셀 변환

```
pixel_x = int(normalized_x * frame_width)
pixel_y = int(normalized_y * frame_height)
```

## 4.3 방향 벡터 계산

화면 비율에 따른 각도 왜곡을 방지하기 위해 실제 해상도를 반영한다.

```
dx = (end_x - start_x) * frame_width
dy = (end_y - start_y) * frame_height
```

`dx`, `dy`를 사용하여 포인팅 각도를 계산한다.

## 4.4 영상 방향 정보

Edge는 프레임 메타데이터에 다음 정보를 포함한다.

```
{
  "width": 640,
  "height": 480,
  "mirrored": false,
  "rotation_deg": 0
}
```

- 좌표는 전송된 JPEG 영상 기준으로 해석한다.
- AI는 `mirrored`와 `rotation_deg`를 반영하여 좌표를 일관되게 처리한다.
- 카메라 위치나 각도가 변경되면 기기 방향 영역을 다시 보정한다.

---

# 5. Edge–AI 인터페이스

## 5.1 통신 방식

| 항목 | 규격 |
| --- | --- |
| 프로토콜 | WebSocket |
| 개발 주소 | `ws://{server}:8000/ws/v1/frames` |
| 운영 주소 | `wss://{domain}/ws/v1/frames` |
| 영상 형식 | JPEG |
| 기본 해상도 | 640×480 |
| 기본 FPS | 10 FPS |
| 기본 JPEG 품질 | 95 |
| 인증 | Edge 전용 Bearer Token |
| 전송 순서 | Metadata JSON → JPEG Binary |

JPEG 품질 95를 기본값으로 사용한다. 실제 장비 테스트 결과에 따라 설정 파일에서 값을 조정할 수 있어야 한다.

```
camera:
  width: 640
  height: 480
  fps: 10
  jpeg_quality: 95
```

- 네트워크·인코딩 부담이 크면 품질을 낮출 수 있다.
- 인식 품질이 부족하고 처리 여유가 있으면 더 높은 품질 또는 다른 영상 형식을 검토할 수 있다.
- 변경은 소스코드를 수정하지 않고 환경설정으로 수행한다.
- 최종값은 전송량, 지연시간, 인식 성공률을 함께 측정하여 결정한다.

## 5.2 Edge 인증

```
Authorization: Bearer {edge_token}
X-Edge-ID: raspberrypi-01
```

`edge_token`은 코드에 직접 작성하지 않고 Edge 환경설정에서 읽는다.

## 5.3 전송 순서

```
1. Edge → AI: 프레임 메타데이터 JSON
2. Edge → AI: 해당 프레임의 JPEG Binary
3. AI → Edge: 프레임 처리 ACK
```

WebSocket은 메시지 전송 순서를 보장하므로 JSON 다음에 수신된 Binary를 해당 `frame_id`의 영상으로 간주한다.

메타데이터 다음에 Binary가 오지 않거나 Binary 크기가 비정상적이면 해당 프레임을 폐기한다.

## 5.4 프레임 메타데이터

```
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

## 5.5 AI 서버 ACK

```
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

ACK 상태는 다음으로 제한한다.

| 상태 | 의미 |
| --- | --- |
| `PROCESSED` | 정상 처리 |
| `DROPPED` | 서버 부하 등으로 프레임 폐기 |
| `INVALID` | 메타데이터 또는 JPEG 형식 오류 |
| `ERROR` | 서버 내부 처리 오류 |

## 5.6 프레임 적체 방지

- Edge의 전송 대기 프레임은 최대 1개로 제한한다.
- 새 프레임이 생성되면 오래된 대기 프레임을 폐기한다.
- AI 서버는 오래된 영상보다 최신 영상을 우선한다.
- 연결 종료 시 `1초 → 2초 → 4초 → 최대 30초` 지수 백오프로 재접속한다.
- 원본 영상과 JPEG Binary를 디스크 또는 데이터베이스에 저장하지 않는다.

---

# 6. AI 담당 간 인터페이스

## 6.1 손동작 인식 결과

AI 담당 A는 다음 형식으로 AI 담당 B의 의도 판단 모듈에 결과를 전달한다.

```
{
  "schema_version": "1.0",
  "frame_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "handedness": "RIGHT",
  "gesture": "THUMB_UP",
  "pointing_vector": {
    "start_x": 0.42,
    "start_y": 0.61,
    "end_x": 0.75,
    "end_y": 0.38
  },
  "stable_frames": 6,
  "hold_time_ms": 520,
  "detected_at_ms": 1793430000080
}
```

제스처 값은 다음으로 제한한다.

- `POINTING`
- `THUMB_UP`
- `THUMB_DOWN`
- `HELP`
- `UNKNOWN`

`HELP`는 v1 필수 규격으로 포함한다. 실제 도움 요청 손 모양과 판정 조건은 제스처 규칙 설정에서 관리한다.

## 6.2 최종 의도 결과

```
{
  "schema_version": "1.0",
  "intent_id": "8d569643-93b1-4179-b0f3-76916501414f",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "target_device_id": "fan-01",
  "action": "ON",
  "status": "CONFIRMED",
  "confirmed_at_ms": 1793430000100
}
```

`action` 값:

- `ON`
- `OFF`
- `HELP`

`status` 값:

- `PENDING`
- `CONFIRMED`
- `CANCELLED`

HELP 의도는 특정 기기를 대상으로 하지 않는다.

```
{
  "target_device_id": null,
  "action": "HELP",
  "status": "CONFIRMED"
}
```

취소된 경우 취소 사유를 포함한다.

```
{
  "status": "CANCELLED",
  "cancel_reason": "TARGET_NOT_FOUND"
}
```

취소 사유:

- `TARGET_NOT_FOUND`
- `AMBIGUOUS_TARGET`
- `GESTURE_TIMEOUT`
- `INVALID_GESTURE`
- `DIRECTION_CHANGED`

---

# 7. AI–웹 인터페이스

## 7.1 통신 구분

```
REST API:
로그인, 방·기기 등록, 위치 매핑, 이력 조회, 도움 요청 상태 변경

WebSocket:
기기 선택, 제스처 확정, 명령 결과, 기기 상태, 도움 요청 실시간 전달
```

## 7.2 기본 경로

```
REST API: /api/v1
WebSocket: /ws/v1/events
Content-Type: application/json
```

## 7.3 핵심 REST API

| Method | 경로 | 기능 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 로그인 및 JWT Cookie 발급 |
| `POST` | `/api/v1/auth/logout` | 인증 Cookie 삭제 |
| `GET` | `/api/v1/auth/me` | 현재 사용자 조회 |
| `GET` | `/api/v1/rooms` | 방 목록 조회 |
| `POST` | `/api/v1/rooms` | 방 등록 |
| `GET` | `/api/v1/devices` | 기기 목록 조회 |
| `POST` | `/api/v1/devices` | 기기·위치·방향 영역 등록 |
| `PATCH` | `/api/v1/devices/{device_id}` | 기기 정보 수정 |
| `GET` | `/api/v1/control-events` | 기기 제어 이력 조회 |
| `GET` | `/api/v1/help-requests` | 도움 요청 조회 |
| `POST` | `/api/v1/help-requests` | 웹 도움 요청 생성 |
| `PATCH` | `/api/v1/help-requests/{request_id}` | 도움 요청 상태 변경 |

## 7.4 기기 위치 등록

```
{
  "device_id": "fan-01",
  "room_id": "room-01",
  "name": "선풍기",
  "device_type": "FAN",
  "map_position": {
    "x": 0.72,
    "y": 0.35
  },
  "pointing_region": {
    "min_angle_deg": -15.0,
    "max_angle_deg": 15.0
  },
  "enabled": true
}
```

- `map_position`: 웹 방 배치도에 표시할 위치
- `pointing_region`: 포인팅 대상 기기를 판정할 방향 범위
- 두 값은 서로 다른 목적으로 관리한다.

## 7.5 성공 응답

```
{
  "success": true,
  "data": {
    "device_id": "fan-01"
  }
}
```

## 7.6 오류 응답

```
{
  "success": false,
  "error": {
    "code": "DEVICE_NOT_FOUND",
    "message": "요청한 기기를 찾을 수 없습니다."
  }
}
```

---

# 8. 웹 인증 및 보안

## 8.1 인증 방식

JWT는 응답 본문이나 Local Storage에 저장하지 않고 HttpOnly Cookie로 발급한다.

```
Set-Cookie: aiot_access_token={JWT};
HttpOnly;
Secure;
SameSite=Strict;
Path=/;
Max-Age=1800
```

| 속성 | 규격 |
| --- | --- |
| `HttpOnly` | JavaScript의 JWT 직접 접근 차단 |
| `Secure` | 운영 환경에서 HTTPS/WSS로만 전송 |
| `SameSite` | `Strict` |
| `Path` | `/` |
| `Max-Age` | 1,800초 |
| `Domain` | 지정하지 않고 Host-only Cookie 사용 |

개발 환경에서는 `Secure=false`, 운영 환경에서는 `Secure=true`를 사용한다.

## 8.2 동일 출처 구성

운영 환경은 Nginx를 이용하여 React, REST API, WebSocket을 같은 도메인으로 제공한다.

```
https://aiot.example.com/          → React
https://aiot.example.com/api/v1/   → FastAPI
wss://aiot.example.com/ws/v1/      → FastAPI WebSocket
```

개발 환경에서는 Vite Proxy로 `/api`와 `/ws`를 FastAPI에 전달한다.

## 8.3 CORS

프런트엔드와 FastAPI 주소가 다를 때만 정확한 출처를 허용한다.

```
allow_origins=["http://localhost:5173"]
allow_credentials=True
```

Cookie 인증에서는 `allow_origins=["*"]`를 사용하지 않는다.

## 8.4 CSRF

HttpOnly Cookie 인증은 CSRF 공격을 별도로 방어해야 한다.

- `SameSite=Strict` 적용
- 상태 변경 API의 `Origin` 검사
- `POST`, `PATCH`, `DELETE`에 CSRF Token 적용
- 조회용 `GET` 요청에서 데이터 변경 금지

JWT Cookie와 CSRF Cookie를 분리한다.

```
aiot_access_token: HttpOnly=true
aiot_csrf_token:   HttpOnly=false
```

React는 다음 헤더를 포함한다.

```
X-CSRF-Token: {csrf_token}
```

## 8.5 WebSocket 인증

WebSocket 연결 순서:

```
1. Origin 허용 목록 검사
2. HttpOnly Cookie에서 JWT 추출
3. JWT 서명과 만료시간 검사
4. 사용자 역할 검사
5. 검사 통과 후 accept()
```

종료 코드:

| 코드 | 의미 |
| --- | --- |
| `4401` | JWT 없음 또는 만료 |
| `4403` | 접근 권한 없음 |
| `4408` | 인증 또는 연결 시간 초과 |

---

# 9. 웹 실시간 이벤트

## 9.1 이벤트 Envelope

```
{
  "schema_version": "1.0",
  "event_id": "68069bdd-b523-4702-b960-c0257886d358",
  "event_type": "device.selected",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "timestamp_ms": 1793430000100,
  "data": {}
}
```

## 9.2 이벤트 종류

| 이벤트 | 설명 |
| --- | --- |
| `edge.connected` | Raspberry Pi 연결 |
| `edge.disconnected` | Raspberry Pi 연결 종료 |
| `device.selected` | 포인팅 대상 기기 선택 |
| `gesture.confirmed` | 명령 제스처 확정 |
| `command.created` | MQTT 명령 생성 |
| `command.completed` | 기기 제어 성공 |
| `command.failed` | 기기 제어 실패 |
| `device.state_changed` | 기기 상태 변경 |
| `help.created` | 도움 요청 생성 |
| `help.updated` | 도움 요청 상태 변경 |

## 9.3 기기 선택 이벤트

```
{
  "schema_version": "1.0",
  "event_id": "68069bdd-b523-4702-b960-c0257886d358",
  "event_type": "device.selected",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "timestamp_ms": 1793430000100,
  "data": {
    "device_id": "fan-01",
    "device_name": "선풍기"
  }
}
```

---

# 10. 도움 요청 규격

HELP는 v1 필수 규격으로 포함한다.

## 10.1 도움 요청 생성

```
{
  "schema_version": "1.0",
  "request_id": "077df9d4-d4b0-47a9-89b4-c21809a03780",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "user_id": "user-01",
  "source": "GESTURE",
  "status": "CREATED",
  "created_at_ms": 1793430000100
}
```

`source` 값:

- `GESTURE`
- `WEB`

## 10.2 처리 상태

```
CREATED
→ CONFIRMED
→ COMPLETED
```

| 상태 | 의미 |
| --- | --- |
| `CREATED` | 도움 요청 발생 |
| `CONFIRMED` | 보호자가 요청 확인 |
| `COMPLETED` | 도움 요청 처리 완료 |

## 10.3 실시간 이벤트

```
{
  "schema_version": "1.0",
  "event_id": "68069bdd-b523-4702-b960-c0257886d358",
  "event_type": "help.created",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "timestamp_ms": 1793430000100,
  "data": {
    "request_id": "077df9d4-d4b0-47a9-89b4-c21809a03780",
    "user_id": "user-01",
    "status": "CREATED"
  }
}
```

---

# 11. AI–MQTT 인터페이스

## 11.1 Topic 규칙

```
aiot/v1/{home_id}/{device_id}/cmd
aiot/v1/{home_id}/{device_id}/ack
aiot/v1/{home_id}/{device_id}/state
aiot/v1/{home_id}/{device_id}/status
```

| Topic | 방향 | 역할 |
| --- | --- | --- |
| `cmd` | 서버 → ESP32 | 기기 제어 명령 |
| `ack` | ESP32 → 서버 | 명령 실행 결과 |
| `state` | ESP32 → 서버 | 현재 기기 상태 |
| `status` | ESP32 → 서버 | 온라인·오프라인 상태와 LWT |

## 11.2 제어 명령

```
{
  "schema_version": "1.0",
  "command_id": "d4419718-f59a-4432-a3c4-866bc595ad91",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "device_id": "fan-01",
  "action": "ON",
  "issued_at_ms": 1793430000120,
  "expires_at_ms": 1793430005120,
  "source": "GESTURE"
}
```

`action` 값:

- `ON`
- `OFF`

`source` 값:

- `GESTURE`
- `WEB`
- `SYSTEM`

HELP는 MQTT 기기 제어 명령으로 발행하지 않는다.

## 11.3 ACK 메시지

```
{
  "schema_version": "1.0",
  "command_id": "d4419718-f59a-4432-a3c4-866bc595ad91",
  "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab",
  "device_id": "fan-01",
  "result": "OK",
  "state": "ON",
  "processed_at_ms": 1793430000200,
  "error_code": null
}
```

`result` 값:

- `OK`
- `ERROR`
- `EXPIRED`
- `DUPLICATE`

## 11.4 상태 메시지

```
{
  "schema_version": "1.0",
  "device_id": "fan-01",
  "state": "ON",
  "updated_at_ms": 1793430000200
}
```

## 11.5 MQTT 설정

| 항목 | 규격 |
| --- | --- |
| `cmd` QoS | QoS 1 |
| `ack` QoS | QoS 1 |
| `state` QoS | QoS 1 |
| `status` QoS | QoS 1 |
| `cmd` Retain | `false` |
| `ack` Retain | `false` |
| `state` Retain | `true` |
| `status` Retain | `true` |
| ACK 제한시간 | 2초 |
| 명령 유효시간 | 5초 |
| ESP32 세션 | Clean Session |
| 초기 자동 재전송 | 사용하지 않음 |
| 중복 방지 | `command_id` |

ACK 제한시간과 명령 유효시간은 서로 다르다.

- 서버는 명령 발행 후 2초 동안 ACK를 기다린다.
- ESP32는 발행 후 5초가 지난 명령을 실행하지 않는다.
- ACK가 2초 이내에 오지 않으면 서버는 명령을 실패로 기록한다.
- 늦게 도착한 명령은 ESP32가 `EXPIRED`로 처리한다.

## 11.6 중복 명령 처리

```
처음 받은 command_id
→ 릴레이 동작
→ command_id 저장
→ ACK 발행

이미 처리한 command_id
→ 릴레이 재동작 금지
→ DUPLICATE ACK 발행
```

## 11.7 시간 동기화

ESP32는 명령 만료 여부를 판단하기 위해 NTP로 시간을 동기화한다.

시간이 동기화되지 않은 상태에서는 릴레이 제어 명령을 실행하지 않고 오류 ACK를 발행하는 것을 원칙으로 한다.

## 11.8 LWT 상태

정상 연결:

```
{
  "schema_version": "1.0",
  "device_id": "fan-01",
  "status": "ONLINE",
  "timestamp_ms": 1793430000000
}
```

비정상 연결 종료:

```
{
  "schema_version": "1.0",
  "device_id": "fan-01",
  "status": "OFFLINE",
  "timestamp_ms": 1793430000000
}
```

Mosquitto는 LWT 메시지를 `status` Topic에 Retain으로 발행한다.

---

# 12. 공통 오류 규격

## 12.1 REST 오류

```
{
  "success": false,
  "error": {
    "code": "DEVICE_NOT_FOUND",
    "message": "요청한 기기를 찾을 수 없습니다.",
    "correlation_id": "e17d8451-59dd-4c45-92e0-3fdc018e72ab"
  }
}
```

## 12.2 주요 오류 코드

| 코드 | 설명 |
| --- | --- |
| `INVALID_SCHEMA` | 메시지 Schema 불일치 |
| `UNSUPPORTED_VERSION` | 지원하지 않는 인터페이스 버전 |
| `UNAUTHORIZED` | 인증 실패 |
| `FORBIDDEN` | 권한 부족 |
| `DEVICE_NOT_FOUND` | 기기를 찾을 수 없음 |
| `TARGET_NOT_FOUND` | 포인팅 대상 없음 |
| `COMMAND_EXPIRED` | 명령 유효시간 초과 |
| `COMMAND_DUPLICATE` | 중복 명령 |
| `ACK_TIMEOUT` | 제한시간 안에 ACK 미수신 |
| `INTERNAL_ERROR` | 서버 내부 오류 |

---

# 13. 규격별 기준 파일

| 인터페이스 | 기준 파일 |
| --- | --- |
| Edge 프레임 메타데이터 | `shared/schemas/v1/frame-metadata.schema.json` |
| 손동작 인식 결과 | `shared/schemas/v1/gesture-result.schema.json` |
| 최종 의도 결과 | `shared/schemas/v1/intent-result.schema.json` |
| MQTT 명령 | `shared/schemas/v1/mqtt-command.schema.json` |
| MQTT ACK | `shared/schemas/v1/mqtt-ack.schema.json` |
| 도움 요청 | `shared/schemas/v1/help-request.schema.json` |
| Python 공통 타입 | `shared/types.py` |
| 공통 상수 | `shared/constants.py` |
| 공통 오류 | `shared/errors.py` |
| MQTT Topic | `shared/mqtt_topics.py` |
| REST API 문서 | `docs/api-spec.md` |
| WebSocket 문서 | `docs/websocket-spec.md` |
| MQTT 문서 | `docs/mqtt-spec.md` |

---

# 14. 인터페이스 준수 규칙

1. 각 담당자는 `shared/`의 규격을 임의로 수정하지 않는다.
2. Schema에 없는 필드를 임의로 추가해 송신하지 않는다.
3. 필드 제거 또는 자료형 변경은 새로운 버전에서만 수행한다.
4. 선택 필드를 추가할 때도 통합 담당자 검토를 받는다.
5. 송신자는 전송 전에 Schema를 준수해야 한다.
6. 수신자는 메시지를 사용하기 전에 Schema와 버전을 검사해야 한다.
7. 잘못된 메시지는 실행하지 않고 오류로 기록한다.
8. 영상·비밀번호·JWT·인증정보는 로그에 기록하지 않는다.
9. 공통 인터페이스 변경 시 관련 계약 테스트도 함께 수정한다.
10. 통합 담당자는 PR에서 인터페이스 준수 여부를 확인한다.

---

# 15. 통합 테스트 기준

## Edge–AI

- Metadata JSON 다음에 JPEG Binary가 전달되는지 확인
- `frame_id`와 ACK의 `frame_id`가 일치하는지 확인
- 해상도·반전·회전 정보가 정확한지 확인
- 프레임 적체 시 오래된 프레임이 폐기되는지 확인

## AI 담당 간

- 정규화 좌표가 `0.0~1.0` 범위인지 확인
- 화면 비율을 반영하여 포인팅 각도를 계산하는지 확인
- 안정화 조건을 충족하지 않은 제스처가 의도로 확정되지 않는지 확인
- HELP 의도가 기기 선택 없이 처리되는지 확인

## AI–웹

- HttpOnly Cookie의 JWT를 JavaScript에서 읽을 수 없는지 확인
- 인증되지 않은 REST·WebSocket 요청이 거부되는지 확인
- 허용되지 않은 Origin의 WebSocket 연결이 거부되는지 확인
- 도움 요청과 기기 상태가 실시간으로 표시되는지 확인

## AI–MQTT

- Topic의 `v1`과 페이로드의 `schema_version`이 일치하는지 확인
- 동일 `command_id`가 두 번 실행되지 않는지 확인
- 5초가 지난 명령이 실행되지 않는지 확인
- ACK가 2초 안에 도착하지 않으면 실패 처리되는지 확인
- `state`와 `status`만 Retain되는지 확인
- HELP가 MQTT 기기 명령으로 발행되지 않는지 확인

# 16. 담당 기준 파일

## 1. 엣지 담당

```jsx
shared/schemas/v1/frame-metadata.schema.json
edge/camera.py
edge/frame_encoder.py
edge/websocket_client.py
edge/metrics.py
```

## 2. AI 담당 A — 손동작 인식

```jsx
shared/schemas/v1/gesture-result.schema.json
server/vision/hand_detector.py
server/vision/landmark_processor.py
server/vision/pointing_detector.py
server/vision/gesture_rules.py
server/vision/stability_checker.py
```

## 3. AI 담당 B — 의도 판단

```jsx
shared/schemas/v1/gesture-result.schema.json
shared/schemas/v1/intent-result.schema.json
server/intent/engine.py
server/intent/state_machine.py
server/intent/device_matcher.py
server/intent/parameters.py
server/intent/latency_tracker.py
```

## 4. 웹·응용 서버 담당

```jsx
shared/schemas/v1/help-request.schema.json
server/api/
server/services/
server/db/
server/security/
web/
docs/api-spec.md
docs/websocket-spec.md
```

## 5. 인터페이스·통합 담당

```jsx
shared/
server/iot/
firmware/
deploy/
docker-compose.yml
tests/contract/
tests/integration/
tests/e2e/
docs/mqtt-spec.md
```

