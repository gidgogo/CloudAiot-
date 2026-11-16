# PR #14 AI Intent 통합 검토

## 1. 검토 정보

- 담당자: 유경
- 역할: AI B — 의도 판단
- 브랜치: `ai-intent`
- PR: #14
- 검토 당시 HEAD: `859e4439a0b8cbd51a958eb8565d6614291f24af`
- 검토일: 2026-11-16
- 검토 상태: 담당자 확인 및 인터페이스 결정 대기
- 검토 기준:
  - `docs/interfaces/common-interface-spec-v1.0.md`
  - PR 설명과 담당자 전달 내용
  - `server/intent/` 실제 구현
  - `tests/intent/` 테스트
  - GitHub CI 결과

## 2. 담당자 구현 범위

- 포인팅 방향과 화면 비율을 반영한 기기 매칭
- 대상 없음, 영역 중첩, 비활성 기기 구분
- ±180도 경계를 넘는 기기 영역 처리
- 기기 선택 상태머신과 방향 변경 취소
- 제스처 안정화 기준 검사
- HELP 처리와 5초 쿨다운
- 같은 제스처의 반복 확정 방지
- 선택 만료를 위한 `tick()`
- 의도 확정 지연시간 기록
- 사용법과 결정 사항 문서화

## 3. 확인된 내용

- main 기준 13개 커밋이며 변경은 `server/intent/`, `tests/intent/`에 한정된다.
- Windows와 Ubuntu GitHub CI가 모두 성공했다.
- 포인팅 매칭, 상태머신, 안정화, HELP, 지연시간 및 `tick()` 구현이 존재한다.
- 화면 비율과 ±180도 경계 처리를 검증하는 테스트가 존재한다.
- vision→intent→IoT 실제 파이프라인은 아직 구현되지 않았다.

## 4. 규격 및 구현 차이

### 4.1 선택 만료 기준

`USAGE.md`는 선택 후 3초 안에 엄지 제스처가 없으면 취소된다고 설명한다. 실제 코드는 같은 방향의 유효한 `POINTING`이 들어올 때마다 `keep_alive()`로 만료 기준 시각을 갱신하며, 테스트도 이 동작을 검증한다.

결정이 필요한 기준은 다음과 같다.

1. 최초 선택 시점부터 3초 후 만료
2. 마지막 유효 포인팅 시점부터 3초 후 만료

공통 인터페이스 v1.0에는 기준 시점이 정의되어 있지 않다. 담당자 의도와 팀 결정을 확인한 뒤 코드·문서·테스트를 같은 의미로 맞춰야 한다.

### 4.2 비확정 결과의 `action`

공통 `IntentResult` 타입의 기본값은 `action=HELP`, `status=PENDING`이다. 이 때문에 기기 선택 중이거나 별도 action 없이 취소된 결과가 `PENDING + HELP` 또는 `CANCELLED + HELP`로 표현될 수 있다.

공통 규격의 취소 예제에는 action이 없지만 기존 Python 타입과 JSON Schema는 이를 일관되게 표현하지 못한다. 다음 중 하나를 공통 계약으로 결정해야 한다.

- 비확정 결과에서 action 필드 생략
- `action=null` 허용
- action을 유지하고 모든 수신부가 status를 먼저 검사하도록 계약 테스트로 강제

### 4.3 MQTT 명령 변환의 상태 검사

`command_from_intent()`는 action이 ON/OFF인지와 대상 기기가 있는지는 검사하지만 `status == CONFIRMED`인지는 검사하지 않는다. 잘못 구성된 `CANCELLED + ON + target` 결과가 MQTT 명령으로 변환될 수 있으므로 통합 경계에서 방어 검사가 필요하다.

### 4.4 공통 JSON Schema

규격은 `shared/schemas/v1/gesture-result.schema.json`과 `intent-result.schema.json`을 기준 파일로 지정한다. 기존 Schema는 필드가 부족하고 오래된 이름을 사용한다. PR 테스트는 엔진과 Python 타입을 검증하지만 최신 JSON Schema 계약 전체를 검증하지 않는다.

## 5. 통합 위험과 미구현 의존성

- 비확정 결과를 action만 보고 처리하면 잘못된 HELP 요청이 생성될 수 있다.
- `command_from_intent()` 호출 경계가 잘못되면 취소 결과가 MQTT 명령으로 변환될 수 있다.
- AI A의 반전·회전 보정과 프레임 크기 기준이 확정되어야 한다.
- 웹에서 ±180도 경계 영역을 등록하고 위치 변경 시 `engine.update_regions()`를 호출해야 한다.
- 파이프라인에서 `engine.tick()`을 주기적으로 호출해야 한다.

## 6. 담당자에게 요청한 사항

- 선택 만료가 최초 선택 기준인지 마지막 포인팅 기준인지 확인
- 비확정 결과의 action 표현 방식에 대한 의견 제공
- 결정된 기준에 맞춰 AI Intent 코드·문서·테스트를 함께 수정

## 7. 통합 담당 후속 작업

- `shared/schemas/v1/gesture-result.schema.json` 작성
- `shared/schemas/v1/intent-result.schema.json` 작성
- Python 공통 타입과 JSON Schema 정합성 관리
- `command_from_intent()`의 CONFIRMED 방어 검사 보완
- vision→intent→IoT 파이프라인 및 계약 테스트 작성

## 8. 머지 판단

현재 판단: **보류**

재검토 조건:

- 선택 만료 기준 합의
- 비확정 action 계약 합의
- 담당자 수정 커밋 검토
- 공통 v1 Schema 및 계약 테스트와의 정합성 확인

## 9. 결정 이력

| 날짜 | 상태 | 근거 |
| --- | --- | --- |
| 2026-11-16 | 최초 검토, 머지 보류 | 인터페이스 결정과 통합 경계 위험 확인 |

