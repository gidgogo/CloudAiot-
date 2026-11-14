# REST API 명세

웹 대시보드와 FastAPI 사이의 요청·응답 규격을 기록한다.
기준 규격은 [공통 인터페이스 규격 v1.0](interfaces/common-interface-spec-v1.0.md) 7·8장이다.
실행 중인 서버의 <http://localhost:8000/docs>에서 같은 내용을 직접 호출해 볼 수 있다.

## 공통 규칙

- 기본 경로: `/api/v1`, `Content-Type: application/json`
- 시간: UTC Unix 밀리초 정수(`*_ms`)
- ID(`room_id`, `device_id`, `user_id`): 영문·숫자·`-`·`_` 1~64자. 생략하면 서버가 UUID v4를 만든다.
- 요청 본문에 정의되지 않은 필드가 있으면 `INVALID_SCHEMA`로 거부한다.
- PATCH는 보낸 필드만 바꾼다. 빈 본문과 필수 필드의 `null`은 거부한다.
- `/health`와 `/api/v1/auth/login`, `/api/v1/auth/logout`을 뺀 모든 API는 로그인이 필요하다.

### 성공 응답

```json
{ "success": true, "data": { } }
```

목록 중 페이지를 나누는 API(제어 이력, 도움 요청)는 `meta`를 함께 보낸다.

```json
{ "success": true, "data": [ ], "meta": { "total": 3, "limit": 50, "offset": 0 } }
```

### 오류 응답

```json
{
  "success": false,
  "error": { "code": "DEVICE_NOT_FOUND", "message": "요청한 기기를 찾을 수 없습니다.", "correlation_id": null }
}
```

| HTTP | 코드 | 의미 |
| --- | --- | --- |
| 401 | `UNAUTHORIZED` | 로그인 안 함, JWT 만료·위조, 삭제된 사용자 |
| 401 | `INVALID_CREDENTIALS` | 이메일 또는 비밀번호 틀림(계정 존재 여부는 알려주지 않음) |
| 403 | `FORBIDDEN` | 역할 권한 없음, CSRF 토큰 없음·불일치, 허용되지 않은 Origin |
| 404 | `NOT_FOUND` | 없는 경로 |
| 404 | `ROOM_NOT_FOUND` / `DEVICE_NOT_FOUND` / `USER_NOT_FOUND` / `HELP_REQUEST_NOT_FOUND` / `COMMAND_NOT_FOUND` / `MAPPING_NOT_FOUND` | 대상 없음 |
| 405 | `METHOD_NOT_ALLOWED` | 허용되지 않는 메서드 |
| 409 | `ROOM_ALREADY_EXISTS` / `DEVICE_ALREADY_EXISTS` / `USER_ALREADY_EXISTS` | 중복 |
| 409 | `ROOM_NOT_EMPTY` | 기기가 남아 있는 방 삭제 |
| 409 | `INVALID_STATUS_TRANSITION` | 도움 요청 상태 순서 위반 |
| 409 | `INVALID_USER_ROLE` | 역할이 맞지 않는 사용자 지정(예: 보호자를 방 사용자로) |
| 409 | `CANNOT_MODIFY_SELF` | 관리자가 자기 역할 변경·삭제 |
| 409 | `MAPPING_CONFLICT` | 같은 명령을 두 제스처에 연결 |
| 409 | `HELP_USER_UNKNOWN` | HELP 제스처를 누구의 요청으로 기록할지 정할 수 없음 |
| 422 | `INVALID_SCHEMA` | 요청 형식·값 범위 오류 |
| 429 | `TOO_MANY_ATTEMPTS` | 같은 계정·주소에서 로그인 5회 연속 실패(5분) |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |

`DEVICE_NOT_FOUND`, `INVALID_SCHEMA`, `UNAUTHORIZED`, `FORBIDDEN`, `INTERNAL_ERROR`를 뺀 코드는 웹 서버 전용이다
(`server/services/__init__.py`). 공통 규격에 올릴지는 통합 담당자와 합의한다.

## 인증과 보안 (규격 8장)

### 로그인 흐름

1. `POST /api/v1/auth/login` → 서버가 Cookie 두 개를 발급한다.
   - `aiot_access_token`: JWT. `HttpOnly; SameSite=Strict; Path=/; Max-Age=1800`, 운영에서는 `Secure`
   - `aiot_csrf_token`: CSRF 토큰. JavaScript가 읽을 수 있다(HttpOnly 아님).
2. 웹은 `POST`·`PATCH`·`DELETE` 요청에 `X-CSRF-Token: {aiot_csrf_token 값}` 헤더를 붙인다.
3. 서버는 헤더 = Cookie = JWT에 넣어 둔 값(SHA-256)인지 확인한다. 다른 세션의 CSRF 쌍으로 바꿔 끼워도 거부된다.
4. 상태 변경 요청에 `Origin` 헤더가 있으면 `ALLOWED_ORIGINS` 또는 같은 출처여야 한다.
5. 매 요청마다 JWT의 사용자가 DB에 있는지, 현재 역할이 무엇인지 다시 확인한다(역할 변경·삭제가 바로 반영됨).

JWT는 응답 본문에 넣지 않는다. CORS는 `ALLOWED_ORIGINS`에 적힌 출처만 `allow_credentials`로 허용한다(`*` 사용 안 함).

### 역할별 권한 (SAD 6.1)

| API | USER | GUARDIAN | ADMIN |
| --- | --- | --- | --- |
| 방·기기·제어 이력·제스처 매핑 조회 | ✅ | ✅ | ✅ |
| 방·기기·제스처 매핑 변경 | ❌ | ❌ | ✅ |
| 도움 요청 생성 | 본인만 | ❌ | 사용자 지정 |
| 도움 요청 조회 | 본인 것 | 연결된 사용자 것 | 전체 |
| 도움 요청 확인·완료 | ❌ | 연결된 사용자 것 | 전체 |
| 사용자 조회 | 본인 | 본인 + 연결된 사용자 | 전체 |
| 사용자·보호자 연결 관리 | ❌ | ❌ | ✅ |

### 엔드포인트

| Method | 경로 | 설명 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | `{ "email", "password" }` → 세션 정보 + Cookie |
| `POST` | `/api/v1/auth/logout` | Cookie 삭제(만료된 로그인도 가능) |
| `GET` | `/api/v1/auth/me` | 현재 세션 정보 |
| `POST` | `/api/v1/auth/password` | `{ "current_password", "new_password" }` 본인 비밀번호 변경 |

세션 정보(`login`, `me` 응답의 `data`):

```json
{
  "user": { "user_id": "guardian-01", "email": "guardian@demo.local", "name": "보호자", "role": "GUARDIAN", "created_at_ms": 1793430000000 },
  "linked_user_ids": ["user-01"],
  "expires_at_ms": 1793431800000
}
```

`linked_user_ids`는 보호자일 때만 채워진다. 이메일은 대소문자를 구분하지 않는다. 비밀번호는 8자 이상, 72바이트 이하.

## 사용자·보호자 연결

| Method | 경로 | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/users?role=` | 로그인 | 볼 수 있는 사용자 목록 |
| `POST` | `/api/v1/users` | ADMIN | `{ user_id?, email, password, name, role }` (201) |
| `GET` | `/api/v1/users/{user_id}` | 로그인 | 볼 수 있는 사용자만 |
| `PATCH` | `/api/v1/users/{user_id}` | ADMIN | `name`, `role`, `password`. 역할이 바뀌면 보호자 연결 해제, 실시간 연결 종료 |
| `DELETE` | `/api/v1/users/{user_id}` | ADMIN | 204. 본인은 삭제 불가 |
| `GET` | `/api/v1/guardian-links?guardian_id=&user_id=` | ADMIN | 연결 목록 |
| `POST` | `/api/v1/guardian-links` | ADMIN | `{ guardian_id, user_id }` (201, 이미 있으면 그대로) |
| `DELETE` | `/api/v1/guardian-links/{guardian_id}/{user_id}` | ADMIN | 204 |

응답에 비밀번호·해시는 절대 포함하지 않는다.

## 방

| Method | 경로 | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/rooms` | 로그인 | 방 목록 |
| `POST` | `/api/v1/rooms` | ADMIN | 방 등록 (201) |
| `GET` | `/api/v1/rooms/{room_id}` | 로그인 | 방 조회 |
| `PATCH` | `/api/v1/rooms/{room_id}` | ADMIN | `name`, `description`, `resident_user_id` 수정 |
| `DELETE` | `/api/v1/rooms/{room_id}` | ADMIN | 204. 기기가 있으면 `ROOM_NOT_EMPTY` |

```json
{ "room_id": "room-01", "name": "안방", "description": "1층", "resident_user_id": "user-01" }
```

`resident_user_id`는 이 방에서 생활하는 USER다. HELP 손동작을 누구의 도움 요청으로 기록할지 정하는 데 쓴다.

## 기기

| Method | 경로 | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/devices?room_id=&enabled=` | 로그인 | 기기 목록 (필터 선택) |
| `POST` | `/api/v1/devices` | ADMIN | 기기·위치·방향 영역 등록 (201) |
| `GET` | `/api/v1/devices/{device_id}` | 로그인 | 기기 조회 |
| `PATCH` | `/api/v1/devices/{device_id}` | ADMIN | 기기 정보 수정 |
| `DELETE` | `/api/v1/devices/{device_id}` | ADMIN | 204. 제어 이력도 함께 삭제 |

요청(규격 7.4):

```json
{
  "device_id": "fan-01",
  "room_id": "room-01",
  "name": "선풍기",
  "device_type": "FAN",
  "map_position": { "x": 0.72, "y": 0.35 },
  "pointing_region": { "min_angle_deg": -15.0, "max_angle_deg": 15.0 },
  "enabled": true
}
```

| 필드 | 규칙 |
| --- | --- |
| `device_id` | MQTT Topic `aiot/v1/{home_id}/{device_id}/...`의 `device_id`와 같은 값 |
| `device_type` | 영문 대문자로 시작, 대문자·숫자·`_` (웹 선택지: `LIGHT`, `FAN`, `TV`, `AIR_CONDITIONER`, `HEATER`, `OUTLET`, `OTHER`) |
| `map_position` | 웹 배치도 위치. `x`, `y` 모두 0.0~1.0 |
| `pointing_region` | 포인팅 판정 범위. -180~180, `min_angle_deg < max_angle_deg` |

`pointing_region` 각도는 AI 의도 판단 모듈(`server/intent/device_matcher.py`)과 같은 기준이다.
카메라 영상 좌표에서 `atan2(dy, dx)`로 계산하며 오른쪽 0°, 아래 +90°, 위 -90°, 왼쪽 ±180°이다.
사용 중인 기기끼리 영역이 겹치면 그 방향은 대상을 정하지 못해 명령이 취소된다(웹 설정 화면이 경고한다).

응답 `data`는 요청 필드에 서버가 관리하는 값을 더한다.

```json
{
  "...": "요청 필드와 동일",
  "state": "UNKNOWN",
  "connection_status": "OFFLINE",
  "state_updated_at_ms": null,
  "created_at_ms": 1793430000000,
  "updated_at_ms": 1793430000000
}
```

`state`(`ON`/`OFF`/`UNKNOWN`)와 `connection_status`(`ONLINE`/`OFFLINE`)는 MQTT 수신으로만 바뀌며 PATCH로 바꿀 수 없다.
IoT 모듈은 `DeviceService.update_state(device_id, state)`, `update_connection_status(device_id, status)`를 호출한다.
의도 판단 모듈은 `DeviceService.pointing_regions()`로 사용 중인 기기의 방향 영역 목록(`DeviceRegion`)을 받는다.

## 기기 제어 이력

| Method | 경로 | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/control-events?device_id=&limit=50&offset=0` | 로그인 | 최신순 목록 (`limit` 1~200) |
| `GET` | `/api/v1/control-events/{command_id}` | 로그인 | 명령 1건 조회 |

응답 항목:

```json
{
  "command_id": "d4419718-...",
  "correlation_id": "e17d8451-...",
  "device_id": "fan-01",
  "action": "ON",
  "source": "GESTURE",
  "status": "COMPLETED",
  "result": "OK",
  "error_code": null,
  "gesture_confirmed_at_ms": 1793430000100,
  "command_published_at_ms": 1793430000120,
  "ack_received_at_ms": 1793430000200,
  "latency_ms": 100
}
```

- `status`: `PENDING`(ACK 대기) → `COMPLETED` 또는 `FAILED`
- `latency_ms`: 제스처 확정 시각(없으면 명령 발행 시각) → ACK 수신 시각 (NFR-01)
- 실패 시 `error_code`: ACK의 `error_code`, 없으면 `COMMAND_EXPIRED`(EXPIRED) 또는 `ACK_TIMEOUT`(2초 초과)
- 성공 ACK의 `state`는 기기 상태에도 반영된다.

이력은 IoT 모듈이 `ControlEventService`로 남긴다.

| 시점 | 호출 |
| --- | --- |
| MQTT 명령 발행 직후 | `record_command(command, gesture_confirmed_at_ms=...)` |
| ACK 수신 | `record_ack(ack)` |
| ACK 2초 초과 | `mark_timeout(command_id)` |

## 도움 요청

| Method | 경로 | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/help-requests?status=&limit=50&offset=0` | 로그인 | 볼 수 있는 요청을 최신순으로 |
| `POST` | `/api/v1/help-requests` | USER, ADMIN | 웹 도움 요청 생성 (201, `source=WEB`) |
| `GET` | `/api/v1/help-requests/{request_id}` | 로그인 | 볼 수 있는 요청만 |
| `PATCH` | `/api/v1/help-requests/{request_id}` | GUARDIAN(연결된 사용자), ADMIN | 상태 변경 |

생성 요청: USER는 `{}`(본인), ADMIN은 `{ "user_id": "user-01" }`. `correlation_id`는 선택이며 생략하면 `request_id`와 같다.
도움 요청은 USER 역할 사용자만 대상이 된다.

상태 변경 요청:

```json
{ "status": "CONFIRMED" }
```

상태는 `CREATED → CONFIRMED → COMPLETED` 순서로만 바뀐다. 건너뛰거나 되돌리면 `INVALID_STATUS_TRANSITION`.
`confirmed_by`, `completed_by`에는 처리한 보호자·관리자가 기록된다.

응답 `data`:

```json
{
  "schema_version": "1.0",
  "request_id": "077df9d4-...",
  "correlation_id": "e17d8451-...",
  "user_id": "user-01",
  "source": "WEB",
  "status": "CONFIRMED",
  "created_at_ms": 1793430000100,
  "confirmed_at_ms": 1793430005000,
  "confirmed_by": "guardian-01",
  "completed_at_ms": null,
  "completed_by": null
}
```

HELP 제스처는 의도 판단 모듈이 `HelpService.create_from_gesture(correlation_id, room_id=None)`를 호출해 만든다.
사용자는 `room_id`의 방 사용자 → (room_id가 없으면) 방 사용자가 한 명뿐일 때 그 사용자 순서로 정한다.
정할 수 없으면 `HELP_USER_UNKNOWN`.

## 제스처·명령 매핑 (SAD 4.1)

| Method | 경로 | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/gesture-mappings` | 로그인 | 매핑 목록 |
| `PATCH` | `/api/v1/gesture-mappings/{gesture}` | ADMIN | `{ "action"?: "ON"\|"OFF"\|"HELP", "enabled"?: bool }` |

기본값: `THUMB_UP→ON`, `THUMB_DOWN→OFF`, `HELP→HELP`. `POINTING`은 기기 선택용이라 매핑 대상이 아니다.
사용 중인 매핑끼리 같은 명령을 쓰면 `MAPPING_CONFLICT`.
의도 판단 모듈은 `GestureMappingService.action_for(gesture)`로 현재 명령을 얻는다(꺼져 있으면 `None`).
