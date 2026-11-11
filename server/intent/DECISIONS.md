# AI B (의도 판단) 결정 사항

스펙 v1.0에 정해진 것이 없어서 먼저 정하고 코드에 반영한 내용임.
값은 `server/intent/parameters.py`에서 바꿀 수 있음.

## 1. 기준값

| 값 | 결정 | 위치 |
| --- | --- | --- |
| 대상 선택 유지 시간 | 3000ms | `IntentParameters.selection_timeout_ms` |
| 안정화 프레임 | 6프레임 이상 (AI A의 `stability_checker.py`와 같은 값) | `min_stable_frames` |
| 제스처 유지 시간 | 500ms 이상 (AI A와 같은 값) | `min_hold_ms` |
| 선택 중 방향 변화 허용 | 15° (정확히 15°는 유지, 넘으면 취소) | `max_angle_delta_deg` |
| HELP 쿨다운 | 5초. 확정 후 5초 동안, 그리고 다른 제스처가 나오기 전까지 새 HELP는 무시함 | `help_cooldown_ms` |

## 2. 동작 규칙

- 아무 일도 없는 프레임은 결과를 내지 않음(`None`). PENDING, CONFIRMED, CANCELLED만 결과로 냄.
- 각도 기준은 오른쪽 0°, 아래 +90°, 위 -90°, 왼쪽 ±180°임. 웹 담당의 `device_service.py`, AI A의 `pointing_angle_deg`와 같음.
- 각도는 프레임 가로·세로 비율을 반영해 계산함(스펙 4.3). 프레임 크기를 안 주면 640×480으로 봄.
- `min_angle_deg > max_angle_deg`인 영역은 ±180°를 넘는 범위로 봄(예: 170 ~ -170).
- 영역 경계는 포함함. 경계가 맞닿은 두 기기는 그 각도에서 `AMBIGUOUS_TARGET`이 됨. `enabled=false` 기기는 매칭에서 뺌.
- 선택 중 방향이 바뀌면 `DIRECTION_CHANGED`로 취소만 하고, 새 대상은 다음 POINTING 프레임에서 고름.
- 같은 제스처가 이어지는 동안 CONFIRMED는 한 번만 나옴. 확정하면 선택을 지움.
- HELP를 확정하면 기기 선택도 지움(직후 엄지로 기기가 켜지지 않게 하기 위함).
- 확정(CONFIRMED)된 결과만 지연시간을 기록함(NFR-01).
- 잘못된 GestureResult(버전이 "1.0"이 아님, 제스처 값 오류, POINTING인데 벡터 없음, 좌표가 0~1 밖)는 처리하지 않고 경고 로그만 남김.

## 3. 확인 필요

| 대상 | 내용 |
| --- | --- |
| 웹·통합 | `INVALID_GESTURE`는 "매핑이 꺼진 제스처로 확정하려 할 때"만 사용함. 엔진은 `action_for(gesture)` 함수를 받으며, web-app의 `GestureMappingService.action_for`와 모양이 같음. |
| 웹·통합 | 기기 위치가 바뀌면 `IntentEngine.update_regions(...)` 호출이 필요함. |
| 통합 | PENDING·CANCELLED 결과의 `action`이 `HELP`로 나감(`IntentResult` 기본값 때문). `action`을 null로 허용하려면 스키마와 `IntentResult`를 같이 바꿔야 해서 합의가 필요함. 그 전까지는 `status`를 먼저 확인해야 함. |
| 통합 | `command_from_intent`(`server/iot/command_service.py`)가 `status`를 보지 않음. 파이프라인에서 CONFIRMED만 넘기거나 함수에서 status 검사가 필요함. |
| AI A | `mirrored`, `rotation_deg` 보정을 누가 할지 정해야 함. A가 랜드마크 단계에서 반영하는 쪽을 제안함. 90°·270° 회전이면 B에 넘기는 프레임 가로·세로도 바뀐 값이어야 함. |
| AI A | 손이 사라질 때 `gesture=UNKNOWN`, `stable_frames=0`인 결과가 필요함. 없으면 HELP를 다시 요청할 수 없음. |
| 웹 | ±180°를 넘는 영역(min > max)을 등록할 수 없음. B는 이미 처리하므로 웹에서 받을 수 있게 해야 함. 영역끼리 겹침 검사도 있으면 `AMBIGUOUS_TARGET`이 줄어듦. 경계는 맞닿게 하지 말고 조금 띄우는 게 좋음. |
| 웹 | `DeviceService.pointing_regions()`가 `DeviceRegion`을 위치 인자로 만듦. 필드 순서(device_id, min, max, enabled)는 유지하지만 키워드 인자가 더 안전함. |
