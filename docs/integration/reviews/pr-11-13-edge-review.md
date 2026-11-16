# PR #11·#13 Edge 통합 검토

## 1. 검토 정보

- 담당자: 찬우
- 역할: Raspberry Pi Edge
- PR: #11, #13
- PR #11 HEAD: `a2cc287a52dab5d740dfe13ae1ffa25dba8e1fa9`
- PR #13 HEAD: `149024ab756d4ec8af53f639d81c0f324888b752`
- 검토일: 2026-11-16
- 검토 상태: 실기기 결과 및 아키텍처 의도 확인 대기
- 검토 기준:
  - `docs/interfaces/common-interface-spec-v1.0.md`
  - PR 설명과 담당자 전달 내용
  - Edge 영상 전송 및 Raspberry Pi IoT agent 구현
  - 관련 단위·계약 테스트
  - GitHub CI 결과

## 2. 담당자 구현 범위

### PR #11

- OpenCV, Picamera2, synthetic 및 파일 카메라 입력
- Metadata JSON → JPEG Binary → Frame ACK 전송
- 최신 프레임 1개 버퍼와 오래된 프레임 폐기
- ACK 검증, 시간 초과 및 지수 백오프 재접속
- Edge Bearer Token과 `X-Edge-ID` 인증 헤더
- 프레임 메타데이터 및 ACK Schema와 계약 테스트
- Mock Frame 서버와 Edge 운영 문서

### PR #13

- 물리 버튼을 이용한 영상 송출 시작·중지
- LED를 이용한 송출·정지·비정상 종료 표시
- 영상 송출 자식 프로세스 관리
- MQTT ON/OFF, ACK, state, status 및 LWT 처리
- Raspberry Pi GPIO 릴레이 제어용 `iot_agent`
- systemd 자동 실행 스크립트

## 3. 확인된 내용

- PR #11은 Windows와 Ubuntu GitHub CI가 모두 성공했다.
- 프레임 전송 순서, 최신 프레임 우선, 영상 비저장 및 재접속 로직이 구현되어 있다.
- Picamera2 백엔드는 존재하지만 자동 테스트는 가짜 객체를 이용한다.
- PR #11의 실물 시험란에는 실제 Pi 카메라 실행 결과가 기록되어 있지 않다.
- 실제 AI 서버 `/ws/v1/frames` 수신부는 없으며 현재 통신 상대는 Mock 서버다.
- PR #13에는 GitHub CI 결과가 등록되어 있지 않다.

## 4. 규격 및 구현 차이

### 4.1 프레임 Schema 기준 경로

PR #11은 기존 `shared/schemas/` 아래의 Frame Metadata Schema를 수정하고 Frame ACK Schema를 추가한다. 공통 규격의 공식 기준 경로는 `shared/schemas/v1/`이다. Schema 내용과 최종 위치는 통합 담당자가 전체 v1 계약과 함께 정리해야 한다.

### 4.2 추가 구현값

다음 값은 구현되어 있지만 공통 규격에 확정되지 않았다.

- 최대 프레임 크기 2MB
- Frame ACK 대기 2초
- ACK 3회 연속 시간 초과 시 재접속
- WebSocket 핸드셰이크 거부 응답 코드
- stop-and-wait 전송 방식

AI 서버 수신 담당자와 통합 담당자의 합의가 필요하다.

### 4.3 Raspberry Pi의 IoT 제어 역할

현재 합의된 아키텍처는 Raspberry Pi가 카메라 Edge를 담당하고 ESP32-S3가 MQTT와 릴레이를 담당한다. PR #13은 Raspberry Pi에 범용 MQTT agent와 조명·선풍기 GPIO 릴레이 제어를 추가한다.

카메라 송출 버튼·LED만 필요한지, Raspberry Pi가 릴레이 제어까지 담당할 것인지 팀 결정이 필요하다. 범용 Pi 릴레이 제어는 현재 역할 경계와 충돌한다.

### 4.4 카메라 송출의 MQTT 기기 등록

PR #13은 `edge-stream-01`을 일반 MQTT 기기처럼 제어한다. 웹에 일반 기기로 등록하면 포인팅과 제스처로 카메라가 꺼질 수 있다. 카메라 송출 제어 권한과 제스처 대상 제외 규칙을 별도로 정해야 한다.

## 5. 통합 위험과 미구현 의존성

- 실제 Raspberry Pi Camera Module 3의 지속 송출 성능이 확인되지 않았다.
- 실제 AI 서버 수신부와의 인증·프레임·ACK 통합 시험이 남아 있다.
- `rotation_deg`의 의미를 AI A와 동일하게 해석해야 한다.
- PR #13의 Pi IoT agent를 병합하면 ESP32 담당 범위와 구현이 중복될 수 있다.
- PR #11과 웹 PR #12가 `.gitignore`, `docs/websocket-spec.md`를 함께 수정한다.

## 6. 담당자에게 요청한 사항

- 실제 Pi 카메라 시험 명령과 결과 로그 제공
- 실제 카메라 FPS, 인코딩 시간 및 전송 지연 측정 여부 확인
- PR #13이 카메라 버튼·LED만을 위한 것인지 Pi 릴레이 제어까지 포함하려는 것인지 확인
- `edge-stream-01`을 제스처 대상에서 제외하는 방향 확인
- PR #13 전체 테스트 및 실제 버튼·LED·MQTT 시험 결과 제공

## 7. 통합 담당 후속 작업

- `shared/schemas/v1/frame-metadata.schema.json` 작성 및 경로 정리
- Frame ACK Schema의 공식 기준 파일 결정
- AI 서버 담당자와 추가 구현값 합의
- PR #11과 #12의 `.gitignore`, `docs/websocket-spec.md` 의미 단위 통합
- Edge→Vision 실제 파이프라인과 계약 테스트 구성
- Raspberry Pi와 ESP32 역할 경계 최종 확인

## 8. 머지 판단

- PR #11: **실기기 근거와 공통 계약 확인 후 재검토**
- PR #13: **아키텍처 역할 합의 전까지 보류**

## 9. 결정 이력

| 날짜 | 상태 | 근거 |
| --- | --- | --- |
| 2026-11-16 | PR #11 조건부 재검토, PR #13 보류 | 실기기 근거와 Raspberry Pi 역할 결정 필요 |

