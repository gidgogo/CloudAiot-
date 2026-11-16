# PR #12 웹·응용 서버 통합 검토

## 1. 검토 정보

- 담당자: 성수
- 역할: 웹·응용 서버
- 브랜치: `web-app`
- PR: #12
- 검토 당시 HEAD: `d49dff691663d5468c4bf0c64e867f029366586c`
- 검토일: 2026-11-16
- 검토 상태: 담당자 수정 및 연동 범위 확인 대기
- 검토 기준:
  - `docs/interfaces/common-interface-spec-v1.0.md`
  - PR 설명과 담당자 전달 내용
  - FastAPI, 데이터베이스, 보안 및 React 구현
  - 서버·웹·통합 테스트
  - GitHub CI 결과

## 2. 담당자 구현 범위

- 로그인과 JWT HttpOnly Cookie 인증
- CSRF, Origin, CORS 및 역할별 권한 검사
- 사용자·보호자 연결, 방, 기기와 방향 영역 API
- 기기 제어 이력과 도움 요청 저장·조회·상태 변경
- `/ws/v1/events` 실시간 이벤트와 사용자별 전달 범위
- PostgreSQL 데이터 모델과 초기 Schema
- React 보호자 대시보드와 관리자 화면
- 다른 역할 모듈이 호출할 서비스 연결 지점

## 3. 확인된 내용

- 서버 Windows·Ubuntu CI와 웹 typecheck·test·build가 모두 성공했다.
- REST API 기본 경로와 WebSocket 경로가 공통 규격과 일치한다.
- JWT를 HttpOnly Cookie로 발급하고 CSRF Cookie와 분리한다.
- CORS에서 와일드카드를 사용하지 않고 허용된 Origin과 Credential을 사용한다.
- 도움 요청은 MQTT 기기 제어와 분리되어 DB 및 WebSocket 경로로 처리된다.
- 도움 요청 상태 전이가 `CREATED → CONFIRMED → COMPLETED`로 제한된다.

## 4. 규격 및 구현 차이

### 4.1 JWT 만료시간

공통 규격은 JWT Cookie의 Max-Age를 1,800초로 정한다. 코드 기본값과 테스트는 1,800초지만 `.env.example`은 `JWT_EXPIRE_SECONDS=3600`으로 설정한다. 배포 예시를 규격과 동일한 1,800초로 수정해야 한다.

### 4.2 ±180도 방향 영역

AI Intent는 `min_angle_deg > max_angle_deg`인 값을 ±180도 경계를 넘는 영역으로 처리한다. 웹 API와 편집 화면은 `min_angle_deg < max_angle_deg`만 허용하므로 같은 영역을 등록할 수 없다.

API 검증, 서비스 검증 및 웹 입력 화면을 AI Intent의 영역 계약과 맞춰야 한다.

### 4.3 WebSocket 인증 실패 처리

공통 규격은 모든 인증 검사를 통과한 뒤 연결을 accept하도록 설명한다. 현재 구현은 실패한 브라우저에 `4401`, `4403`, `4408` 종료 코드를 전달하기 위해 실패 시 accept 후 즉시 close한다. 인증 전 이벤트는 전송하지 않으므로 즉각적인 데이터 노출은 없지만, 규격과 구현 중 어느 동작을 기준으로 할지 기록해야 한다.

## 5. 통합 위험과 미구현 의존성

- AI Intent 브랜치와 코드 충돌 없이 테스트가 통과한 사실은 실제 파이프라인 연동 완료를 의미하지 않는다.
- `PENDING`, `CANCELLED`, `CONFIRMED` 결과를 웹·IoT 경로에 연결하는 코드가 없다.
- HELP 확정 결과를 `HelpService.create_from_gesture()`에 연결해야 한다.
- 기기 위치 변경 시 `IntentEngine.update_regions()`를 호출해야 한다.
- 실시간 EventHub가 프로세스 메모리 기반이므로 MQTT 처리와 WebSocket이 같은 API 프로세스에 있어야 한다. 현재 구조에서는 API worker 1개 조건이 필요하다.
- PR #11과 `.gitignore`, `docs/websocket-spec.md`가 겹치므로 단순 줄 병합이 아니라 문서 의미를 확인해야 한다.

## 6. 담당자에게 요청한 사항

- `.env.example`의 JWT 만료시간을 1,800초로 수정
- ±180도 경계 영역을 API와 웹에서 등록할 수 있도록 수정
- AI Intent와 합쳐 실행한 테스트의 범위와 결과 설명
- 현재 EventHub 구조에서는 API worker 1개가 필요함을 배포 문서에 명시

## 7. 통합 담당 후속 작업

- `shared/schemas/v1/help-request.schema.json` 작성
- 도움 요청 Python 타입·DB 표현·JSON Schema 정합성 확인
- PR #11과 #12의 공용 파일 의미 단위 통합
- Vision→Intent→IoT→Web 전체 파이프라인 연결
- WebSocket 인증 실패 처리에 대한 공통 규격 표현 정리
- EventHub와 MQTT 처리 프로세스의 배포 구조 결정

## 8. 머지 판단

현재 판단: **수정 및 연동 범위 확인 후 재검토**

재검토 조건:

- JWT 만료시간 일치
- ±180도 영역 입력 지원
- AI Intent 병합 시험 범위 확인
- 단일 worker 배포 조건 또는 대체 이벤트 전달 방식 결정

## 9. 결정 이력

| 날짜 | 상태 | 근거 |
| --- | --- | --- |
| 2026-11-16 | 수정 요청 후 재검토 | 명시적 규격 차이와 역할 간 연결 의존성 확인 |

