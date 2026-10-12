# 라즈베리파이

카메라 입력을 담당합니다. 클라우드 구조에서는 촬영한 프레임을 서버로 전송하고 연결 상태를 관리할 예정입니다.
AI 분석과 의도 판단 코드는 `server/`에 있습니다.

## 설치와 실행

Python 3.11 가상환경을 활성화하고 저장소 루트에서 실행합니다.

```bash
python -m pip install -r edge/requirements.txt
python -m edge.main --check-camera
```

현재 명령은 카메라 프레임 한 장을 메모리에서 읽고 크기를 출력한 뒤 카메라를 닫습니다.
원본 파일을 저장하지 않으며 서버로 전송하지도 않습니다. 장비가 없으면 `python -m edge.main --help`로 진입점을 확인할 수 있습니다.

카메라 번호·해상도는 `edge/config.example.yaml`에 있습니다. 개인 설정은 `edge/config.yaml`로 복사해 수정합니다.
다른 설정 파일은 `python -m edge.main --config 경로 --check-camera`로 지정합니다.

## 코드

- `camera.py`: OpenCV 카메라 입력
- `main.py`: 카메라 점검 진입점
- `devices/`: 기존 Mock 및 직접 GPIO 제어용 틀. GPIO는 미구현 오류를 발생시킵니다.
- `config.py`: edge 전용 설정 읽기

`devices/`는 기존 로컬 데모를 보존하기 위한 코드입니다. SAD의 ESP32 제어는 `firmware/`에서 별도로 구현합니다.
실제 Raspberry Pi의 영상 패키지 설치와 카메라 동작은 장비에서 검증해야 합니다.

## 다음 작업

프레임 인코딩·서버 전송, 인증, 재연결, 전송 지연과 프레임 적체 처리를 구현합니다.
메시지 형식은 서버 담당자와 `shared/` 기준으로 합의합니다.
