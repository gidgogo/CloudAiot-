# 데이터베이스 명세

사용자, 방, 기기, 제어 이력, 도움 요청 데이터 구조를 기록한다.

- 모델: `server/db/models.py` (SQLAlchemy 2.0)
- PostgreSQL DDL: `server/db/migrations/initial_schema.sql` (모델에서 생성)
- 연결: 환경변수 `DATABASE_URL`. 없으면 로컬 개발용 `sqlite:///./cloudaiot-dev.db`
  - Docker 예: `postgresql+psycopg://cloudaiot:비밀번호@postgres:5432/cloudaiot`
- 서버 시작 시 없는 테이블을 만든다(`Base.metadata.create_all`). 기존 테이블은 바꾸지 않는다.
  모델을 바꾼 뒤에는 기존 개발 DB를 지우거나(`cloudaiot-dev.db`) 직접 ALTER 해야 한다.
- 모델을 바꾸면 `python -m server.db.schema_sql`로 DDL을 다시 만든다(테스트가 최신 여부를 검사한다).
- 실제 PostgreSQL로 테스트: `TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest tests/server`
  (테스트마다 테이블을 지우고 다시 만드므로 빈 테스트용 DB를 쓴다.)

## 저장 원칙 (SAD 5장, NFR-03)

- 카메라 원본 프레임, JPEG, 손 랜드마크, 포인팅 벡터는 저장하지 않는다.
- 기기 제어 결과(`control_events`)와 도움 요청(`help_requests`)만 이력으로 남긴다.
- 비밀번호는 bcrypt 해시(`password_hash`)로만 저장하고 응답·로그에 넣지 않는다.
- 시간은 모두 UTC Unix 밀리초 `BIGINT`(`*_ms`)다.

## 테이블

### users

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `user_id` | VARCHAR(64) PK | |
| `email` | VARCHAR(255) UNIQUE | 로그인 ID |
| `password_hash` | VARCHAR(255) | bcrypt |
| `name` | VARCHAR(100) | |
| `role` | VARCHAR(16) | `USER` / `GUARDIAN` / `ADMIN` |
| `created_at_ms` | BIGINT | |

### guardian_links

보호자와 사용자(환자)의 연결. 보호자는 연결된 사용자의 도움 요청만 다룬다(권한 단계에서 적용).

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `guardian_id` | FK users, PK | `GUARDIAN` |
| `user_id` | FK users, PK | `USER` |
| `created_at_ms` | BIGINT | |

### rooms

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `room_id` | VARCHAR(64) PK | |
| `name` | VARCHAR(100) | |
| `description` | VARCHAR(500) NULL | |
| `resident_user_id` | FK users NULL (SET NULL) | 방 사용자(USER). HELP 제스처 요청자 결정에 사용 |
| `created_at_ms`, `updated_at_ms` | BIGINT | |

### devices

배치도 좌표와 포인팅 판정 범위는 목적이 달라 따로 저장한다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `device_id` | VARCHAR(64) PK | MQTT Topic의 `{device_id}`와 같은 값 |
| `room_id` | FK rooms (RESTRICT) | 기기가 있는 방은 삭제 불가 |
| `name`, `device_type` | VARCHAR | |
| `map_x`, `map_y` | FLOAT | 웹 배치도 위치 0.0~1.0 |
| `min_angle_deg`, `max_angle_deg` | FLOAT | 포인팅 판정 범위 -180~180 |
| `enabled` | BOOLEAN | 비활성 기기는 포인팅 대상에서 제외 |
| `state` | VARCHAR(16) | `ON` / `OFF` / `UNKNOWN` (MQTT state·ACK) |
| `connection_status` | VARCHAR(16) | `ONLINE` / `OFFLINE` (MQTT status·LWT) |
| `state_updated_at_ms` | BIGINT NULL | 마지막 상태 수신 시각 |
| `created_at_ms`, `updated_at_ms` | BIGINT | |

### control_events

MQTT 명령 1건당 1행. NFR-01 지연 측정의 기준 데이터다.

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `command_id` | VARCHAR(64) PK | MQTT 명령의 `command_id` |
| `correlation_id` | VARCHAR(64) | 영상 입력부터 이어지는 흐름 ID |
| `device_id` | FK devices (CASCADE) | |
| `action` | VARCHAR(8) | `ON` / `OFF` |
| `source` | VARCHAR(16) | `GESTURE` / `WEB` / `SYSTEM` |
| `status` | VARCHAR(16) | `PENDING` / `COMPLETED` / `FAILED` |
| `result` | VARCHAR(16) NULL | ACK `result` |
| `error_code` | VARCHAR(64) NULL | |
| `gesture_confirmed_at_ms` | BIGINT NULL | 제스처 확정 시각 |
| `command_published_at_ms` | BIGINT | 명령 발행 시각 |
| `ack_received_at_ms` | BIGINT NULL | ACK 수신 시각 |
| `latency_ms` | BIGINT NULL | 확정(또는 발행) → ACK 수신, 0 이상 |

### help_requests

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `request_id` | VARCHAR(64) PK | |
| `correlation_id` | VARCHAR(64) | |
| `user_id` | FK users (CASCADE) | 도움을 요청한 사용자 |
| `source` | VARCHAR(16) | `GESTURE` / `WEB` |
| `status` | VARCHAR(16) | `CREATED` → `CONFIRMED` → `COMPLETED` |
| `created_at_ms` | BIGINT | |
| `confirmed_at_ms`, `confirmed_by` | BIGINT NULL, FK users NULL | 보호자 확인 |
| `completed_at_ms`, `completed_by` | BIGINT NULL, FK users NULL | 처리 완료 |

### gesture_mappings

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `gesture` | VARCHAR(16) PK | `THUMB_UP` / `THUMB_DOWN` / `HELP` |
| `action` | VARCHAR(8) | `ON` / `OFF` / `HELP` |
| `enabled` | BOOLEAN | 꺼져 있으면 해당 제스처로 명령을 만들지 않음 |
| `updated_at_ms` | BIGINT | |

서버 시작 시 없으면 기본값(엄지 올림=ON, 엄지 내림=OFF, HELP=도움 요청)을 넣는다.

## 보존 기간 (SAD 5.2)

`CONTROL_EVENT_RETENTION_DAYS`, `HELP_REQUEST_RETENTION_DAYS`(일)를 설정하면 서버가 1시간마다 정리한다.

- 제어 이력: `PENDING`이 아닌 기록 중 발행 시각이 기간보다 오래된 것
- 도움 요청: `COMPLETED`된 요청 중 생성 시각이 기간보다 오래된 것(처리 중인 요청은 지우지 않음)

비워 두면 지우지 않는다.

## 아직 정하지 않은 것

- HELP 제스처 요청자를 카메라(edge_id)와 방을 연결해 정할지. 지금은 방 사용자 기준이다.
- 마이그레이션 도구(Alembic) 도입 시점.
