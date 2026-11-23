# 소프트웨어 아키텍처 명세서

승인된 SAD 원본과 변경 이력을 관리한다. 버전마다 별도 파일로 두고, 이전 버전 파일은 고치지 않는다.

| 파일 | 버전 | 날짜 | 상태 | 내용 |
| --- | --- | --- | --- | --- |
| `SAD_v1.0.docx` | v1.0 | 2026-10-24 | 팀 검토 완료, 초판 확정 | 설계 기준 초판 |
| `SAD_v1.1.docx` | v1.1 | 2026-11-23 | 팀 검토 전 | 구현 코드(main) 기준 갱신 |

v1.1의 주요 변경

- 공통 인터페이스 규격 v1.0 반영: MQTT Topic `aiot/v1/{home_id}/{device_id}/{cmd|ack|state|status}`, Edge 프레임 WebSocket(`/ws/v1/frames`), 실시간 이벤트 10종
- ESP32·릴레이 모듈을 쓰지 않고 Raspberry Pi 5V LED로 IoT 기기 제어부 구성(Pi LED 에이전트)
- 손동작 지정 변경: 손바닥 펴기(OPEN_PALM)=ON, 주먹(FIST)=OFF, V자(V_SIGN)=HELP. 코드는 `feat/change-gesture` 브랜치에서 병합 예정이며 문서에는 적용된 내용으로 적음
- 의도 판단 파라미터와 상태 전이, Cookie JWT·CSRF 인증, DB 스키마(7개 테이블), 구현 현황·미결 사항 갱신
- ADR-006(웹 인증), ADR-007(도움 요청 분리), ADR-008(Raspberry Pi LED 제어부) 추가, 그림 1~4 재작성

버전별 상세 변경 내용은 각 문서의 "개정 이력" 표에 있다.
