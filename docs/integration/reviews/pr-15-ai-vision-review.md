# PR #15 AI Vision 통합 검토

## 1. 검토 정보

- 담당자: 민형
- 역할: AI A — 손동작·포인팅 인식
- 브랜치: `ai-vision`
- PR: #15
- 검토 당시 HEAD: `d0393302066af451d872594bc074febfaf78c22f`
- 검토일: 2026-11-16
- 검토 상태: 시간·좌표 계약 및 모델 배포 방식 확인 대기
- 검토 기준:
  - `docs/interfaces/common-interface-spec-v1.0.md`
  - PR 설명과 담당자 전달 내용
  - `server/vision/` 실제 구현
  - `tests/vision/` 테스트
  - GitHub CI 및 Dockerfile 변경

## 2. 담당자 구현 범위

- MediaPipe Tasks Hand Landmarker 기반 손 검출
- `POINTING`, `THUMB_UP`, `THUMB_DOWN`, `HELP`, `UNKNOWN` 판정
- 좌우 반전 및 0·90·180·270도 회전 보정
- 사용자의 실제 손 기준 handedness 변환
- 정규화 포인팅 벡터와 최소 길이 검사
- 프레임 수와 유지시간 안정화 계산
- JPEG 메모리 디코딩과 입력 검증
- 로컬 웹캠 확인 스크립트와 Vision 문서
- Ubuntu MediaPipe 실행에 필요한 GLES/EGL 의존성 추가

## 3. 확인된 내용

- Ubuntu와 Windows GitHub CI가 모두 성공했다.
- Ubuntu Runner 및 서버 Dockerfile에 `libgles2`, `libegl1`이 추가되었다.
- 손이 없을 때 `UNKNOWN`, `stable_frames=0`, `hold_time_ms=0` 결과를 생성한다.
- 포인팅 벡터는 0.0~1.0 범위로 제한된다.
- 안정화 시간은 Edge의 `captured_at_ms` 차이로 계산된다.
- JPEG와 프레임 크기 검증이 존재하며 영상은 메모리에서 처리된다.
- 실제 확인은 iPhone 미러링 웹캠의 정면 제스처 조건이다.

## 4. 규격 및 구현 차이

### 4.1 `detected_at_ms`의 의미

안정화 계산은 Edge의 `captured_at_ms`를 사용한다. 그러나 `GestureResult` 생성 시 `detected_at_ms`를 직접 지정하지 않아 공통 타입의 기본값인 AI 처리 시점이 들어간다.

AI Intent는 이 값을 오래된 입력 판단과 선택 만료에 사용하므로 다음 중 하나로 의미를 확정해야 한다.

1. Edge 프레임 촬영 시각
2. AI가 제스처 판정을 완료한 시각

결정 후 Vision 출력, Intent 입력 검사, JSON Schema 및 계약 테스트를 동일한 의미로 맞춰야 한다.

### 4.2 `rotation_deg`의 의미

AI Vision은 `rotation_deg`를 받은 영상을 똑바로 세우기 위해 시계 방향으로 돌릴 각도로 해석한다. Edge도 같은 의미로 값을 보내야 하며 90도·270도에서는 AI Intent에 보정된 가로·세로를 전달해야 한다.

### 4.3 공통 Gesture Schema

기존 `shared/schemas/gesture-result.schema.json`은 `detected_at` 같은 오래된 필드를 사용하고 규격 6.1의 필드를 표현하지 못한다. 공식 기준 파일은 `shared/schemas/v1/gesture-result.schema.json`으로 작성해야 한다.

## 5. 통합 위험과 미구현 의존성

- 서버 `/ws/v1/frames` 수신부에 `GesturePipeline`이 연결되지 않았다.
- Vision 결과를 `IntentEngine.consume()`에 전달하는 실제 파이프라인이 없다.
- 90도·270도 회전 시 `oriented_frame_size()` 결과를 Intent에 넘기는 통합 코드가 필요하다.
- MediaPipe 모델 파일이 없으면 기본 `GesturePipeline()`을 생성할 수 없다.
- 모델을 Docker 이미지에 포함할지 실행 볼륨으로 제공할지 결정되지 않았다.
- HELP 손 모양과 임계값은 실제 Raspberry Pi 카메라 환경에서 보정되지 않았다.

## 6. 담당자에게 요청한 사항

- `detected_at_ms`의 의도된 기준 확인
- Edge 담당자와 `rotation_deg` 의미 확인
- Docker 이미지 빌드 시 다운로드 또는 볼륨 제공 중 모델 배포 방식에 대한 의견 제공
- 추후 Raspberry Pi 카메라, 반전·회전, 거리·조명 조건에서 임계값 보정

## 7. 통합 담당 후속 작업

- `shared/schemas/v1/gesture-result.schema.json` 작성
- AI A 출력과 AI B 입력 계약 테스트 추가
- Edge→Vision→Intent 파이프라인 연결
- 회전된 프레임 크기를 Intent에 전달
- MediaPipe 모델 배포 및 Docker 통합 방식 결정
- Raspberry Pi 카메라 기반 전체 파이프라인 시험 구성

## 8. 머지 판단

현재 판단: **시간·좌표 계약과 모델 배포 방식 합의 후 재검토**

재검토 조건:

- `detected_at_ms` 의미 합의
- Edge와 `rotation_deg` 해석 통일
- 모델 배포 방식 결정
- 공식 Gesture Schema 및 계약 테스트와의 정합성 확인

## 9. 결정 이력

| 날짜 | 상태 | 근거 |
| --- | --- | --- |
| 2026-11-16 | 최초 검토, 조건부 보류 | 시간·좌표 계약과 실행 모델 의존성 확인 |

