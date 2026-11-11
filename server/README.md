# AI·응용 서버 (FastAPI)

손동작 인식(`vision/`), 의도 판단(`intent/`), MQTT 기기 제어(`iot/`)와
웹 대시보드용 API(`api/`, `services/`, `db/`, `security/`)를 하나의 FastAPI 애플리케이션으로 실행합니다.
라즈베리파이의 카메라나 GPIO를 직접 열지 않습니다.

## 설치와 실행

Python 3.11 가상환경을 활성화하고 저장소 루트에서 실행합니다.

```bash
python -m pip install -r server/requirements.txt
python -m scripts.seed_demo_data --password demo-pass-123   # 데모 계정·방·기기
python -m uvicorn server.app:app --reload --host 127.0.0.1
```

API 문서는 <http://127.0.0.1:8000/docs>에서 확인합니다. `DATABASE_URL`이 없으면 `./cloudaiot-dev.db`(SQLite)를 씁니다.
설정 환경변수는 `server/settings.py`와 루트 `.env.example`에 정리되어 있습니다.

영상 분석 모듈을 개발할 때 추가 의존성을 설치합니다.

```bash
python -m pip install -e ".[server,vision]"
```

## 웹·응용 서버 부분 (담당: 웹·응용 서버)

| 위치 | 내용 |
| --- | --- |
| `app.py` | 앱 생성(`create_app`), CORS, 시작 시 기본 데이터, 보존 기간 정리 작업 |
| `settings.py` | 환경변수 설정 |
| `bootstrap.py` | 테이블 생성, 기본 제스처 매핑, 최초 관리자 |
| `api/` | REST API·WebSocket(`/ws/v1/events`), 요청 검증, 오류 형식 |
| `services/` | 방·기기·사용자·도움 요청·제어 이력·제스처 매핑·보존 기간, 실시간 이벤트 허브 |
| `db/` | SQLAlchemy 모델, 리포지토리, PostgreSQL DDL 생성(`python -m server.db.schema_sql`) |
| `security/` | 비밀번호(bcrypt), JWT Cookie, CSRF·Origin 검사, 역할 권한 |

다른 모듈이 쓰는 연결 지점은 `docs/api-spec.md`, `docs/websocket-spec.md`에 정리했습니다.

- IoT: `ControlEventService.record_command / record_ack / mark_timeout`, `DeviceService.update_state / update_connection_status`
- 의도 판단: `DeviceService.pointing_regions()`, `GestureMappingService.action_for()`, `HelpService.create_from_gesture()`
- 실시간 이벤트: `app.state.events.publish(event_type, data, correlation_id, audience_user_id=None)`

## 테스트

```bash
python -m pytest -q tests/server
TEST_DATABASE_URL="postgresql+psycopg://user:pw@localhost:5432/cloudaiot_test" python -m pytest -q tests/server
```

두 번째 명령은 실제 PostgreSQL에서 같은 테스트를 돌립니다(테스트마다 테이블을 지우므로 빈 테스트용 DB 사용).

## 그 밖의 코드

- `vision/`, `intent/`, `iot/`: 각 담당자의 모듈(규격 v1 스켈레톤)
- `intent/fusion.py`, `vision/gaze.py`, `notifications/`, `config.py`: 이전 로컬 데모(`scripts/local_demo.py`)용 코드
