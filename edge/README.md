# 라즈베리파이 카메라·장치 코드

카메라 프레임을 JPEG로 인코딩해 AI 서버(`/ws/v1/frames`)로 전송합니다.
규격은 [공통 인터페이스 v1 5장](../docs/interfaces/common-interface-spec-v1.0.md)을 따릅니다.
AI 분석과 의도 판단 코드는 `server/`에 있습니다.

## 설치

Python 3.11 가상환경을 활성화하고 저장소 루트에서 실행합니다.

```bash
python -m pip install -r edge/requirements.txt
```

## 카메라 백엔드

라즈베리파이 연결 부분은 `edge/camera.py`의 백엔드로 분리되어 있어, 장비 없이도 같은 코드로 개발·테스트할 수 있습니다.
`Camera(device_index, width, height, fps)` 인터페이스는 그대로이며 `camera.source`만 바꾸면 됩니다.

| `source` | 용도 | 준비 |
|---|---|---|
| `opencv` (기본) | USB 웹캠, 노트북 카메라, V4L2 장치 | `edge/requirements.txt` |
| `picamera2` | Raspberry Pi 카메라 모듈(CSI 리본 케이블) | Pi에서 `sudo apt install python3-picamera2`, 가상환경은 `python -m venv --system-site-packages .venv` |
| `synthetic` | 하드웨어 없이 움직이는 테스트 패턴 | 없음 |
| `file` | 동영상·이미지 폴더·이미지 한 장을 반복 재생 (협업용 더미 송출) | `--file 경로` 또는 `camera.file_path` |

우선순위: `--source` 인자 > 환경변수 `EDGE_CAMERA_SOURCE` > 설정 `camera.source`.
다른 장치를 붙이려면 `open()`, `read()`(BGR 배열 또는 실패 시 None), `close()`를 가진 클래스를 만들어 `BACKENDS`에 등록합니다.

## 실행

```bash
python -m edge.main --check-camera          # 카메라 프레임 한 장 확인
EDGE_TOKEN=... python -m edge.main --stream # AI 서버로 스트리밍 (Ctrl+C로 종료)
python -m edge.main --stream --duration 30  # 30초만 전송하고 메트릭 출력
python -m edge.main --check-camera --source synthetic  # 장비 없이 확인
```

카메라 번호·해상도·FPS·JPEG 품질은 `edge/config.example.yaml`에 있습니다. 개인 설정은 `edge/config.yaml`로 복사해 수정합니다(커밋 금지).
다른 설정 파일은 `--config 경로`로 지정합니다.

| 환경변수 | 설명 |
|---|---|
| `EDGE_TOKEN` | Edge Bearer 토큰. 설정 파일의 `edge.edge_token`보다 우선 |
| `EDGE_SERVER_URL` | 서버 주소(예: `ws://192.168.0.10:8000`). `edge.server_url`보다 우선 |
| `EDGE_CAMERA_SOURCE` | 카메라 백엔드. `camera.source`보다 우선 |
| `EDGE_CAMERA_FILE` | 재생할 파일·폴더. 지정하면 source가 `file`이 됨 (`--file`이 더 우선) |

### AI 서버 없이 확인하기

AI 서버의 프레임 수신부가 준비되기 전에는 Mock 서버로 확인합니다. 라즈베리파이·카메라도 없으면 `--source synthetic`을 함께 씁니다.

```bash
python -m edge.dev.mock_frame_server --port 8000 --token dev-token --delay-ms 50
EDGE_TOKEN=dev-token python -m edge.main --stream --source synthetic
```

### 협업용 더미 송출 (AI·서버 담당용)

라즈베리파이 없이 **실제 Edge와 똑같은 규격**(메타데이터 JSON → JPEG Binary → ACK)으로 자기 PC의 서버에 프레임을 보냅니다.
Edge 코드를 그대로 쓰므로 해상도 변환, `frame_id`, ACK 대기, 재접속까지 실제와 같습니다.

| 목적 | 명령 |
|---|---|
| 손이 나오는 같은 영상으로 반복 테스트 | `python -m edge.main --stream --file samples/pointing.mp4` |
| 이미지 몇 장(제스처별 사진)으로 테스트 | `python -m edge.main --stream --file samples/thumb_up/` |
| 노트북 카메라로 실시간 테스트 | `python -m edge.main --stream --source opencv` |
| 손 없이 연결·성능만 확인 | `python -m edge.main --stream --source synthetic` |

```bash
EDGE_TOKEN=dev-token EDGE_SERVER_URL=ws://localhost:8000 python -m edge.main --stream --file ~/Videos/pointing.mp4
```

- 파일 끝에 도달하면 처음부터 반복합니다. 한 번만 보내려면 설정에서 `camera.file_loop: false`로 둡니다.
- 재생 속도는 원본 FPS가 아니라 `camera.fps`(기본 10)를 따릅니다. 30fps 영상은 3배 느리게 재생됩니다.
- 해상도가 달라도 `camera.width × height`(기본 640×480)로 맞춰 보냅니다.
- `mirrored`, `rotation_deg`는 메타데이터로만 전달되니, 셀카처럼 좌우 반전된 영상이면 `camera.mirrored: true`로 설정합니다.
- 녹화 파일에는 얼굴이 나올 수 있습니다. 저장소에 커밋하지 말고 팀 드라이브로 공유합니다(NFR-03).

## 동작

1. 촬영 작업이 설정 FPS로 카메라를 읽어 전송 대기 버퍼(최대 1개)에 넣습니다. 대기 프레임이 있으면 오래된 것을 폐기합니다.
2. 전송 작업이 최신 프레임을 JPEG로 인코딩하고 메타데이터 JSON → JPEG Binary 순서로 보낸 뒤 같은 `frame_id`의 ACK를 기다립니다(2초 제한).
3. ACK가 `edge.ack_timeout_sec`(기본 2초) 안에 오지 않으면 그 프레임만 폐기하고 연결은 유지합니다. 연속 3번 시간 초과이거나 연결이 끊기면 `1 → 2 → 4 → 8 → 16 → 30초` 백오프로 재접속합니다(이후 30초 간격 반복).
   카메라 읽기가 일시적으로 실패하면 0.1초 간격으로 재시도하고, 10번 연속 실패하면 카메라를 한 번 다시 엽니다. 그래도 안 되면 종료 코드 1로 끝납니다(systemd 재시작 권장).
4. 10초마다 전송 FPS, 폐기 수, 인코딩 시간, 왕복 지연(평균·p95), 촬영→ACK 지연을 로그로 출력합니다.

원본 영상과 JPEG는 메모리에서만 처리하며 디스크에 저장하지 않습니다. 토큰과 영상은 로그에 남기지 않습니다.
`mirrored`, `rotation_deg`는 영상을 변환하지 않고 메타데이터로만 전달하며, AI 서버가 반영합니다.

## 코드

- `camera.py`: 카메라 인터페이스와 백엔드(opencv·picamera2·synthetic)
- `frame_encoder.py`: 해상도 조정, JPEG 인코딩, 프레임 메타데이터 생성
- `frame_buffer.py`: 최신 프레임 1개만 유지하는 전송 대기 버퍼
- `websocket_client.py`: 인증 헤더, 프레임 전송, ACK 검증, 백오프 재접속
- `metrics.py`: FPS·지연·폐기 수 측정(최근 300개만 유지)
- `main.py`: 진입점과 촬영·전송 루프
- `config.py`: edge 전용 설정 읽기
- `devices/`: 기존 로컬 데모용 Mock·GPIO 틀. SAD의 ESP32 제어는 `firmware/`에서 구현합니다.

- `dev/mock_frame_server.py`: 개발용 Mock AI 프레임 서버
- `tests/`: edge 테스트. 프레임 메타데이터·ACK는 `shared/schemas/`의 기준 스키마로 검증

테스트는 저장소 루트에서 실행합니다. 기본 `pytest` 경로(`tests/`)에는 포함되지 않으므로 경로를 지정합니다.

```bash
python -m pytest tests edge/tests
```

## 남은 작업

- 실제 Raspberry Pi에서 `--check-camera --source picamera2`(또는 `opencv`) 확인 후, 카메라에서 FPS, 인코딩 시간, 지연 측정 후 `jpeg_quality`·해상도 결정
- AI 서버의 `/ws/v1/frames` 수신부와 통합 테스트 (서버 담당과 협의)
- 운영 환경 `wss://` 인증서 설정, systemd 서비스 등록
