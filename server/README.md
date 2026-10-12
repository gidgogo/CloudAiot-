# AI 분석·의도 판단·API

시선·손동작 분석, 두 입력을 조합한 의도 판단, 이벤트 API를 관리합니다.
라즈베리파이의 카메라나 GPIO를 직접 열지 않습니다.

## 설치와 실행

Python 3.11 가상환경을 활성화하고 저장소 루트에서 실행합니다.

```bash
python -m pip install -r server/requirements.txt
python -m uvicorn server.app:app --reload --host 127.0.0.1
```

영상 분석 모듈을 개발할 때 추가 의존성을 설치합니다.

```bash
python -m pip install -e ".[server,vision]"
```

## 코드와 현재 기능

- `app.py`: `POST /events`, `GET /events` API. 이벤트는 메모리 저장이며 서버를 재시작하면 사라집니다.
- `vision/`: 시선·손동작 인식 틀. 아직 유효 인식 결과를 반환하지 않습니다.
- `intent/fusion.py`: 두 입력의 존재·신뢰도·유효 시간 검사와 동일 명령 반복 제한
- `notifications/client.py`: 기존 로컬 데모에서 `/events`로 HTTP 이벤트를 보내는 클라이언트. 보호자 푸시는 미구현입니다.
- `config.py`, `config.example.yaml`: AI·의도 판단·로컬 이벤트 전송 설정

개인 설정은 `server/config.yaml`에 둡니다. API 문서는 <http://127.0.0.1:8000/docs>에서 확인합니다.
`app.py`에는 아직 영상 수신·추론 API가 연결되지 않았습니다. 현재는 로컬 개발용이며 인증·영구 저장도 미구현입니다.

## 다음 작업

Pi 영상 수신 API와 AI 추론 연결, 의도 상태머신, MQTT 명령 발행·ACK 추적,
사용자 인증·이벤트 영구 저장·보호자 알림을 구현합니다. 영상 전송 형식과 MQTT 계약은 `shared/`에 문서화합니다.
