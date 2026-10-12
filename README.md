# CloudAiot: AI 시선·손동작 비언어 의사소통 시스템

말하기나 손 사용이 어려운 사용자가 **기기를 바라보고 등록된 손동작을 하면** 조명·선풍기 같은 가전을 제어하거나 보호자를 호출할 수 있는 카메라 기반 AIoT 시스템입니다. 라즈베리파이에서 동작합니다.

## 동작 흐름

```
카메라 ─┬─ 시선 인식 (어떤 기기를 보는가) ─┐
        └─ 손동작 인식 (어떤 동작인가) ────┴─ 의도 판단 ─┬─ 기기 제어 (조명/선풍기)
                                                         └─ 보호자 알림 서버 (시간·상태 기록)
```

시선과 손동작이 **둘 다 인식될 때만** 동작합니다. 영상은 메모리에서만 처리하고 파일로 저장하지 않습니다.

## 폴더 구조

| 경로 | 역할 |
|---|---|
| `src/cloudaiot/vision/camera.py` | 카메라 프레임 입력 |
| `src/cloudaiot/vision/gaze.py` | 시선 → 주시 대상 기기 판단 |
| `src/cloudaiot/vision/gesture.py` | 손동작 인식 (open_palm, fist, v_sign) |
| `src/cloudaiot/intent/fusion.py` | 시선 + 손동작 결합해 명령 결정 |
| `src/cloudaiot/devices/` | 기기 인터페이스, GPIO 릴레이, 가짜(mock) 기기 |
| `src/cloudaiot/alert/client.py` | 보호자 알림 서버로 이벤트 전송 |
| `src/cloudaiot/main.py` | 디바이스 메인 루프 |
| `src/cloudaiot/types.py` | 모듈 간 데이터 형식 |
| `server/app.py` | 보호자 알림 서버 (FastAPI) |
| `config/config.example.yaml` | 설정 예시 (기기 영역, 손동작 매핑, GPIO 핀 등) |
| `tests/` | 테스트 |

## 기본 손동작 매핑

| 손동작 | 의미 |
|---|---|
| 손바닥 펴기 (`open_palm`) | 바라보는 기기 켜기 |
| 주먹 (`fist`) | 바라보는 기기 끄기 |
| 브이 (`v_sign`) | 보호자 호출 |

`config/config.yaml` 의 `gesture.mapping` 에서 바꿀 수 있습니다.

## 시작하기

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
cp config/config.example.yaml config/config.yaml

# 보호자 알림 서버
uvicorn server.app:app --reload

# 디바이스 (하드웨어 없이 테스트할 때는 --mock)
python -m cloudaiot.main --mock

# 테스트
pytest
```

## 구현 현황

지금은 뼈대 단계입니다. 의도 판단(`fusion.py`)과 서버 기본 API는 동작하고, 아래는 `TODO` 로 남아 있습니다.

- [ ] 시선 추정 (MediaPipe Face Mesh)
- [ ] 손동작 분류 (MediaPipe Hands)
- [ ] GPIO 릴레이 제어 (gpiozero)
- [ ] 알림 서버 영구 저장소, 보호자 푸시 알림
- [ ] 2초 이내 응답 측정
