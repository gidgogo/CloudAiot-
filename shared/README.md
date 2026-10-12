# 공통 형식과 설정 로더

`types.py`의 Action, GazeResult, GestureResult, Intent를 Python 구성요소에서 공통으로 사용합니다.
`config.py`는 명시한 경로의 YAML 파일을 읽습니다. 각 컴포넌트의 기본 설정 경로는 해당 폴더에서 관리합니다.

이 폴더는 edge나 server를 import하지 않습니다. 공통 형식을 변경하면 관련 담당자와 호환성을 확인합니다.
현재 dataclass는 프로세스 내부 객체이며, 네트워크 직렬화·검증 계약은 아직 구현되지 않았습니다.

향후 영상 프레임 전송, MQTT 명령·ACK, 보호자 이벤트의 JSON 형식과 버전을 이곳에 정의합니다.
ESP32와 웹은 Python 코드를 직접 사용하지 않으므로 합의된 JSON 스키마나 명세를 기준으로 구현합니다.
