# 공동 개발 방법

## 참여와 작업 기록

각자 GitHub 계정으로 참여하고, 저장소 관리자가 Collaborators에서 쓰기 권한으로 초대합니다.
현재 저장소 소유자는 `gidgogo`입니다. 역할과 담당자는 팀에서 합의한 뒤 Issue의 Assignee에 지정합니다.

수업에서는 GitHub 기록으로 참여도를 평가하므로 각자의 계정과 작성자 정보를 사용합니다.
아래 예시의 이름과 이메일은 반드시 본인의 정보로 바꿉니다. GitHub 비공개 noreply 이메일도 사용할 수 있습니다.

```bash
git config user.name "본인 이름"
git config user.email "GitHub에 등록한 본인 이메일"
```

AI가 작성한 코드도 담당자가 동작을 설명하고 테스트할 수 있어야 합니다.
기존 커밋의 작성자나 공유된 이력을 다시 쓰지 않습니다.

## Issue부터 PR까지

1. 작업 Issue에 목표, 관련 요구사항, 완료 조건을 적고 담당자를 정합니다.
2. 최신 `main`에서 `feat/이슈번호-설명`, `fix/이슈번호-설명`, `docs/이슈번호-설명` 브랜치를 만듭니다.
3. 작은 작업 단위로 커밋하고 PR에 테스트 결과를 적습니다.
4. 팀원 리뷰를 요청하고 CI 통과와 리뷰 의견 반영을 확인한 뒤 병합합니다.

```bash
git switch main
git pull --ff-only
git switch -c feat/12-gesture-recognition
# 수정 후
python -m pytest
git add src/cloudaiot/vision/gesture.py
git commit -m "by 본인이름 - feat: 손동작 분류 구현"
git push -u origin feat/12-gesture-recognition
```

위 파일과 브랜치는 예시입니다. 자신이 변경한 파일만 추가하고, GitHub에서 `main` 대상 PR을 만듭니다.
관련 Issue가 있으면 PR 본문에 `Closes #12`처럼 연결합니다.

`main`에는 PR과 CI를 거쳐 반영합니다. 강제 푸시와 브랜치 삭제는 금지합니다.
초기에는 소유자만 등록되어 있으므로 승인 리뷰 수는 강제하지 않습니다.
팀원이 합류하면 관리자와 상의해 승인 리뷰 1개를 필수로 설정합니다.
기여 이력을 보존하려면 GitHub의 Create a merge commit 방식으로 병합합니다.

## 개발 규칙

- 기준 환경은 Python 3.11이며 설치·실행 방법은 README를 따릅니다.
- 모듈 간 전달 형식은 `src/cloudaiot/types.py`를 기준으로 맞춥니다. 형식 변경은 관련 담당자와 먼저 합의합니다.
- 공통 의존성은 `pyproject.toml`의 dependencies, 영상 의존성은 vision, 테스트 도구는 dev에 추가합니다.
- 버그 수정 시 재현 테스트를 추가합니다. 실제 카메라/GPIO 테스트 결과는 장비와 조건을 PR에 기록합니다.
- 개인 설정, `.env`, 인증키, 촬영 영상은 커밋하지 않습니다. 공유할 설정은 값이 없는 예제 파일로 제공합니다.
- 요구사항 변경은 문서와 Issue에 이유를 남깁니다. 확정되지 않은 SAD 초안의 내용을 구현 완료로 표시하지 않습니다.

## 문서와 역할

설계 문서는 `docs/`에서 함께 관리하고, 발표 자료 등 바이너리 문서는 한 번에 한 사람이 수정합니다.
각 단계의 담당 역할과 결과는 Issue·PR에 남깁니다. 팀원의 GitHub 아이디와 역할은 합의 후 추가합니다.
