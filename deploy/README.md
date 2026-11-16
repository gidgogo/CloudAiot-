# Docker 실행 환경

저장소 루트에서 실행한다.

```bash
cp .env.example .env      # 비밀번호·JWT_SECRET·ADMIN_EMAIL·ADMIN_PASSWORD를 채운다
docker compose up -d --build
```

| 컨테이너 | 주소 | 역할 |
| --- | --- | --- |
| nginx | <http://localhost:8080> | React 웹, `/api`·`/ws`·`/health`를 api로 전달 |
| api | <http://localhost:8000> | FastAPI(AI·의도 판단·웹 API) |
| postgres | 내부 5432 | 사용자·기기·이력 저장(외부 포트 공개 안 함) |
| mosquitto | 1883 | MQTT 브로커 |

- 첫 실행에서 사용자가 없으면 `ADMIN_EMAIL`·`ADMIN_PASSWORD`로 관리자 계정을 만든다.
- 데모 데이터는 api 컨테이너에서 `docker compose exec api python -m scripts.seed_demo_data --password 비밀번호`로 넣는다.
- 웹 주소를 바꾸면 `.env`의 `ALLOWED_ORIGINS`도 바꾼다. HTTPS로 운영하면 `COOKIE_SECURE=true`.
- Edge와 같은 `EDGE_TOKEN`을 설정하고, MQTT를 사용하면 `MQTT_ENABLED=true`,
  `MQTT_HOST=mosquitto`, `MQTT_HOME_ID`를 설정한다.
- `POSTGRES_PASSWORD`에 `@ : /` 같은 문자가 있으면 `DATABASE_URL`에 들어가므로 URL 인코딩이 필요하다.
- **api는 워커 1개로 실행한다**(`server/Dockerfile`의 uvicorn 기본값). 웹 실시간 이벤트 허브(`EventHub`)가 api 프로세스 메모리에 있어서,
  MQTT 수신·의도 판단 결과 처리와 WebSocket(`/ws/v1/events`)이 같은 프로세스에 있어야 웹으로 이벤트가 전달된다.
  `--workers`를 늘리거나 MQTT 처리를 별도 컨테이너로 나누려면 Redis 등 프로세스 간 이벤트 전달을 먼저 추가해야 한다.

## 설정 파일

- `nginx/default.conf`: `proxy_pass http://api:8000;`처럼 경로 없이 전달해야 `/api/v1/...` 경로가 유지된다.
  Host는 포트까지(`$http_host`) 넘겨야 FastAPI의 같은 출처(Origin) 검사가 맞는다.
- `mosquitto/`: MQTT 브로커 설정(통합 담당)
- `postgres/init.sql`: DB 초기 설정. 테이블은 api가 시작할 때 만든다(`server/db/migrations/initial_schema.sql`과 같다).
