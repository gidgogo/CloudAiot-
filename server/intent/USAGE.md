# 의도 엔진 사용법 (파이프라인 연결용)

`IntentEngine`(`server/intent/engine.py`)을 vision과 iot 사이에 연결할 때 필요한 내용임.
엔진은 vision이 만든 `GestureResult`(스펙 6.1)를 받아 `IntentResult`(스펙 6.2)를 만듦.
기준값과 동작 규칙은 [DECISIONS.md](DECISIONS.md)를 볼 것.

## 1. 생성

카메라(edge) 하나당 엔진 하나를 둠. 상태(선택된 기기, HELP 쿨다운)가 엔진 안에 있어서 카메라끼리 공유하면 섞임.

```python
from server.intent.device_matcher import DeviceRegion
from server.intent.engine import IntentEngine

engine = IntentEngine(
    regions=[DeviceRegion("fan-01", -15.0, 15.0), DeviceRegion("light-01", 75.0, 105.0)],
    frame_width=640,    # 선택. 기본 640x480
    frame_height=480,
    action_for=mapping_service.action_for,  # 선택. 기본: 엄지 위=ON, 엄지 아래=OFF, HELP=HELP
)
```

| 인자 | 내용 |
| --- | --- |
| `regions` | 기기 방향 영역(스펙 7.4 `pointing_region`). `DeviceRegion(device_id, min_angle_deg, max_angle_deg, enabled=True)`. `min > max`면 ±180°를 넘는 범위. 각도는 오른쪽 0°, 아래 +90° |
| `frame_width`, `frame_height` | 프레임 크기 기본값. 각도 계산에 화면 비율이 반영됨(스펙 4.3) |
| `action_for` | `GestureType → IntentAction \| None`. `None`을 돌려주면 그 제스처는 꺼진 매핑이라 `INVALID_GESTURE`로 취소함. web-app의 `GestureMappingService.action_for`와 모양이 같음 |
| `parameters` | `IntentParameters`. 선택 유지 3000ms, 안정 6프레임, 유지 500ms, 방향 변화 15°, HELP 쿨다운 5초 |

## 2. 프레임마다 `consume`

```python
result = engine.consume(gesture_result, frame_width=meta.width, frame_height=meta.height)
if result is not None:
    handle(result)
```

- 프레임마다 부름. 프레임 크기는 프레임 메타데이터 값을 넘기는 게 맞음(안 넘기면 생성자 기본값).
- 반환은 `IntentResult` 또는 `None`. **의미 있는 일이 있을 때만 결과가 나오고, 나머지는 `None`임.** `None`은 정상임.
- 잘못된 `GestureResult`(버전이 "1.0"이 아님, 제스처 값 오류, POINTING인데 벡터 없음, 좌표가 0~1 밖)는 `None`을 돌려주고 경고 로그만 남김.
- 안정화 기준(6프레임, 500ms)에 못 미친 제스처는 선택도 확정도 못 함.

## 3. 결과의 `status`별 처리

`command_from_intent`(`server/iot/command_service.py`)는 `status`를 보지 않음. **반드시 CONFIRMED만 넘길 것.**

| status | 의미 | 파이프라인이 할 일 |
| --- | --- | --- |
| `PENDING` | POINTING으로 기기가 선택됨. `target_device_id`에 기기 ID | 웹 이벤트 `device.selected`(스펙 9)의 근거. MQTT 명령은 만들지 않음 |
| `CONFIRMED` + `ON`/`OFF` | 엄지 제스처로 확정. `target_device_id`, `confirmed_at_ms` 있음 | `command_from_intent`로 MQTT 명령 생성(스펙 11). `gesture.confirmed` 이벤트의 근거 |
| `CONFIRMED` + `HELP` | HELP 확정. `target_device_id`는 `None` | MQTT로 보내지 않음. 도움 요청 1건 생성(스펙 10) |
| `CANCELLED` | 취소됨. `cancel_reason`에 사유 | 명령을 만들지 않음. 필요하면 사용자에게 알림 |

주의:
- `PENDING`, `CANCELLED` 결과의 `action`은 `HELP`로 나갈 수 있음(`IntentResult` 기본값 때문). **`action`만 보고 도움 요청으로 처리하면 안 되고 `status`를 먼저 확인해야 함.** 엄지 제스처가 취소될 때만 시도한 ON/OFF가 들어감.
- 결과의 `correlation_id`는 그 결과를 만든 프레임의 값임. 명령과 도움 요청까지 그대로 이어서 쓰면 추적됨.
- 같은 제스처가 이어지는 동안 CONFIRMED는 한 번만 나옴. HELP는 확정 후 5초 동안 다시 확정되지 않음.

취소 사유(`server/intent/cancel_reasons.py`):

| 사유 | 언제 |
| --- | --- |
| `TARGET_NOT_FOUND` | 가리킨 방향에 기기가 없음, 또는 선택 없이 엄지 제스처 |
| `AMBIGUOUS_TARGET` | 가리킨 방향에 기기 영역이 둘 이상 겹침 |
| `GESTURE_TIMEOUT` | 선택 후 3초 안에 엄지 제스처가 없음 |
| `DIRECTION_CHANGED` | 선택 중 포인팅 방향이 15°를 넘게 바뀜 |
| `INVALID_GESTURE` | 꺼진 매핑의 제스처로 확정하려 함 |

## 4. 주기적으로 `tick`

```python
result = engine.tick()  # 0.5~1초마다. 시각을 넘기려면 engine.tick(now_ms)
```

- 프레임이 안 와도(엣지 연결이 끊겨도) 선택 시간이 지나면 `GESTURE_TIMEOUT` 취소를 한 번 돌려주고 선택을 지움. 선택이 없거나 아직 안 지났으면 `None`.
- 안 부르면 다음 프레임이 올 때까지 선택이 남아 있음. 결과는 `consume`과 같은 방식으로 처리하면 됨.

## 5. 기기 위치가 바뀌면 `update_regions`

```python
engine.update_regions(new_regions)
```

- 웹에서 기기 위치를 등록·수정·삭제·비활성화하면 새 `DeviceRegion` 목록 전체를 넘김.
- 선택된 기기가 목록에서 빠지거나 비활성이 되면 선택을 조용히 지움(결과를 내지 않음).
- `DeviceRegion`의 필드 순서(device_id, min, max, enabled)는 바꾸지 않음. web-app이 위치 인자로 만들고 있음.
- 영역 경계는 포함이라 경계가 맞닿은 두 기기는 그 각도에서 `AMBIGUOUS_TARGET`이 됨. 경계를 조금 띄워 등록하는 게 좋음.

## 6. 지연시간 `latency_ms`

```python
ms = engine.latency_ms(result.correlation_id)  # int | None
```

- NFR-01(2초 이내) 확인용. 확정된 결과의 correlation_id에 대해 "제스처 감지 → 의도 확정" 시간을 ms로 돌려줌.
- 확정되지 않았거나 모르는 correlation_id면 `None`. 기록은 최대 1000개까지만 보관하고 오래된 것부터 지움.
- 감지 시각은 `GestureResult.detected_at_ms`, 확정 시각은 서버 현재 시각이므로 두 시계가 같은 UTC ms 기준이어야 의미가 있음.

## 7. 연결 예시

```python
def on_gesture(engine, gesture_result, meta):
    result = engine.consume(gesture_result, frame_width=meta.width, frame_height=meta.height)
    dispatch(result)

def on_timer(engine):  # 0.5~1초마다
    dispatch(engine.tick())

def dispatch(result):
    if result is None:
        return
    if result.status is IntentStatus.CONFIRMED and result.action is IntentAction.HELP:
        create_help_request(result)                      # MQTT로 보내지 않음
    elif result.status is IntentStatus.CONFIRMED:
        publish_mqtt(command_from_intent(result))        # ON/OFF
    # PENDING, CANCELLED는 웹 이벤트만 보냄
```
