# CloudAIoT

AI 기반 시선·손동작 인식 비언어 의사소통 시스템. 숭실대학교 클라우드AIoT 팀 프로젝트입니다.
사용자가 기기를 바라보며 등록된 손동작을 하면 조명·선풍기를 제어하고 보호자에게 도움을 요청하는 것이 목표입니다.

## 실행 위치별 구조

하나의 GitHub 저장소에서 역할별 폴더를 함께 관리합니다.

```text
cloudaiot/
├── edge/          # 라즈베리파이: 카메라 입력, 장치 코드
├── server/        # 서버: 시선·손동작 분석, 의도 판단, 이벤트 API
├── firmware/      # ESP32: MQTT 명령 수신·실물 제어 예정
├── web/           # 보호자 웹 화면 예정
├── shared/        # 공통 데이터 형식·설정 로더
├── scripts/       # 한 컴퓨터에서 실행하는 로컬 통합 데모
├── tests/         # 하드웨어 없는 회귀 테스트
├── docs/          # 요구사항과 설계 기록
└── .github/       # CI, Issue·PR 양식
```

**실행 역할에 맞춰 기존 코드를 분리한 초기 뼈대입니다.** 시선·손동작 인식은 TODO이며,
Pi에서 서버로 보내는 영상 전송, 서버의 MQTT 명령 발행, ESP32 펌웨어와 보호자 웹은 아직 구현되지 않았습니다.
폴더가 분리된 상태와 장비 간 통신이 완성된 상태를 구분합니다.

| 담당 | 작업 시작 문서 | 현재 확인 가능한 기능 |
|---|---|---|
| 라즈베리파이 | [edge](edge/README.md) | 카메라 한 프레임 점검, Mock 장치 제어 |
| AI·백엔드 | [server](server/README.md) | 의도 판단, 이벤트 등록·조회 API |
| ESP32 | [firmware](firmware/README.md) | 구현할 역할 안내 |
| 보호자 화면 | [web](web/README.md) | 구현할 화면과 현재 API 안내 |
| 공통 형식 | [shared](shared/README.md) | Action, GazeResult, GestureResult, Intent |

## 개발 환경

기준 버전은 Python 3.11입니다. **설치·실행 명령은 모두 저장소 루트에서 실행합니다.**

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

기본 개발 환경은 카메라·GPIO 없이 테스트할 수 있습니다. 역할에 필요한 추가 패키지는 각 폴더 README를 따릅니다.
의존성 목록은 루트 `pyproject.toml`에서 관리하며 각 `requirements.txt`는 해당 설치 그룹을 선택합니다.

## 실행 명령

```bash
# 라즈베리파이: 카메라 패키지 설치 후 한 프레임만 확인 (파일 저장 없음)
python -m pip install -r edge/requirements.txt
python -m edge.main --check-camera

# 서버: 이벤트 API 실행
python -m pip install -r server/requirements.txt
python -m uvicorn server.app:app --reload --host 127.0.0.1
```

API 문서는 <http://127.0.0.1:8000/docs>에서 확인합니다.
현재 서버는 로컬 개발용이며 이벤트는 메모리 저장입니다. 인증, 영구 저장, 외부 배포는 추가 구현이 필요합니다.
ESP32와 웹에는 아직 실행할 프로그램이 없습니다.

## 설정과 기존 코드 이전

- 카메라·로컬 장치 설정: `edge/config.example.yaml`을 `edge/config.yaml`로 복사합니다.
- AI·의도 판단·로컬 알림 설정: `server/config.example.yaml`을 `server/config.yaml`로 복사합니다.
- 복사를 생략하면 해당 컴포넌트의 예제 설정을 읽습니다. 개인 설정은 Git에서 제외합니다.
- 기존 `config/config.yaml`에 개인 값을 넣었다면 카메라·devices 항목은 edge 설정으로, 나머지는 server 설정으로 옮깁니다. 기존 파일은 자동으로 읽지 않습니다.
- 기존 `src/cloudaiot`의 import 경로는 각 역할별 패키지로 변경되었습니다. 기존 작업 브랜치는 새 main을 반영한 뒤 경로를 맞춥니다.
- 기존 통합 실행 명령 `python -m cloudaiot.main --mock`은 아래로 바뀌었습니다.

```bash
python -m pip install -r requirements.txt
python -m scripts.local_demo --mock
```

이 데모는 한 컴퓨터에서 edge와 server 모듈을 함께 확인하는 개발 도구입니다.
`--mock`은 GPIO만 대체하므로 실제 카메라와 영상 패키지가 필요합니다. 인식이 미구현이라 현재는 명령이 발생하지 않습니다.

## 협업과 구현 기준

각자 작업 브랜치를 만들고 PR로 합칩니다. [협업 가이드](CONTRIBUTING.md)에 작성자 설정과 작업 절차를 정리했습니다.

손동작 매핑은 `open_palm`=켜기, `fist`=끄기, `v_sign`=도움 요청입니다.
도움 요청도 시선과 손동작이 모두 확인되어야 합니다. 인식 정확도와 2초 이내 응답 성능은 아직 측정하지 않았습니다.
전체 요구사항과 SAD 초안의 차이는 [프로젝트 기준](docs/project-status.md)을 확인하세요.
