# CloudAIoT

AI 기반 손동작 인식 비언어 의사소통 AIoT 시스템의 목표 구조, 역할 분담 및 협업 기준을 정리한다.

> 이 문서는 목표 설계와 개발 책임을 정의한다. 디렉토리나 스켈레톤 파일이 존재하더라도 해당 기능의 구현 완료를 의미하지 않는다.

## 핵심 개발 문서

- [공통 인터페이스 규격 v1.0](docs/interfaces/common-interface-spec-v1.0.md): Edge–AI, AI–웹, AI–MQTT 규격과 담당별 기준 파일
- [협업 가이드](CONTRIBUTING.md): Issue, 브랜치, 커밋, Pull Request 절차

## 디렉토리 구조도

## 1. 전체 디렉토리 구조도

> 아래 구조는 Docker 환경과 5명의 역할 분담을 반영한 목표 디렉토리 구조이다.
>

```
CloudAiot-/
│
├── edge/                                      # [엣지 담당] Raspberry Pi 프로그램
│   ├── __init__.py                            # edge Python 패키지 선언
│   ├── main.py                                # 엣지 에이전트 실행 진입점
│   ├── camera.py                              # 카메라 영상 프레임 수집
│   ├── frame_encoder.py                       # 해상도 조정 및 JPEG 인코딩
│   ├── websocket_client.py                    # 서버 전송 및 자동 재접속
│   ├── metrics.py                             # FPS와 영상 전송 지연 측정
│   ├── config.py                              # 엣지 설정 파일 로딩
│   ├── config.example.yaml                    # 카메라·서버 연결 설정 예시
│   ├── requirements.txt                       # 엣지 Python 라이브러리
│   └── README.md                              # Raspberry Pi 설치·실행 안내
│
├── server/                                    # AI·의도 판단·웹 API 서버
│   ├── __init__.py                            # server Python 패키지 선언
│   ├── app.py                                 # FastAPI 애플리케이션 진입점
│   ├── config.py                              # 서버 환경설정 로딩
│   ├── config.example.yaml                    # 서버 설정 예시
│   ├── requirements.txt                       # 서버 Python 라이브러리
│   ├── Dockerfile                             # FastAPI·AI 서버 이미지 생성
│   ├── .dockerignore                          # 서버 이미지에서 제외할 파일
│   ├── README.md                              # 서버 설치·실행 안내
│   │
│   ├── api/                                   # [웹 담당] REST API·WebSocket
│   │   ├── __init__.py                        # API 패키지 선언
│   │   ├── auth.py                            # 로그인 및 JWT 발급 API
│   │   ├── rooms.py                           # 방 등록·조회·수정 API
│   │   ├── devices.py                         # 기기·위치·방향 영역 API
│   │   ├── help_requests.py                   # 도움 요청 관리 API
│   │   ├── control_events.py                  # 기기 제어 이력 API
│   │   ├── websocket.py                       # 실시간 상태·알림 전송
│   │   └── health.py                          # 서버 상태 확인 API
│   │
│   ├── vision/                                # [AI 담당 A] 손동작 인식
│   │   ├── __init__.py                        # 영상 인식 패키지 선언
│   │   ├── hand_detector.py                   # MediaPipe Hands 실행
│   │   ├── landmark_processor.py              # 21개 손 랜드마크 전처리
│   │   ├── pointing_detector.py               # 검지 포인팅 방향 계산
│   │   ├── gesture_rules.py                   # 엄지·도움 요청 제스처 판정
│   │   └── stability_checker.py               # 연속 프레임·유지시간 검사
│   │
│   ├── intent/                                # [AI 담당 B] 의도 판단
│   │   ├── __init__.py                        # 의도 판단 패키지 선언
│   │   ├── engine.py                          # 최종 사용자 의도 결정
│   │   ├── state_machine.py                   # 선택·명령·취소 상태 관리
│   │   ├── device_matcher.py                  # 포인팅과 기기 영역 매칭
│   │   ├── parameters.py                      # 유지시간·허용 각도 관리
│   │   └── latency_tracker.py                 # 의도 판단 지연시간 측정
│   │
│   ├── iot/                                   # [통합 담당] MQTT 기기 제어
│   │   ├── __init__.py                        # IoT 패키지 선언
│   │   ├── mqtt_client.py                     # MQTT 연결·발행·구독
│   │   ├── command_service.py                 # command_id와 명령 생성
│   │   ├── ack_handler.py                     # 기기 ACK 처리
│   │   └── device_state_handler.py            # 기기 상태·연결 여부 관리
│   │
│   ├── services/                              # [웹 담당] 응용 서비스 로직
│   │   ├── __init__.py                        # 서비스 패키지 선언
│   │   ├── room_service.py                    # 방 관리 로직
│   │   ├── device_service.py                  # 기기·위치 관리 로직
│   │   ├── user_service.py                    # 사용자·보호자 관리 로직
│   │   ├── help_service.py                    # 도움 요청 처리 로직
│   │   └── control_event_service.py           # 기기 제어 이력 관리
│   │
│   ├── db/                                    # [웹 담당] PostgreSQL 계층
│   │   ├── __init__.py                        # 데이터베이스 패키지 선언
│   │   ├── session.py                         # DB 연결·세션 관리
│   │   ├── models.py                          # DB 테이블 모델 정의
│   │   ├── repositories.py                    # 데이터 조회·저장 처리
│   │   └── migrations/                        # DB 구조 변경 이력
│   │       ├── README.md                       # 마이그레이션 사용 안내
│   │       └── initial_schema.sql              # 최초 테이블 생성 스크립트
│   │
│   └── security/                              # [웹 담당] 인증·인가
│       ├── __init__.py                        # 보안 패키지 선언
│       ├── authentication.py                  # 계정·비밀번호 검증
│       ├── jwt.py                             # JWT 생성·검증
│       └── permissions.py                     # 역할별 접근 권한 검사
│
├── web/                                       # [웹 담당] React 대시보드
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx                  # 로그인 화면
│   │   │   ├── DashboardPage.tsx              # 통합 현황 화면
│   │   │   ├── RoomMappingPage.tsx            # 방·기기 위치 등록 화면
│   │   │   └── HelpRequestPage.tsx            # 도움 요청 확인 화면
│   │   │
│   │   ├── components/
│   │   │   ├── RoomMap.tsx                    # 방과 기기 위치 표시
│   │   │   ├── DeviceCard.tsx                 # 기기 정보 카드
│   │   │   ├── DeviceStatus.tsx               # 기기 상태 표시
│   │   │   └── HelpRequestList.tsx            # 도움 요청 목록
│   │   │
│   │   ├── api/
│   │   │   └── client.ts                      # FastAPI REST API 호출
│   │   │
│   │   ├── websocket/
│   │   │   └── eventClient.ts                 # 실시간 상태·알림 수신
│   │   │
│   │   ├── types/
│   │   │   └── index.ts                       # 웹 공통 자료형
│   │   │
│   │   ├── App.tsx                            # 화면 구성과 라우팅
│   │   ├── main.tsx                           # React 실행 진입점
│   │   └── index.css                          # 공통 화면 스타일
│   │
│   ├── index.html                             # React 기본 HTML
│   ├── package.json                           # Node.js 패키지·실행 명령
│   ├── tsconfig.json                          # TypeScript 설정
│   ├── vite.config.ts                         # Vite 개발·빌드 설정
│   ├── Dockerfile                             # React 빌드·Nginx 이미지 생성
│   ├── .dockerignore                          # 웹 이미지 제외 파일
│   └── README.md                              # 웹 설치·실행 안내
│
├── firmware/                                  # [통합 담당] ESP32 펌웨어
│   ├── src/
│   │   ├── main.cpp                           # 펌웨어 실행 진입점
│   │   ├── mqtt_handler.cpp                   # MQTT 명령·ACK 처리
│   │   └── relay_controller.cpp               # 릴레이 ON/OFF 제어
│   │
│   ├── include/
│   │   ├── mqtt_handler.h                     # MQTT 모듈 선언
│   │   ├── relay_controller.h                 # 릴레이 모듈 선언
│   │   └── config.example.h                   # Wi-Fi·MQTT 설정 예시
│   │
│   ├── platformio.ini                         # ESP32 빌드 환경 설정
│   └── README.md                              # 펌웨어 설치·업로드 안내
│
├── shared/                                    # [통합 담당] 공통 인터페이스
│   ├── __init__.py                            # shared Python 패키지 선언
│   ├── types.py                               # Python 공통 자료형
│   ├── mqtt_topics.py                         # MQTT Topic 생성 규칙
│   ├── constants.py                           # 공통 상태·이벤트 상수
│   ├── errors.py                              # 공통 오류 코드
│   │
│   ├── schemas/
│   │   ├── frame-metadata.schema.json         # 영상 프레임 정보 규격
│   │   ├── gesture-result.schema.json         # 제스처 인식 결과 규격
│   │   ├── intent-result.schema.json          # 최종 의도 결과 규격
│   │   ├── mqtt-command.schema.json           # MQTT 제어 명령 규격
│   │   ├── mqtt-ack.schema.json               # MQTT 실행 응답 규격
│   │   └── help-request.schema.json           # 도움 요청 데이터 규격
│   │
│   └── README.md                              # 인터페이스 변경 규칙
│
├── deploy/                                    # [통합 담당] 컨테이너 세부 설정
│   ├── nginx/
│   │   └── default.conf                       # 웹·API·WebSocket 전달 설정
│   │
│   ├── mosquitto/
│   │   ├── mosquitto.conf                     # MQTT Broker 실행 설정
│   │   ├── acl.example                        # MQTT Topic 접근 권한 예시
│   │   └── passwd.example                     # MQTT 계정 형식 예시
│   │
│   ├── postgres/
│   │   └── init.sql                           # PostgreSQL 초기 설정
│   │
│   └── README.md                              # Docker 실행·관리 안내
│
├── tests/                                     # 담당자별 자동 테스트
│   ├── edge/
│   │   ├── test_camera.py                     # 카메라 입력 테스트
│   │   ├── test_frame_encoder.py              # JPEG 인코딩 테스트
│   │   └── test_websocket_client.py           # 전송·재접속 테스트
│   │
│   ├── vision/
│   │   ├── test_hand_detector.py              # 손 검출 테스트
│   │   ├── test_pointing_detector.py          # 포인팅 계산 테스트
│   │   ├── test_gesture_rules.py              # 제스처 규칙 테스트
│   │   └── test_stability_checker.py          # 유지시간 검사 테스트
│   │
│   ├── intent/
│   │   ├── test_device_matcher.py             # 기기 영역 매칭 테스트
│   │   ├── test_state_machine.py              # 상태 전이 테스트
│   │   └── test_intent_engine.py              # 최종 의도 판단 테스트
│   │
│   ├── server/
│   │   ├── test_auth_api.py                   # 인증 API 테스트
│   │   ├── test_device_api.py                 # 기기 API 테스트
│   │   └── test_help_api.py                   # 도움 요청 API 테스트
│   │
│   ├── contract/
│   │   ├── test_frame_contract.py             # 영상 전송 규격 테스트
│   │   ├── test_intent_contract.py            # AI 결과 규격 테스트
│   │   └── test_mqtt_contract.py              # MQTT 메시지 규격 테스트
│   │
│   ├── integration/
│   │   ├── test_video_pipeline.py             # Edge→AI 연결 테스트
│   │   ├── test_control_pipeline.py           # AI→MQTT 연결 테스트
│   │   └── test_web_pipeline.py               # 서버→웹 연결 테스트
│   │
│   └── e2e/
│       └── test_device_control_flow.py         # 전체 기기 제어 흐름 테스트
│
├── docs/                                      # 프로젝트 설계 문서
│   ├── architecture/
│   │   ├── SAD.md                             # 소프트웨어 아키텍처 문서
│   │   └── directory-structure.md             # 디렉토리 구조 문서
│   │
│   ├── api-spec.md                            # REST API 명세
│   ├── websocket-spec.md                      # WebSocket 전송 명세
│   ├── mqtt-spec.md                           # MQTT Topic·페이로드 명세
│   ├── database-spec.md                       # 데이터베이스 명세
│   └── project-status.md                      # 구현 상태·미결정 사항
│
├── scripts/                                   # 개발·통합 보조 도구
│   ├── __init__.py                            # scripts 패키지 선언
│   ├── local_demo.py                          # 로컬 통합 데모 실행
│   ├── start_development.py                   # 개발 서비스 일괄 실행
│   └── seed_demo_data.py                      # 데모용 방·기기 데이터 생성
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml                             # PR 자동 테스트
│   │
│   ├── ISSUE_TEMPLATE/
│   │   ├── task.md                            # 개발 작업 Issue 양식
│   │   └── bug.md                             # 오류 보고 Issue 양식
│   │
│   ├── CODEOWNERS                             # 디렉토리별 검토 담당자
│   └── pull_request_template.md               # Pull Request 작성 양식
│
├── docker-compose.yml                         # 전체 컨테이너 통합 실행
├── .env.example                               # DB·JWT·MQTT 환경변수 예시
├── .dockerignore                              # 공통 Docker 제외 파일
├── .editorconfig                              # 공통 편집기 형식 설정
├── .gitignore                                 # Git 제외 파일 설정
├── .python-version                            # Python 기준 버전
├── pyproject.toml                             # Python 프로젝트·테스트 설정
├── requirements.txt                           # 공통 Python 라이브러리
├── requirements-dev.txt                       # 개발·테스트 라이브러리
├── CONTRIBUTING.md                            # 브랜치·PR 협업 규칙
└── README.md                                  # 프로젝트 전체 설명
```

---

## 2. 디렉토리 및 역할 설명

### 역할별 담당 범위

| 역할 | 담당 디렉토리 | 주요 책임 |  |
| --- | --- | --- | --- |
| 엣지 담당 | `edge/`, `tests/edge/` | 카메라 수집, JPEG 인코딩, WebSocket 전송, 재접속, 전송 성능 측정 |  |
| AI 담당 A | `server/vision/`, `tests/vision/` | MediaPipe Hands, 랜드마크, 포인팅, 제스처 판정 |  |
| AI 담당 B | `server/intent/`, `tests/intent/` | 기기 매칭, 상태머신, 의도 확정, 안전 취소, 지연 측정 |  |
| 웹·응용 서버 담당 | `server/api/`, `server/services/`, `server/db/`, `server/security/`, `web/`, `tests/server/` | FastAPI, React, PostgreSQL, 로그인, 방·기기·도움 요청 관리 |  |
| 인터페이스·통합 담당 | `server/iot/`, `firmware/`, `shared/`, `deploy/`, 통합 테스트 | MQTT, ESP32, 공통 규격, Docker, Nginx, Mosquitto, 전체 통합 |  |

### 핵심 디렉토리 설명

| 디렉토리 | 설명 |
| --- | --- |
| `edge/` | Raspberry Pi에서 영상을 수집·인코딩하고 AI 서버로 전송한다. |
| `server/vision/` | 손 랜드마크를 검출하고 포인팅과 제스처를 판정한다. |
| `server/intent/` | 포인팅 대상과 명령 제스처를 조합하여 최종 의도를 결정한다. |
| `server/iot/` | MQTT 명령을 발행하고 ESP32의 ACK와 상태를 처리한다. |
| `server/api/` | 웹에서 사용하는 REST API와 WebSocket을 제공한다. |
| `server/services/` | 방·기기·사용자·도움 요청의 응용 로직을 처리한다. |
| `server/db/` | PostgreSQL 연결과 데이터 저장을 관리한다. |
| `server/security/` | JWT 로그인과 역할별 접근 권한을 관리한다. |
| `web/` | 방·기기 매핑, 상태 확인, 도움 요청 기능을 제공한다. |
| `firmware/` | ESP32가 MQTT 명령을 받아 릴레이를 제어하도록 한다. |
| `shared/` | 파트 간 데이터 형식과 MQTT Topic 규칙을 관리한다. |
| `deploy/` | Nginx·Mosquitto·PostgreSQL의 실행 설정을 관리한다. |
| `tests/` | 단위·규격·통합·전체 흐름 테스트를 관리한다. |
| `docs/` | API·MQTT·DB·아키텍처 명세를 관리한다. |
| `scripts/` | 로컬 데모와 개발 환경 실행을 지원한다. |

### Docker 구성

```
docker-compose.yml
│
├── nginx                         # React 웹 제공 및 요청 전달
├── api                           # FastAPI·MediaPipe·의도 판단
├── postgres                      # 사용자·기기·이력 저장
└── mosquitto                     # MQTT 명령·ACK·상태 중계
```

Raspberry Pi의 `edge/`와 ESP32의 `firmware/`는 Docker 컨테이너로 실행하지 않는다.

```
Raspberry Pi
    │ WebSocket
    ▼
Nginx → FastAPI·AI → Mosquitto → ESP32·릴레이
              │
              └──────────────→ PostgreSQL
```

### 공통 작업 원칙

- 각 담당자는 자신의 기능과 단위 테스트를 함께 구현한다.
- 공통 인터페이스는 `shared/`를 기준으로 관리한다.
- 인터페이스 변경은 송신 담당자, 수신 담당자, 통합 담당자가 합의한다.
- 실제 비밀번호와 인증정보는 GitHub에 올리지 않는다.
- 설정 파일은 `.env.example`과 `config.example.*` 형태로만 공유한다.

---

## 3. 역할별 브랜치 구성

### 브랜치 구조

```
main                              # 전체 기능이 정상 동작하는 안정 브랜치
│
└── integration                   # 모듈 통합 및 전체 테스트 브랜치
    │
    ├── edge                      # 엣지 담당 개인 브랜치
    ├── ai-vision                 # AI 담당 A 개인 브랜치
    ├── ai-intent                 # AI 담당 B 개인 브랜치
    └── web-app                   # 웹·응용 서버 담당 개인 브랜치
```

`integration`은 통합 담당자의 개인 작업 브랜치이면서 모든 모듈을 합치는 통합 브랜치로 사용한다.

### 브랜치별 담당

| 브랜치 | 담당 내용 |
| --- | --- |
| `edge` | Raspberry Pi 카메라, 인코딩, WebSocket 전송 |
| `ai-vision` | MediaPipe Hands, 랜드마크, 포인팅, 제스처 판정 |
| `ai-intent` | 기기 매칭, 상태머신, 명령 확정, 안전 취소 |
| `web-app` | FastAPI, React, PostgreSQL, 인증, 도움 요청 |
| `integration` | 공통 인터페이스, MQTT, ESP32, Docker, 모듈 통합 |
| `main` | 통합 테스트가 완료된 실행 가능한 안정 버전 |

### 개발 및 통합 절차

```
1. 각 담당자는 자신의 브랜치에서 기능을 구현한다.
2. 각 담당자는 자신의 기능에 대한 단위 테스트를 수행한다.
3. 일정 범위의 기능이 완료되면 integration 대상 Pull Request를 생성한다.
4. 통합 담당자는 코드 충돌과 공통 인터페이스 호환성을 확인한다.
5. 통합 담당자는 승인된 코드를 integration 브랜치에 병합한다.
6. integration 브랜치에서 Docker 기반 통합 테스트를 수행한다.
7. 영상 입력부터 기기 동작까지 전체 흐름을 테스트한다.
8. 전체 기능이 정상적으로 실행될 때만 integration을 main에 병합한다.
```

### 브랜치 운영 규칙

- 각 담당자는 자신의 역할 브랜치에만 직접 코드를 올린다.
- 다른 담당자의 디렉토리를 수정해야 할 때는 해당 담당자와 먼저 합의한다.
- `shared/` 변경은 통합 담당자의 검토를 받아야 한다.
- 개인 브랜치에서 `main`으로 직접 병합하지 않는다.
- 미완성 기능은 `integration` 또는 `main`에 병합하지 않는다.
- `main` 병합은 통합 담당자가 전체 테스트를 완료한 후 수행한다.
- `main`은 항상 시연 가능한 상태로 유지한다.

## 역할 분담

#### 1. 엣지 담당

- Raspberry Pi 개발 환경 구성
- 카메라 영상 수집
- 해상도 조정 및 JPEG 인코딩
- WebSocket을 통한 서버 전송
- 연결 중단 시 자동 재접속
- 영상 전송 속도와 지연시간 측정

#### 2. AI·의도 판단 담당 2명

- AI 담당 A
    - MediaPipe Hands 연동
    - 21개 손 랜드마크 추출
    - 검지 포인팅, 엄지 올림·내림, 도움 요청 제스처 판정
    - 연속 프레임 및 유지시간 검사
- AI 담당 B
    - 포인팅 방향과 기기 영역 매칭
    - 대상 선택 상태머신
    - ON/OFF 의도 확정 및 안전 취소
    - 제스처 인식부터 명령 확정까지의 지연시간 측정

#### 3. 웹·응용 서버 담당

- React 통합 대시보드
- FastAPI REST API
- 방·기기·위치 영역 등록
- 기기 상태와 제어 이력 표시
- 도움 요청 생성·확인·처리
- PostgreSQL 데이터 관리
- JWT 로그인과 역할별 권한

1명이 맡기에는 다소 넓은 범위.
따라서 인증이나 세밀한 UI보다 방·기기 매핑과 도움 요청 같은 핵심 기능을 우선 구현

#### 4. 인터페이스·통합 담당

각 파트 사이의 연결 규격을 관리 및 통합하는 역할

- `shared/` 공통 데이터 형식 관리
- Edge → AI 영상 전송 규격 확정
- AI → MQTT 명령 규격 확정
- MQTT Topic과 `command_id`, ACK 규격 관리
- ESP32·릴레이 제어 구현
- Docker Compose, Mosquitto, Nginx 설정
- 각 모듈을 연결한 통합 테스트
- GitHub PR 충돌과 버전 호환 확인

| 인원 | 역할 | 주요 담당 |
| --- | --- | --- |
| 1명 | 엣지 담당 | Raspberry Pi 4B, 카메라, JPEG 인코딩, WebSocket 전송·재접속 |
| 2명 | AI·의도 판단 | MediaPipe Hands, 규칙 기반 제스처, 2차원 포인팅, 대상 매칭, 상태머신 |
| 1명 | 웹·응용 서버 | React 화면, FastAPI API, PostgreSQL, 사용자·기기·도움 요청 관리 |
| 1명 | 인터페이스·통합 | 공통 메시지 규격, MQTT, ESP32·릴레이, Docker Compose, 전체 통합 테스트 |

각 담당자는 자신의 모듈에 대한 단위 테스트까지 책임진다.
통합 담당자는 공통 규격과 모듈 간 연결 테스트를 책임진다.
인터페이스가 바뀌면 송신자·수신자·통합 담당자 세 사람이 합의한다.
