# 로컬 개발 도구

`local_demo.py`는 기존 통합 실행 코드를 보존한 도구입니다.
한 컴퓨터에서 edge의 카메라·Mock 장치와 server의 인식·의도 판단 모듈을 함께 실행합니다.
운영용 edge/server 프로세스는 서로 직접 import하지 않으며, 이 도구만 두 모듈을 함께 사용합니다.

저장소 루트에서 실행합니다.

```bash
python -m pip install -r requirements.txt
python -m scripts.local_demo --mock
```

별도 터미널에서 `python -m uvicorn server.app:app --host 127.0.0.1`을 실행하면 이벤트 수신 API를 준비할 수 있습니다.
카메라가 필요하고 GPIO만 Mock으로 대체합니다. 인식 함수가 TODO이므로 현재는 명령·이벤트가 발생하지 않습니다.
실물 장비 없이 확인하려면 `python -m pytest`를 사용합니다.
