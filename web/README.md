# 통합 웹 대시보드 (React)

사용자·보호자·관리자가 역할에 따라 쓰는 웹 화면입니다. React 19 + TypeScript + Vite.
브라우저는 FastAPI의 REST API(`/api/v1`)와 실시간 이벤트(`/ws/v1/events`)만 사용하며 카메라나 ESP32에 직접 접근하지 않습니다.

## 화면

| 경로 | 화면 | 역할 |
| --- | --- | --- |
| `/login` | 로그인 | 모두 |
| `/` | 대시보드: 기기 상태·배치도·진행 중인 도움 요청·최근 제어·실시간 활동. 사용자는 큰 도움 요청 버튼 | 모두 |
| `/help` | 도움 요청 목록(상태별 탭), 확인·완료 처리 | 모두(권한별 범위) |
| `/history` | 기기 제어 이력과 지연시간(NFR-01 2초 기준) | 보호자·관리자 |
| `/mapping` | 방 등록, 배치도 위치 지정, 포인팅 방향 영역 편집(겹침 경고) | 관리자 |
| `/admin` | 계정 관리, 보호자 연결, 제스처·명령 매핑 | 관리자 |
| `/account` | 내 정보, 비밀번호 변경 | 모두 |

보호자·관리자에게는 새 도움 요청이 오면 닫을 때까지 남는 알림, 알림음, 브라우저 알림(허용 시), 탭 제목의 대기 건수가 표시됩니다.

## 개발 실행

FastAPI를 먼저 띄웁니다(저장소 루트).

```bash
python -m scripts.seed_demo_data --password demo-pass-123
python -m uvicorn server.app:app --reload
```

웹 개발 서버(5173)는 `/api`, `/ws`, `/health`를 FastAPI(127.0.0.1:8000)로 전달합니다.

```bash
cd web
npm install
npm run dev
```

<http://localhost:5173>에서 `admin@demo.local`, `guardian@demo.local`, `user@demo.local` / `demo-pass-123`으로 로그인합니다.
FastAPI 주소가 다르면 `VITE_API_PROXY=http://주소:포트 npm run dev`.

## 검사와 빌드

```bash
npm run typecheck   # TypeScript 검사
npm test            # 단위 테스트(각도 계산, API 클라이언트, 실시간 재연결)
npm run build       # dist/ 생성 (Docker에서는 Nginx가 제공)
```

## 구조

```
src/
├── api/client.ts            # REST 호출. Cookie 인증, CSRF 헤더, 오류 코드 처리
├── auth/AuthContext.tsx      # 로그인 상태, 만료 시 로그인 화면으로 이동
├── realtime/RealtimeContext.tsx  # /ws/v1/events 연결과 이벤트 구독
├── websocket/eventClient.ts  # 재연결(1~30초), 4401·4403 처리
├── hooks/                    # 사용자·방·기기 목록, 비동기 조회
├── components/               # 배치도, 방향 영역 편집기, 도움 요청 목록, 알림 등
├── pages/                    # 화면
└── utils/                    # 표시 문구, 각도 계산(서버 device_matcher와 같은 기준)
```

포인팅 각도는 카메라 영상 기준 `atan2(dy, dx)`로 오른쪽 0°, 아래 +90°, 위 -90°입니다.
API·이벤트 형식은 `docs/api-spec.md`, `docs/websocket-spec.md`를 따릅니다.
