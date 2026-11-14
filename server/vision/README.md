# 손동작 인식 (AI 담당 A)

Edge가 보낸 프레임(규격 5.4)에서 손을 찾아 `GestureResult`(규격 6.1)를 만든다.
결과는 `server/intent`의 `IntentEngine.consume`에 그대로 넘긴다.

## 준비

`pyproject.toml` 범위에서 설치되는 최신 MediaPipe(0.10.35에서 확인)에는 `mp.solutions`가 없다.
그래서 Tasks API의 Hand Landmarker를 사용하며, 모델 파일을 따로 받아야 한다.
모델은 저장소에 올리지 않는다(`models/.gitignore`).

```bash
curl -L -o server/vision/models/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
```

## 사용법

카메라 하나당 `GesturePipeline` 하나를 둔다. 손 추적과 안정화 누적이 영상 하나를 기준으로 동작하기 때문이다.

```python
from server.vision.landmark_processor import oriented_frame_size
from server.vision.pipeline import GesturePipeline

pipeline = GesturePipeline()  # HandDetector(model_path=...)를 넘겨 모델 경로를 바꿀 수 있음

try:
    gesture = pipeline.process_jpeg(jpeg_bytes, metadata)  # metadata: shared.types.FrameMetadata
except ValueError:
    ...  # JPEG가 아니거나 크기가 메타데이터와 다름 → frame_ack status INVALID
width, height = oriented_frame_size(metadata.width, metadata.height, metadata.rotation_deg)
intent = engine.consume(gesture, frame_width=width, frame_height=height)

pipeline.close()  # 연결이 끝나면 호출
```

- 프레임마다 결과를 하나 돌려준다. 손이 없으면 `gesture=UNKNOWN`, `stable_frames=0`, `hold_time_ms=0`이다.
- JPEG는 메모리에서만 디코딩하고 저장하지 않는다(규격 5.6).
- `pointing_vector`는 `POINTING`일 때만 들어간다. 손이 작아 방향을 믿을 수 없으면 `UNKNOWN`으로 낸다.

## 판정 기준

| 제스처 | 조건 |
| --- | --- |
| `POINTING` | 검지만 펴짐(엄지는 상관없음). 방향은 모든 각도 허용 |
| `THUMB_UP` / `THUMB_DOWN` | 네 손가락이 접히고 엄지가 곧게 펴져 위/아래(±45°)를 향함 |
| `HELP` | 네 손가락을 모두 펴고 손바닥을 위로 세움(손목→중지 뿌리 방향이 위 ±45°). 엄지는 상관없음 |
| `UNKNOWN` | 위에 해당하지 않음, 또는 손 없음 |

- 손가락이 펴졌는지는 관절 각도로 판단한다(`GestureRuleParameters`, 기본 150°). 손이 어느 쪽을 향해도 같은 기준이 적용된다.
- 안정화는 `StabilityChecker`가 계산한다. 같은 제스처가 이어지면 누적하고, 제스처가 바뀌거나 `UNKNOWN`이 나오거나 프레임 간격이 500ms를 넘으면 다시 센다.
  유지 시간은 Edge의 `captured_at_ms` 차이로 계산하므로 네트워크 지연의 영향을 받지 않는다.
- 6프레임·500ms 기준 확인은 의도 엔진이 한다. `StabilityChecker`의 같은 값은 `IntentParameters`와 맞춰 둔 것이다.

## 좌표와 방향 (규격 4.4)

- 랜드마크는 받은 JPEG 기준으로 검출한 뒤 똑바로 선 화면 기준으로 바꾼다. 결과의 좌표는 모두 바뀐 기준이다.
- 순서: `mirrored=true`면 좌우를 먼저 되돌리고, 그다음 `rotation_deg`만큼 시계 방향으로 돌린다.
  `rotation_deg`는 "받은 영상을 똑바로 세우려면 시계 방향으로 몇 도 돌려야 하는가"로 해석한다.
- 90°·270°이면 가로·세로가 바뀌므로, 의도 엔진에는 `oriented_frame_size`로 구한 크기를 넘긴다.
- 포인팅 각도는 `pointing_angle_deg`로 구한다. 오른쪽 0°, 아래 +90°, 위 -90°, 왼쪽 ±180°이다.
- `handedness`는 사용자의 실제 손이다. MediaPipe는 거울 영상을 가정하므로 `mirrored=false`면 좌우 라벨을 바꾼다.

## 확인 필요

| 대상 | 내용 |
| --- | --- |
| 엣지 | `rotation_deg`의 의미를 위 해석(시계 방향으로 돌려 세우는 각도)으로 맞춰야 한다. |
| 통합 | 서버 컨테이너에 모델 파일을 넣는 방법(이미지 빌드 시 다운로드 또는 볼륨)을 정해야 한다. |
| 통합 | `shared/schemas/gesture-result.schema.json`이 규격 6.1과 다르다(`detected_at`만 요구). |
| 팀 | `HELP` 손 모양(손바닥 세우기)과 판정 기준값은 실제 카메라로 보정이 필요하다. |
