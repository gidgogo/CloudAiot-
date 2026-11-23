# SAD v1.0 → v1.1 변경 내역

- 대상: `SAD_v1.0.docx`(2026-10-24, 초판 확정) → `SAD_v1.1.docx`(2026-11-23, 팀 검토 전)
- 기준: main 브랜치 코드(2026-11-23), 공통 인터페이스 규격 v1.0, 팀 변경 사항(ESP32 미사용, 손동작 지정 변경)
- 원본 `SAD_v1.0.docx`는 수정하지 않았다.
- 손동작 변경(OPEN_PALM·FIST·V_SIGN)은 `feat/change-gesture` 브랜치에서 병합될 예정이므로, SAD v1.1에는 확정·적용된 내용으로 적었다.

### 표기 원칙
- **상태값·제스처·이벤트·파라미터:** `영문(한국어)` 형식. 예: `CREATED(요청 발생)`, `OPEN_PALM(손바닥 펴기)`, `device.selected(기기 선택)`, `min_hold_ms (최소 유지 시간)`
- **그대로 쓰는 영어:** 파일 경로(`server/intent/` 등), 클래스·모듈 이름(`IntentEngine`, `pi_led_agent` 등), 환경변수·쿠키·헤더 이름, 엔드포인트, MQTT 토픽. 처음 나올 때 한국어 설명을 괄호로 붙였다.
- **시간 단위:** 코드와 같은 단위로 썼다(500 ms, 3000 ms, 300초, 1800초).
- **그림:** 한국어 이름을 기본으로 하고 영문을 병기했다. 그림 1은 모듈 상자에 클래스·모듈 이름(`GesturePipeline`, `IntentEngine`, `IntentDispatcher`, `MqttBridge`, `UserService` 등)을, 그림 2는 상태·제스처·취소 사유를, 그림 4는 컨테이너·프로그램 이름(`nginx`, `api`, `edge.main`, `pi_led_agent` 등)을 함께 적었다.

## 한눈에 보기

| 절 | 변경 정도 | 요약 |
| --- | --- | --- |
| 문서 관리·개정 이력 | 수정·추가 | 버전 v1.1, 수정일, 개정 이력 v1.1 행 |
| 1.2 시스템 범위 | 수정 | FR-03을 Pi 5V LED로, FR-05를 구현 완료로 |
| 1.3 용어 | 수정 6행, 추가 4행 | JWT·처리 상태 등 구체화, correlation_id·LWT·CSRF·Pi LED 에이전트 추가 |
| 2.1 비기능 요구사항 | 변경 없음 | 요구사항 원문이라 유지 |
| 2.2 기술적 제약 | 수정 4항목 | 기술 스택, ESP32 미사용, 통신 방식 |
| 2.3 추적 매트릭스 | 8행 수정 | 담당 컴포넌트에 코드 경로, 대응 방안을 구현 내용으로 |
| 3.1 종합 아키텍처 | 문단 5개 수정, 그림 1 교체 | 실제 데이터 흐름과 엔드포인트 |
| 3.2 아키텍처 패턴 | 1항목 수정 | FrameSessionProcessor·IntentDispatcher 구조 |
| 4.1 서비스 구성 | 12행 수정 | 역할·기술 스택·저장소를 구현 기준으로 |
| 4.2 서비스 간 통신 | 4항목 수정, MQTT 표 전면 수정 | 토픽 v1, status 토픽, 실제 메시지 형식, 이벤트 10종 |
| 4.3 의도 판단 로직 | 문단 수정, 그림 2 교체, 파라미터 표 전면 수정 | 실제 파라미터·취소 사유·새 제스처 |
| 4.4 핵심 시나리오 | 7단계 내용 수정 | 이벤트 이름, 유효시간, 실패 처리 |
| 5.1 DB 전략 | 2항목 수정 | 7개 테이블, `*_ms`, SQLite 개발 모드 |
| 5.2 ERD | 그림 3 교체, 캡션·문단·표 수정 | 실제 스키마와 보존 기간 설정 |
| 6.1 인증·인가 | 2항목, 역할 표 수정 | HttpOnly 쿠키 JWT·CSRF·bcrypt·WebSocket 종료 코드 |
| 6.2 데이터 보안 | 3항목 수정 | TLS·Mosquitto ACL 미적용 사실 명시 |
| 7.1 인프라 | 그림 4 교체, 5항목 수정 | 컨테이너·포트·볼륨, 송출 제어 |
| 8 모니터링·운영 | 6항목 수정 | 재접속 간격, ACK 2초, 측정 항목 |
| 9 ADR | ADR-001~004 일부 수정, ADR-006~008 추가 | 웹 인증, 도움 요청 분리, Pi LED 제어부 |
| 10 부록 | 관련 문서 수정, 구현 현황 표 추가, 미결 사항 전면 교체 | |

---

## 문서 관리 (Document Control)

| 항목 | v1.0 | v1.1 |
| --- | --- | --- |
| 문서 버전 | v1.0 | v1.1 |
| 최종 수정일 | 2026-10-24 | 2026-11-23 |

## 개정 이력 (Revision History)

- **추가:** v1.1 행 (2026-11-23, 정유경)
  - 내용: 구현 코드(main) 기준 갱신. 공통 인터페이스 규격 v1.0(MQTT 토픽 v1과 status 토픽, 엣지 영상 WebSocket, 웹 실시간 이벤트 10종), 의도 판단 파라미터와 상태 전이, 쿠키 기반 JWT·CSRF 인증, DB 스키마, ESP32·릴레이 대신 Raspberry Pi 5V LED 제어부, 손동작 지정 변경(OPEN_PALM=ON, FIST=OFF, V_SIGN=HELP), ADR-006~008 추가, 구현 현황·미결 사항 갱신, 그림 1~4 재작성

---

## 1. 개요

### 1.1 문서 목적
- 변경 없음

### 1.2 시스템 범위

| 항목 | v1.0 | v1.1 |
| --- | --- | --- |
| FR-03 | MQTT 기반 조명·선풍기 등 IoT 기기 제어와 제어 결과 확인 | MQTT 기반 IoT 기기 제어와 제어 결과 확인. **ESP32·릴레이 모듈 없이 Raspberry Pi에 연결한 5V LED의 전원을 켜고 끄는 방식** |
| FR-05 | 도움 요청 알림을 **낮은 우선순위의 선택 구현 범위**로 포함 | HELP 제스처 또는 웹 버튼으로 요청하면 알림·시간·처리 상태를 기록하는 기능을 포함. **v1.0의 선택 범위였으나 현재 구현됨** |

- 제외 범위(Out-of-Scope): 변경 없음

### 1.3 용어 및 약어

**수정한 행**

| 용어 | 바뀐 내용 |
| --- | --- |
| AI 서버 | MediaPipe Hands → MediaPipe Hand Landmarker. 웹 API와 MQTT 연동도 같은 FastAPI 서버에서 수행함을 추가 |
| IoT 기기 제어부 | 현재 시연은 Pi LED 에이전트(`pi_led_agent`)라는 설명 추가 |
| 처리 상태 | "요청 발생, 보호자 확인, 처리 완료 등" → CREATED(요청 발생) → CONFIRMED(보호자 확인) → COMPLETED(처리 완료) 순서로만 변경됨 |
| Docker Compose | 컨테이너 목록에 Nginx 추가 |
| JWT | HS256 서명, HttpOnly 쿠키(`aiot_access_token`)로만 전달함을 추가 |
| RBAC | 역할을 USER(사용자)·GUARDIAN(보호자)·ADMIN(관리자)로 명시 |

**추가한 행**

| 용어 | 정의 요약 |
| --- | --- |
| correlation_id | 영상 프레임 → 제스처 → 의도 → MQTT 명령 → ACK·도움 요청까지 하나의 동작을 추적하는 UUID v4 |
| LWT | 기기가 비정상 종료되면 브로커가 대신 발행하는 메시지. status 토픽에 OFFLINE(연결 끊김)을 retain으로 발행 |
| CSRF | 쿠키 인증이므로 CSRF 토큰 쿠키(`aiot_csrf_token`)와 `X-CSRF-Token` 헤더를 대조해 방어 |
| Pi LED 에이전트 | Raspberry Pi에서 MQTT 명령을 받아 LED를 켜고 끄는 시연용 프로그램(`pi_led_agent`). ESP32·릴레이 대신 사용 |

---

## 2. 아키텍처 목표 및 제약사항

### 2.1 핵심 비기능 요구사항
- 변경 없음 (요구사항 원문이므로 유지하고, 실제 충족 상태는 2.3, 6.2, 8, 10절에 적음)

### 2.2 기술적 제약사항

| 항목 | v1.0 | v1.1 |
| --- | --- | --- |
| 구축 환경 | 서버 구성요소를 Docker Compose로 단일 데스크톱에서 실행 | 컨테이너 4종(Nginx, FastAPI, PostgreSQL, Mosquitto)을 명시하고, 엣지·IoT 제어 프로그램은 컨테이너 밖 Raspberry Pi에서 실행함을 추가 |
| 기술 스택 제약 | Picamera2·OpenCV, MediaPipe Hands, FastAPI, React·TypeScript, PostgreSQL, Mosquitto | MediaPipe Hand Landmarker, FastAPI·Uvicorn, SQLAlchemy, PyJWT·bcrypt, paho-mqtt, React·TypeScript·Vite, PostgreSQL 16, Mosquitto 2. 규칙 판별 기준을 "손가락 관절 각도"로 구체화 |
| IoT 기기 제어 환경 | ESP32 또는 이에 준하는 MCU 사용, 보드·릴레이는 장비 확인 후 확정 | **팀 결정으로 ESP32·릴레이 모듈 사용 안 함.** Raspberry Pi GPIO(BCM 17)의 5V LED 전원을 Pi LED 에이전트로 켜고 끔. 220V 가전 제어는 범위 제외 |
| 기존 시스템 연동 | REST·WebSocket·MQTT로 통신 | 구간별 통신 방식(엣지–서버 WebSocket, 웹–서버 REST·WebSocket, 서버–IoT MQTT)과 `schema_version "1.0"` 준수를 명시 |
| 프로젝트 제약 | | 변경 없음 |

### 2.3 요구사항 추적 매트릭스
8행 모두 "담당 컴포넌트"에 코드 경로를 넣고, "아키텍처 대응 방안"을 구현 내용으로 바꿨다.

| Req | 담당 컴포넌트 (v1.1) | 대응 방안 핵심 변경 |
| --- | --- | --- |
| FR-01 | `edge/`, `server/api/frames.py` | 640×480·10fps JPEG, `/ws/v1/frames`로 메타데이터 → 영상 순서 전송, `frame_ack`(수신 확인), 대기 프레임 1개 |
| FR-02 | `server/vision/`, `server/intent/` | POINTING(검지 포인팅)·OPEN_PALM(손바닥 펴기)·FIST(주먹)·V_SIGN(V자), 6프레임·500 ms 안정성 조건 |
| FR-03 | `server/iot/`, MQTT 브로커, `pi_led_agent/` | command_id(명령 ID)·유효시간 5초, ack·state·status 수신 |
| FR-04 | `server/services/device_service.py`, 의도 판단 | 기기별 각도 범위(min_angle_deg~max_angle_deg), 손목→검지 끝 방향이 한 범위에만 포함되면 선택 |
| FR-05 | `server/services/help_service.py`, 웹 | `help_requests` 저장, help.created(도움 요청 생성)·help.updated(도움 요청 변경) 이벤트, MQTT 미사용 |
| NFR-01 | 의도 판단, IoT 제어, 브로커, 제어부 | `control_events`에 시각·latency_ms 기록, ACK 2초 실패 처리, **실장비 측정 전**임을 명시 |
| NFR-02 | 인식·의도·IoT 제어·제어부 | 3초 제한, 15° 초과 취소, 다섯 가지 cancel_reason(취소 사유), DUPLICATE(중복) 응답 |
| NFR-03 | 엣지, 서버, 브로커, 웹 | 엣지 토큰, 쿠키 기반 JWT·CSRF·RBAC, bcrypt. **TLS·Mosquitto ACL은 기본 배포에 미적용**임을 명시 |

---

## 3. 시스템 아키텍처 개요

### 3.1 종합 아키텍처 구성도

| 문단 | 바뀐 내용 |
| --- | --- |
| 1 (영역 구성) | "초기에는" 삭제 |
| 2 (사용자·엣지) | 640×480·10fps, 엣지 인증 토큰, `/ws/v1/frames`, 메타데이터 → 영상 순서, `frame_ack`의 PROCESSED(정상 처리)·INVALID(형식 오류)·ERROR(처리 오류), 영상을 디스크·DB·로그에 저장하지 않음 |
| 3 (의도 판단·IoT) | 포인팅 = 손목→검지 끝 방향, 기기별 각도 범위, IoT 제어 모듈(`MqttBridge`), command_id·유효시간 5초, ack(실행 결과)·state(현재 상태)·status(연결 상태) 회신, 시연 제어부 = Pi LED 에이전트(`pi_led_agent`) |
| 4 (웹 대시보드) | 역할 USER·GUARDIAN·ADMIN, HELP 제스처 = **V자**, `/ws/v1/events`의 help.created(도움 요청 생성), 관리자 관리 항목 구체화 |
| 5 (향후 이전) | "초기에는" 삭제 |

- **그림 1 교체:** 서버를 처리 흐름(영상 수신 → 손동작 인식 → 의도 판단 → 의도 결과 분배 → IoT 제어)과 서비스 계층·REST API·실시간 이벤트 허브·PostgreSQL로 다시 그림. IoT 영역은 ESP32·릴레이를 빼고 MQTT 브로커 → Pi LED 에이전트 → 5V LED로 바꿈. 엣지 영역에 송출 제어(버튼·LED) 추가.

### 3.2 핵심 아키텍처 패턴
- **아키텍처 스타일:** 엣지 연결마다 `FrameSessionProcessor`(손동작 인식 → 의도 판단)를 두어 카메라별 상태를 따로 관리하고, `IntentDispatcher`(결과 분배)가 웹 알림·도움 요청·MQTT 명령으로 나눈다는 설명 추가. 문장 끝 띄어쓰기 오류("구성한다 .") 수정.
- 채택 사유 3항목: 변경 없음

---

## 4. 컴포넌트 및 서비스 설계

### 4.1 서비스/모듈 구성
12행의 역할·기술 스택·저장소를 모두 구현 기준으로 바꿨다. 저장소 열에는 테이블 이름을 넣었다.

| 모듈 | 주요 변경 |
| --- | --- |
| 엣지 에이전트 | 회전·좌우 반전 정보, `/ws/v1/frames` 전송과 `frame_ack`(수신 확인) 대기, 1→2→4→…→30초 재접속, 버튼·LED·MQTT 송출 켜기/끄기 추가. 스택에 websockets·gpiozero |
| 영상 수신 모듈 | 엣지 토큰 인증, 형식·JPEG(2MB 이하) 검증, edge.connected(엣지 연결)·edge.disconnected(엣지 해제) 이벤트 |
| 손동작 인식 모듈 | 반전·회전 보정, POINTING·OPEN_PALM·FIST·V_SIGN·UNKNOWN(판별 불가) 판별, 스택 MediaPipe Hand Landmarker(`GesturePipeline`) |
| 의도 판단 모듈 | IDLE(대기) ↔ TARGET_SELECTED(대상 선택됨) 상태 관리, OPEN_PALM·FIST로 ON·OFF, 다섯 가지 cancel_reason. 스택 `IntentEngine`·`SelectionStateMachine`, 저장소 "연결별 메모리" |
| 기기·위치 관리 | 웹 배치 좌표(map_x, map_y)와 각도 범위 분리, MQTT state·status로 상태 갱신. 저장소 rooms, devices |
| 제스처·명령 매핑 | 기본 매핑 OPEN_PALM→ON, FIST→OFF, V_SIGN→HELP, 사용 중지된 제스처는 INVALID_GESTURE로 취소. 저장소 gesture_mappings |
| IoT 제어 모듈 | 유효시간 5초, ACK 2초 대기. 스택 paho-mqtt(`MqttBridge`), 저장소 control_events |
| 도움 요청 관리 | 방 거주자(resident_user_id)로 요청자 결정, CREATED → CONFIRMED → COMPLETED(한국어 병기), 본인·보호자·관리자에게만 전달. 스택에 `HelpService`, 저장소 help_requests |
| 사용자·권한 관리 | HttpOnly 쿠키 JWT, CSRF·Origin(요청 출처) 검사, 로그인 실패 제한. 스택 PyJWT(HS256)·bcrypt. 저장소 users, guardian_links |
| MQTT 브로커 | "기기별 Topic 접근 제어" → state·status는 마지막 값을 retain으로 보관. "계정·ACL은 예제만 준비" 추가. 저장소 Docker 볼륨(mosquitto-data) |
| IoT 기기 제어부 | ESP32·PubSubClient·릴레이 → Python·paho-mqtt·gpiozero(`pi_led_agent`)·5V LED, **ESP32·릴레이 미사용**. 검사 항목(형식·device_id·유효시간·command_id 중복·시간 동기화) 추가 |
| 통합 웹 대시보드 | 화면 목록(대시보드·도움 요청·제어 이력·방·기기 설정·사용자·매핑 관리). 추가된 대시보드 UI(요약·실시간 활동, 실시간 제어 패널의 카메라 → 기기 선택 → 제스처 확정 → 명령 전송 → 완료 진행 단계와 손 모양 표시, 사용 가능한 손동작 목록, 효과음·브라우저 알림) 반영. 스택 React 19·Vite·React Router |

### 4.2 서비스 간 통신

| 항목 | 바뀐 내용 |
| --- | --- |
| 영상 전송 | `Authorization: Bearer EDGE_TOKEN`(엣지 인증 토큰)·`X-Edge-ID`(엣지 ID) 헤더, `/ws/v1/frames`, frame_metadata(JSON) → JPEG(최대 2MB), `frame_ack`(수신 확인) 2초, 대기 프레임 1개. WSS는 "현재 미적용"으로 표시 |
| 서버 내부 통신 | 영상 수신 → 손동작 인식(`GesturePipeline`) → 의도 판단(`IntentEngine`) → 결과 분배(`IntentDispatcher`), 0.1초마다 tick(시간 확인) |
| 웹 통신 | `/api/v1`의 공통 응답 형식(`success`/`error`), `/ws/v1/events`의 10종 이벤트를 `영문(한국어)`로 나열. 예: command.completed(명령 완료) |
| IoT 통신 | 토픽에 버전(v1) 포함, state·status만 retain(마지막 값 보관), HELP는 MQTT로 보내지 않음 |

**MQTT 토픽 표 (전면 수정)**

| v1.0 | v1.1 |
| --- | --- |
| `aiot/{home_id}/{device_id}/cmd` | `aiot/v1/{home_id}/{device_id}/cmd` |
| `aiot/{home_id}/{device_id}/ack` | `aiot/v1/{home_id}/{device_id}/ack` |
| `aiot/{home_id}/{device_id}/state` | `aiot/v1/{home_id}/{device_id}/state` |
| `aiot/{home_id}/{device_id}/lwt` | `aiot/v1/{home_id}/{device_id}/status` (연결 상태, 비정상 종료 시 LWT로 OFFLINE) |

- 내용 열: 메시지 예시(JSON)를 규격 v1.0 필드로 바꾸고 한국어 설명을 붙였다. 예: cmd에 `schema_version`, `correlation_id`, `device_id`, `source`, `issued_at_ms`, `expires_at_ms`. ack의 result에 OK·ERROR·EXPIRED·DUPLICATE(성공·오류·만료·중복).

### 4.3 의도 판단 로직
- **본문 문단 전면 수정**
  - 포인팅 벡터: "검지 기준점과 끝점" → 손목(0번) → 검지 끝(8번), 프레임 비율을 반영한 각도(오른쪽 0°, 아래 +90°)
  - 대상 선택: 등록된 각도 범위 중 정확히 하나에 포함될 때 선택. PENDING(선택 대기) 결과와 device.selected(기기 선택) 이벤트로 웹에 표시
  - 명령 확정: 엄지 올림·내림 → **OPEN_PALM(손바닥 펴기)=ON, FIST(주먹)=OFF**, CONFIRMED(확정)
  - 취소: CANCELLED(취소). 사유는 TARGET_NOT_FOUND(기기 없음), AMBIGUOUS_TARGET(범위 겹침), DIRECTION_CHANGED(15° 초과 방향 변경), GESTURE_TIMEOUT(3초 초과), INVALID_GESTURE(사용 중지된 제스처)
  - HELP: **V_SIGN(V자)**, 선택 해제, 5초 동안 다음 HELP를 확정하지 않음
- **그림 2 교체:** IDLE(대기)·TARGET_SELECTED(대상 기기 선택됨) 두 상태와 결과(CONFIRMED 명령 확정, CONFIRMED·HELP 도움 요청 확정, CANCELLED 취소와 사유 5가지)로 다시 그림
- **그림 2 캡션:** "Intent Engine 상태 전이도" → "의도 판단 상태 전이도"
- **파라미터 표 전면 수정** (이름은 코드 필드명에 한국어 병기)

| v1.0 | 값 | v1.1 | 값 |
| --- | --- | --- | --- |
| POINTING_HOLD | 0.8 s | min_stable_frames (연속 검출 프레임) | 6 프레임 |
| COMMAND_HOLD | 0.5 s | min_hold_ms (최소 유지 시간) | 500 ms (모든 제스처 공통) |
| SELECT_TIMEOUT | 3 s | selection_timeout_ms (선택 유지 시간) | 3000 ms (마지막으로 가리킨 때부터, 계속 가리키면 다시 시작) |
| ANGLE_TOLERANCE | ±20° | max_angle_delta_deg (방향 변화 허용 각도) | 15° (선택 후 방향 변화 한도) |
| HELP_HOLD | 1.5 s | help_cooldown_ms (HELP 재확정 간격) | 5000 ms |
| — | — | pointing_region (기기별 포인팅 범위, 추가) | 기기마다 min_angle_deg~max_angle_deg |

### 4.4 핵심 시나리오 흐름

| 단계 | 바뀐 내용 |
| --- | --- |
| 1 | 메타데이터와 JPEG를 `/ws/v1/frames`로 전송 |
| 2 | POINTING(검지 포인팅) 판별, 손목→검지 끝 방향과 연속 프레임 수·유지 시간 계산 |
| 3 | 0.8초 → 6프레임·500 ms, 한 기기 범위에만 포함, PENDING |
| 4 | device.selected(기기 선택) 이벤트를 `/ws/v1/events`로 전달 |
| 5 | 수행 주체를 "손동작 인식·의도 판단 모듈"로, 엄지 → OPEN_PALM(손바닥 펴기, ON)·FIST(주먹, OFF), gesture.confirmed(제스처 확정) |
| 6 | 유효시간 5초, `control_events`에 PENDING(대기) 기록, command.created(명령 생성), 제어부의 유효시간·중복 검사 |
| 7 | command.completed(명령 완료)·device.state_changed(기기 상태 변경), 2초 무응답이나 ERROR(오류)·EXPIRED(만료)면 command.failed(명령 실패) |

---

## 5. 데이터 아키텍처

### 5.1 데이터베이스 전략
- **단일 PostgreSQL:** PostgreSQL 16, 7개 테이블을 `영문(한국어)`로 나열(users(사용자) 등), SQLAlchemy 모델(`server/db/models.py`), 서버 시작 시 테이블·기본 매핑·최초 관리자 생성, 시간은 UTC Unix 밀리초 정수(`*_ms` 컬럼), `DATABASE_URL`이 없으면 SQLite
- 영상 및 인식 데이터: 변경 없음
- **좌표 문단:** "기준 방향·허용 각도" → 각도 범위(min_angle_deg, max_angle_deg), devices 테이블의 별도 컬럼

### 5.2 데이터 흐름도 및 ERD
- **그림 3 교체:** 개념 ERD(user_guardian_links, device_direction_regions, gesture_rules 등 설계 테이블) → 실제 7개 테이블과 컬럼
- **캡션:** "개념 ERD (Conceptual ERD)" → "데이터베이스 ERD"
- **핵심 데이터 흐름 문단:** 기기 현재 상태·연결 상태를 MQTT state·status로 받아 devices에 갱신한다는 내용 추가
- **보존 표**

| 데이터 | 변경 |
| --- | --- |
| 사용자 계정·역할·보호자 연결 | 저장 위치에 users, guardian_links 명시 |
| 방·기기 | 이름 → "방·기기 배치 좌표·포인팅 각도 범위·현재 상태", rooms, devices |
| 제스처·명령 규칙 | 이름 → "제스처·명령 매핑", gesture_mappings, 행은 삭제하지 않음 |
| 기기 제어 이력 | `CONTROL_EVENT_RETENTION_DAYS`(보존 일수) 설정 시 1시간마다 삭제, 미설정 시 보관 |
| 도움 요청 이력 | `HELP_REQUEST_RETENTION_DAYS`(보존 일수) 설정 시 1시간마다 삭제, 미설정 시 보관 |

---

## 6. 보안 및 인증/인가

### 6.1 인증 및 인가 흐름
- **인증:** `POST /api/v1/auth/login`, HS256 JWT를 HttpOnly 쿠키(`aiot_access_token`, SameSite=Strict, Max-Age 1800초)로 전달, CSRF 토큰(`aiot_csrf_token`) 해시를 JWT에 포함, bcrypt 12 rounds, 5회 실패 시 300초 잠금, 엣지는 `EDGE_TOKEN`(엣지 인증 토큰)
- **인가:** USER·GUARDIAN·ADMIN(한국어 병기), CORS `"*"`(모든 출처) 금지, `/ws/v1/events` 종료 코드(4403 Origin, 4401 JWT, 4408 제한시간), 도움 요청 이벤트 수신 범위 제한. **Mosquitto는 현재 익명 허용, ACL은 예제(`deploy/mosquitto/acl.example`)만 있음**을 명시
- **역할 표**

| 역할 | 변경 |
| --- | --- |
| USER | "선택된 기기 확인" → 기기·기기 상태 조회, 본인 비밀번호 변경 추가 |
| GUARDIAN | 확인·완료 처리, 제어 이력 조회 추가 |
| ADMIN | "전체 권한", 각도 범위, 도움 요청 대리 생성·처리 추가 |
| DEVICE | 이름 → "DEVICE (엣지·기기)". 웹 역할이 아니며 엣지는 `EDGE_TOKEN`, 제어부는 Mosquitto 계정·ACL로 구분 |

### 6.2 데이터 보안
- **전송 구간 보호:** TLS는 "목표"로 바꾸고, 현재는 `COOKIE_SECURE`·`MQTT_TLS` 설정만 있으며 기본 배포(80·8000·1883)는 암호화하지 않은 통신임을 명시
- **저장 데이터 보호:** bcrypt, `JWT_SECRET`·`POSTGRES_PASSWORD`·`EDGE_TOKEN`·MQTT 계정은 .env로 관리, `.env.example`만 커밋, `JWT_SECRET`이 비면 임의 키 생성
- **개인정보 최소화:** JPEG도 저장하지 않음, 로그에는 frame_id·correlation_id 같은 식별자만 기록

---

## 7. 인프라 아키텍처

### 7.1 인프라 구성도
- **그림 4 교체:** 웹 서버(Nginx 8080)·AI·응용 서버(FastAPI 8000)·데이터베이스·MQTT 브로커(1883) 컨테이너, 엣지 → FastAPI 직접 WebSocket, 송출 켜기/끄기 MQTT, IoT 제어부 = Pi LED 에이전트·5V LED, ESP32 삭제, "TLS 미적용" 표시

| 항목 | 바뀐 내용 |
| --- | --- |
| 데스크톱 서버 | 컨테이너 4개(nginx, api, postgres, mosquitto)와 포트 |
| 웹 제공 | `/api/`, `/ws/`, `/health` 전달, 같은 출처로 쿠키·CSRF 단순화, TLS는 추후 Nginx에 추가 |
| 데이터 보존 | 볼륨 이름(postgres-data, mosquitto-data) |
| 배포 방식 | api는 postgres healthcheck(상태 검사) 통과 후 시작 |
| 엣지 및 IoT 제어부 | 송출 제어 프로그램(`edge.stream_control`)이 systemd로 부팅 시 실행, 버튼·상태 LED·MQTT(`edge-stream-01`)로 `edge.main --stream`을 켜고 끔, 재접속 간격, Pi LED 에이전트(`pi_led_agent`) |
| 향후 확장 | 변경 없음 |

---

## 8. 모니터링 및 운영

| 항목 | 바뀐 내용 |
| --- | --- |
| 로깅 | 제어 결과 로그 항목(command_id, device_id, result, status, latency_ms), 취소 로그(correlation_id, cancel_reason) |
| 개인정보 보호 | 변경 없음 |
| 서비스 상태 확인 | healthcheck는 api·postgres만, **mosquitto healthcheck 없음** |
| 엣지 연결 관리 | 1→2→4→8→16→30초, frame_ack 시간 초과 3회 연속 시 재연결, `EdgeMetrics`(엣지 지표), edge.connected·edge.disconnected |
| 기기 상태 확인 | 접속 시 ONLINE(연결됨) retain, 비정상 종료 시 LWT로 OFFLINE(끊김), device.state_changed(기기 상태 변경) |
| 성능 측정 | 컬럼명에 `_ms` 붙이고 한국어 병기, latency_ms 정의(ACK 수신 − 제스처 확정), `LatencyTracker`(지연 측정기), **실장비 측정 전** |
| 명령 실패 처리 | ACK 2초 → FAILED(실패, ACK_TIMEOUT), ERROR·EXPIRED는 실패·OK·DUPLICATE는 COMPLETED(완료), **자동 재전송 없음**, 늦은 ACK 무시 |
| 향후 확장 | 변경 없음 |

---

## 9. 아키텍처 결정 기록 (ADR)

### 수정한 ADR

| ADR | 항목 | 바뀐 내용 |
| --- | --- | --- |
| ADR-001 | 결정 | MediaPipe Hands → MediaPipe Hand Landmarker |
| ADR-002 | 결정 | 판정 기준(관절 각도 150°, 손을 세운 방향 위쪽 ±45°), 판별 제스처를 POINTING·OPEN_PALM·FIST·V_SIGN(한국어 병기)으로, 엄지는 판정에 사용하지 않음 |
| ADR-003 | 맥락 | "엄지 올림이나 검지 올림을" → "특정 손 모양을" |
| ADR-003 | 결정 | 기기별 각도 범위를 웹에서 등록, 6프레임·500 ms, 3초, OPEN_PALM=ON·FIST=OFF, 범위 중복·15° 초과 취소 |
| ADR-003 | 결과 | 각도 범위가 겹치면 AMBIGUOUS_TARGET(대상 중복)으로 취소된다는 내용 |
| ADR-004 | 맥락 | "ESP32와 같은" → "Raspberry Pi 같은" |
| ADR-004 | 결정 | 토픽 v1 형식, 명령은 QoS 1·retain 없이 발행, command_id·유효시간 5초(expires_at_ms), status·LWT, 시간 미동기화 시 실행 안 함 |
| ADR-004 | 결과 | 제어부 DUPLICATE(중복) 응답, 서버의 늦은 ACK 무시, Mosquitto 계정·TLS·ACL은 아직 미적용 |
| ADR-005 | | 변경 없음 |

### 추가한 ADR

| ADR | 제목 | 핵심 결정 |
| --- | --- | --- |
| ADR-006 | 웹 인증에 HttpOnly 쿠키 JWT와 CSRF 토큰 사용 | JWT는 HttpOnly·SameSite=Strict 쿠키로만, Nginx로 같은 출처 제공, CSRF 토큰 3중 대조, WebSocket은 Origin·쿠키 인증(4401·4403·4408) |
| ADR-007 | 도움 요청을 MQTT와 분리하여 DB·WebSocket으로 처리 | `IntentDispatcher`가 `HelpService`로 help_requests에 저장하고 help.created를 본인·보호자·관리자에게만 전송, 요청자는 방 거주자. 거주자가 지정된 방이 둘 이상이면 HELP_USER_UNKNOWN 오류가 나는 한계 기록 |
| ADR-008 | ESP32·릴레이 대신 Raspberry Pi 5V LED로 IoT 기기 제어부 구성 | ESP32·릴레이 미사용, `pi_led_agent`가 BCM GPIO 17의 5V LED 전원 제어, 공통 MQTT 규격 그대로 구현, 송출 제어도 같은 규격(`edge-stream-01`) |

---

## 10. 부록

### 관련 문서
- "REST API 및 WebSocket 명세서(작성 예정)" 등 → 실제 파일 경로로 교체: `docs/interfaces/common-interface-spec-v1.0.md`, `docs/api-spec.md`, `docs/websocket-spec.md`, `docs/mqtt-spec.md`, `docs/database-spec.md`, `docs/pi-led-agent.md`, `docs/edge-stream-control.md`. 통합 테스트 계획서는 "작성 예정" 유지

### 구현 현황 (새로 추가한 표, "2026-11-23 기준")

| 구분 | 내용 |
| --- | --- |
| 구현됨 | 엣지 전송·송출 제어, `/ws/v1/frames` 수신, 제스처 인식(POINTING·OPEN_PALM·FIST·V_SIGN), 의도 판단, MQTT 처리, Pi LED 에이전트, REST·실시간 이벤트, 인증, DB, 대시보드 |
| 테스트 | pytest 425개 통과(2026-11-23), vitest. 계약·통합 테스트 일부, e2e 비어 있음 |
| 미구현·미적용 | TLS, Mosquitto 계정·ACL, 웹에서 직접 보내는 ON/OFF 명령(source WEB), 카메라–방 연결 정보 |
| 측정 전 | NFR-01 실측 지연, 인식 정확도·오작동률 |

### 검토 필요 사항 (Open Issues) — 8항목 → 7항목으로 전면 교체

| v1.0 | v1.1 |
| --- | --- |
| ESP32 보드·릴레이·제어 대상 기기 확정 | 해결(ESP32·릴레이 미사용). 항목 삭제 |
| 카메라 종류·해상도·프레임률 확정 | 유지, 현재 기본값(640×480, 10fps, 95) 명시 |
| 기기 위치·방향 영역 등록 UI 방식 확정 | 해결(웹에서 각도 범위 등록). 대신 **인식 기준값·의도 판단 파라미터(6프레임, 500 ms, 3000 ms, 15°) 보정** |
| 도움 요청 제스처 확정 | 해결(V_SIGN). 대신 **FIST(주먹, OFF) 오인식 확인** |
| POINTING_HOLD 등 초기값 조정 | 위 보정 항목으로 합침. 대신 **카메라(edge_id)–방 연결 정보(HELP 요청자 결정)** |
| ACK 제한시간·재전송 확정 | 2초·재전송 없음으로 구현, 실측 후 재검토 |
| FR-05 우선순위 확정 | 해결(구현됨). 대신 **Mosquitto 계정·ACL 적용 시점** |
| TLS 인증서 발급·배포 방법 | 유지 |

---

## 그림 변경 요약

| 그림 | v1.0 | v1.1 |
| --- | --- | --- |
| 그림 1 종합 아키텍처 | ESP32·PubSubClient → 릴레이 → 선풍기·조명, 서버 모듈 개념도 | 서버 처리 흐름(영상 수신 → 손동작 인식 → 의도 판단 → 의도 결과 분배 → IoT 제어)·서비스 계층·REST API·실시간 이벤트 허브, MQTT 브로커 → Pi LED 에이전트 → 5V LED, 송출 제어 추가 |
| 그림 2 상태 전이도 | IDLE → POINTING → TARGET SELECTED → COMMAND PENDING → EXECUTE, 0.8초·0.5초·1.5초 | IDLE(대기) ↔ TARGET_SELECTED(대상 기기 선택됨), OPEN_PALM(손바닥 펴기)=ON·FIST(주먹)=OFF·V_SIGN(V자)=HELP, CANCELLED(취소) 사유 5가지, 6프레임·500 ms·3초·15° |
| 그림 3 ERD | 개념 ERD(device_direction_regions, gesture_rules 등) | 실제 DB의 7개 테이블과 컬럼 |
| 그림 4 인프라 | MQTT/TLS·ACL, ESP32·릴레이 | 실제 컨테이너(nginx 웹 서버·api AI·응용 서버·postgres 데이터베이스·mosquitto MQTT 브로커)와 포트, 엣지 프로그램(`edge.stream_control`, `edge.main`), TLS 미적용 표시, Pi LED 에이전트(`pi_led_agent`), ESP32 삭제 |
