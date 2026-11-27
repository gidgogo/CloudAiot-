# SAD v1.1 → v1.2 변경 내역

- 대상: `SAD_v1.1.docx`(2026-11-23, 팀 검토 전) → `SAD_v1.2.docx`(2026-11-27, 팀 검토 전)
- 기준: main 브랜치 코드(a542a49)와 SAD v1.1을 대조한 결과(`plans/docs/sad-v1.1-fixes.md`)
- 원본 `SAD_v1.1.docx`는 수정하지 않았다. 그림 1~4는 바꾸지 않았다.

## 한눈에 보기

| 절 | 변경 정도 | 요약 |
| --- | --- | --- |
| 문서 관리·개정 이력 | 수정·추가 | 버전 v1.2, 수정일, 개정 이력 v1.2 행 |
| 1.3 용어 | 수정 2행 | MediaPipe Hands → MediaPipe Hand Landmarker |
| 6.2 데이터 보안 | 1항목 수정 | 기본 배포의 Nginx 포트 80 → 8080 |
| 9 ADR | ADR-001 맥락, ADR-002 제목 수정 | MediaPipe 명칭 통일 |

---

## 문서 관리 (Document Control)

| 항목 | v1.1 | v1.2 |
| --- | --- | --- |
| 문서 버전 | v1.1 | v1.2 |
| 최종 수정일 | 2026-11-23 | 2026-11-27 |

## 개정 이력 (Revision History)

- **추가:** v1.2 행 (2026-11-27, 이민형)
  - 내용: SAD v1.1 검토 결과 반영. 6.2 Nginx 포트 8080 통일, MediaPipe Hand Landmarker 명칭 통일(1.3 용어 2행, ADR-001 맥락, ADR-002 제목), 손동작 지정 변경(feat/change-gesture)은 main에 병합하기로 확정하여 v1.1 내용 유지

---

## 1.3 용어 및 약어

| 용어 | v1.1 | v1.2 |
| --- | --- | --- |
| 용어 이름 | MediaPipe Hands | MediaPipe Hand Landmarker (정의는 그대로) |
| 랜드마크 (Landmark) | "MediaPipe Hands가 검출한 …" | "MediaPipe Hand Landmarker가 검출한 …" |

- 이유: 코드가 사용하는 것은 MediaPipe Hand Landmarker 태스크 모델(`server/vision/hand_detector.py`, `hand_landmarker.task`)이다. v1.1에서 1.3 "AI 서버", 2.2, ADR-001 결정은 이미 Hand Landmarker로 바꿨으나 이 두 행이 남아 있었다.

## 6.2 데이터 보안

| 항목 | v1.1 | v1.2 |
| --- | --- | --- |
| 전송 구간 보호 | 기본 배포(Nginx 80, API 8000, MQTT 1883) | 기본 배포(Nginx 8080, API 8000, MQTT 1883) |

- 이유: `docker-compose.yml`의 nginx는 `8080:80`(호스트 8080 → 컨테이너 80)이다. 같은 문단의 API 8000·MQTT 1883도 호스트 포트이고, 7.1절과 그림 4도 8080으로 적혀 있다.

## 9. 아키텍처 결정 기록 (ADR)

| ADR | 항목 | v1.1 | v1.2 |
| --- | --- | --- | --- |
| ADR-001 | 맥락 | MediaPipe Hands 기반 손동작 인식 | MediaPipe 기반 손동작 인식 |
| ADR-002 | 제목 | MediaPipe Hands 기반 규칙식 손동작 인식 채택 | MediaPipe Hand Landmarker 기반 규칙식 손동작 인식 채택 |

---

## 바꾸지 않은 내용

- **손동작 지정(OPEN_PALM=ON, FIST=OFF, V_SIGN=HELP):** main에는 아직 THUMB_UP·THUMB_DOWN·HELP가 남아 있으나, `feat/change-gesture`를 main에 병합하기로 확정했으므로 v1.1의 내용을 그대로 둔다. 병합 전까지는 문서와 main 코드가 다르다.
- **10 부록 구현 현황의 테스트 개수(pytest 425개):** 손동작 브랜치를 병합한 뒤 다시 확인한다(`plans/docs/sad-v1.1-fixes.md` P0-2).
- **3.1 frame_ack 상태 목록(DROPPED 누락):** 아직 반영하지 않았다(같은 계획 P1-3).
