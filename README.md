# CloudAIoT

AI 기반 시선·손동작 인식 비언어 의사소통 시스템. 숭실대학교 클라우드AIoT 팀 프로젝트입니다.
사용자가 기기를 바라보며 등록된 손동작을 하면 조명·선풍기를 제어하고 보호자에게 도움을 요청하는 것이 목표입니다.

**현재는 초기 개발 뼈대입니다.** 시선·손동작 인식, 실제 GPIO 제어, 클라우드 영상 전송, MQTT, 보호자 푸시는 아직 구현되지 않았습니다.
현재 코드는 라즈베리파이 내부에서 분석하는 구조이며, SAD 초안의 클라우드 추론 구조로 전환하는 작업은 팀 합의가 필요합니다.

## 처음 참여하는 팀원

1. 저장소 소유자에게 GitHub 아이디를 전달하고 공동 작업 초대를 수락합니다. Public 저장소라도 쓰기 권한은 별도입니다.
2. 아래 환경을 설치한 뒤 테스트를 실행합니다.
3. [협업 가이드](CONTRIBUTING.md)를 읽고 담당 작업을 Issue로 등록합니다.
4. 개인 작업 브랜치에서 수정하고 Pull Request로 합칩니다.

## 개발 환경

기준 버전은 Python 3.11입니다. 아래 명령은 저장소 루트에서 실행합니다.

```bash
git clone https://github.com/gidgogo/CloudAiot-.git cloudaiot
cd cloudaiot
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

Windows PowerShell에서는 가상환경 생성·활성화를 다음 명령으로 대신합니다.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
```

기본 개발 설치에는 카메라·MediaPipe가 필요하지 않습니다. 패키지 목록은 `pyproject.toml`에서 관리합니다.

### 보호자 알림 서버

```bash
python -m uvicorn server.app:app --reload --host 127.0.0.1
```

API 문서는 <http://127.0.0.1:8000/docs>에서 확인합니다. 현재 이벤트는 메모리에만 저장되어 재시작하면 사라집니다.
인증과 영구 저장소가 구현되지 않았으므로 현재 서버는 로컬 개발용입니다.

### 카메라 모듈 개발

```bash
python -m pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
python -m cloudaiot.main --mock
```

Windows에서는 `cp` 대신 `Copy-Item config/config.example.yaml config/config.yaml`을 사용할 수 있습니다.
설정 복사를 생략하면 예제 설정을 사용합니다. `config/config.yaml`은 개인 설정으로 Git에 올리지 않습니다.

`--mock`은 **GPIO 기기만 가짜 기기로 대체**합니다. 실제 카메라와 영상 패키지가 필요하며,
현재 인식 함수는 미구현 상태라 카메라를 실행해도 제어 명령은 발생하지 않습니다.
라즈베리파이의 영상 패키지 설치와 실제 장치 동작은 해당 장비에서 별도로 검증해야 합니다.

## 구조와 현재 상태

| 경로 | 역할 / 상태 |
|---|---|
| `src/cloudaiot/vision/` | 카메라 입력, 시선·제스처 인식 틀. 인식은 TODO |
| `src/cloudaiot/intent/fusion.py` | 두 입력·신뢰도·유효 시간 확인, 동일 명령 반복 제한 |
| `src/cloudaiot/devices/` | Mock 제어 가능. 실제 GPIO는 미구현 오류로 명시 |
| `src/cloudaiot/alert/client.py` | HTTP 이벤트 전송 |
| `server/app.py` | FastAPI 이벤트 등록·조회, 메모리 저장 |
| `config/config.example.yaml` | 카메라·기기·제스처 설정 예시 |
| `tests/` | 하드웨어 없는 회귀 테스트 |
| `docs/` | 요구사항 기준과 설계 합의가 필요한 항목 |
| `.github/` | 자동 테스트, Issue·PR 양식 |

## 명령과 요구사항

| 손동작 | 명령 |
|---|---|
| `open_palm` | 바라보는 기기 켜기 |
| `fist` | 바라보는 기기 끄기 |
| `v_sign` | 보호자 도움 요청 |

요구사항 정의서에 맞춰 도움 요청도 시선과 손동작이 모두 확인되어야 합니다.
현재 의도 판단은 입력의 신뢰도와 최신 여부를 검사하지만, 일정 시간 유지·취소 상태머신은 추가 구현이 필요합니다.
영상은 현재 코드에서 파일로 저장하지 않습니다. 인식 정확도와 2초 이내 응답 성능은 아직 측정하지 않았습니다.

전체 요구사항과 SAD 초안의 차이는 [프로젝트 기준](docs/project-status.md)을 확인하세요.
