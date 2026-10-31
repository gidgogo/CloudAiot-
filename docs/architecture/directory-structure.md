# 디렉토리 구조

| 역할 | 담당 경로 |
| --- | --- |
| 엣지 | `edge/`, `tests/edge/` |
| AI 담당 A | `server/vision/`, `tests/vision/` |
| AI 담당 B | `server/intent/`, `tests/intent/` |
| 웹·응용 서버 | `server/api/`, `server/services/`, `server/db/`, `server/security/`, `web/`, `tests/server/` |
| 인터페이스·통합 | `server/iot/`, `firmware/`, `shared/`, `deploy/`, 통합 테스트 |

루트 `docker-compose.yml`은 FastAPI·AI 서버, React·Nginx, PostgreSQL, Mosquitto를 통합 실행한다.
Raspberry Pi의 `edge/`와 ESP32의 `firmware/`는 컨테이너 외부에서 실행한다.

브랜치는 `edge`, `ai-vision`, `ai-intent`, `web-app`, `integration`을 사용한다. 각 역할 브랜치의 완료된 작업은 `integration`에서 검증하고, 전체 기능이 정상 동작할 때만 `main`에 반영한다.

