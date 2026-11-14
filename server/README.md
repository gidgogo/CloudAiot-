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
설정 환경변수는 `server/config.py`(`Settings`)와 루트 `.env.example`에 정리되어 있습니다.

영상 분석 모듈을 개발할 때 추가 의존성을 설치합니다.

```bash
python -m pip install -e ".[server,vision]"
```

## 웹·응용 서버 부분 (담당: 웹·응용 서버)

| 위치 | 내용 |
| --- | --- |
파일은 루트 README의 디렉토리 구조도(계획표)와 같게 두고, 계획표에 없던 기능은 가장 가까운 파일에 넣었습니다.

| 위치 | 내용 |
| --- | --- |
| `app.py` | 앱 생성(`create_app`), CORS, 공통 오류 응답, 보존 기간 정리 작업 |
| `config.py` | YAML 설정(`load_config`)과 환경변수 설정(`Settings`) |
| `api/__init__.py` | 요청 본문 기본 모델, `ok()` 응답 형식, 공통 의존성(DB 세션·로그인 사용자·서비스) |
| `api/auth.py` | 로그인·로그아웃·비밀번호 변경, 사용자·보호자 연결 관리(`users_router`) |
| `api/devices.py` | 기기·위치·방향 영역, 제스처·명령 매핑(`mappings_router`) |
| `api/websocket.py` | `/ws/v1/events` 연결과 실시간 이벤트 허브(`EventHub`) |
| `services/__init__.py` | 웹 오류 코드(`web_error`) |
| `services/device_service.py` | 기기 관리, 제스처·명령 매핑(`GestureMappingService`) |
| `services/control_event_service.py` | 제어 이력, 보존 기간 정리(`purge_expired`) |
| `db/models.py` | SQLAlchemy 모델, PostgreSQL DDL 생성(`python -m server.db.models`) |
| `db/session.py` | DB 연결·세션, 시작 시 기본 데이터(`bootstrap`: 테이블·기본 매핑·최초 관리자) |
| `security/jwt.py` | JWT Cookie, CSRF·Origin 검사 |
| `security/authentication.py`, `permissions.py` | 비밀번호(bcrypt)·로그인 잠금, 역할 권한 |

다른 모듈이 쓰는 연결 지점은 `docs/api-spec.md`, `docs/websocket-spec.md`에 정리했습니다.

- IoT: `ControlEventService.record_command / record_ack / mark_timeout`, `DeviceService.update_state / update_connection_status`
- 의도 판단: `DeviceService.pointing_regions()`, `GestureMappingService.action_for()`, `HelpService.create_from_gesture()`
- 실시간 이벤트: `app.state.events.publish(event_type, data, correlation_id, audience_user_id=None)`

## 테스트

```bash
python -m pytest -q tests/server tests/integration/test_web_pipeline.py
TEST_DATABASE_URL="postgresql+psycopg://user:pw@localhost:5432/cloudaiot_test" python -m pytest -q tests/server tests/integration/test_web_pipeline.py
```

두 번째 명령은 실제 PostgreSQL에서 같은 테스트를 돌립니다(테스트마다 테이블을 지우므로 빈 테스트용 DB 사용).

공통 fixture(앱·로그인 클라이언트 등)는 `tests/server/test_auth_api.py` 앞부분에 있고, 다른 테스트 파일은 그것을 import해서 씁니다(계획표에 conftest.py가 없어서).

## 그 밖의 코드

- `vision/`, `intent/`, `iot/`: 각 담당자의 모듈(규격 v1 스켈레톤)
- `intent/fusion.py`, `vision/gaze.py`, `notifications/`, `config.py`의 `load_config`: 이전 로컬 데모(`scripts/local_demo.py`)용 코드
