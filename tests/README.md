# 테스트

하드웨어 없이 실행하는 회귀 테스트를 관리합니다. 저장소 루트에서 실행합니다.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

- `test_fusion.py`: 시선·손동작 결합, 신뢰도, 입력 유효 시간, 반복 명령 제한
- `test_setup.py`: 컴포넌트별 설정, Mock 제어, 모듈 간 의존성 분리
- `test_edge.py`: 카메라 점검 명령의 자원 해제와 프레임 수신 실패 처리

실물 카메라·GPIO와 장비 간 통신 검증은 별도로 진행하고 조건과 결과를 PR에 기록합니다.
