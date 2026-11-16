"""최종 의도 판단 테스트.

server/intent/engine.py(IntentEngine.consume)의 동작을 고정한다.
엔진은 등록된 기기 방향 영역(DeviceRegion)과 포인팅 벡터로 대상을 직접 찾는다.
consume은 의미 있는 일(대상 선택, 의도 확정, 취소)이 있을 때만 IntentResult를 돌려주고, 나머지 프레임에는 None을 돌려준다.
시각은 detected_at_ms로 직접 넣어 실제 시간에 의존하지 않는다.
"""

import math

import pytest

from server.intent.cancel_reasons import (
    AMBIGUOUS_TARGET,
    CANCEL_REASONS,
    DIRECTION_CHANGED,
    GESTURE_TIMEOUT,
    INVALID_GESTURE,
    TARGET_NOT_FOUND,
)
from server.intent.device_matcher import DeviceRegion
from server.intent.engine import DEFAULT_GESTURE_ACTIONS, IntentEngine
from server.intent.parameters import IntentParameters
from server.intent.state_machine import IntentState
from shared.types import GestureResult, GestureType, IntentAction, IntentStatus, PointingVector

PARAMS = IntentParameters()
T0 = 10_000
TIMEOUT_MS = PARAMS.selection_timeout_ms
COOLDOWN_MS = PARAMS.help_cooldown_ms

FAN = DeviceRegion("fan-01", -15.0, 15.0)  # 오른쪽
LIGHT = DeviceRegion("light-01", 75.0, 105.0)  # 아래
REGIONS = [FAN, LIGHT]
TV = DeviceRegion("tv-01", -5.0, 5.0)  # FAN 안쪽과 겹친다
DISABLED_FAN = DeviceRegion("fan-01", -15.0, 15.0, enabled=False)


def toward(angle_deg: float, width: int = 640, height: int = 480) -> PointingVector:
    """화면 각도(오른쪽 0°, 아래 +90°)를 가리키는 정규화 벡터. 기본 프레임 640x480 기준."""
    rad = math.radians(angle_deg)
    return PointingVector(0.5, 0.5, 0.5 + 100 * math.cos(rad) / width, 0.5 + 100 * math.sin(rad) / height)


def gesture(
    kind: GestureType,
    at_ms: int,
    *,
    correlation_id: str = "corr-1",
    vector: PointingVector | None = None,
    stable_frames: int = PARAMS.min_stable_frames,
    hold_time_ms: int = PARAMS.min_hold_ms,
) -> GestureResult:
    """기본값은 안정화 기준을 딱 맞춘 제스처다. POINTING은 기본으로 오른쪽(0°)을 가리킨다."""
    if kind is GestureType.POINTING and vector is None:
        vector = toward(0.0)
    return GestureResult(
        frame_id=f"frame-{at_ms}",
        correlation_id=correlation_id,
        gesture=kind,
        pointing_vector=vector,
        stable_frames=stable_frames,
        hold_time_ms=hold_time_ms,
        detected_at_ms=at_ms,
    )


def point(angle_deg: float, at_ms: int, **kwargs) -> GestureResult:
    return gesture(GestureType.POINTING, at_ms, vector=toward(angle_deg), **kwargs)


@pytest.fixture
def engine() -> IntentEngine:
    return IntentEngine(REGIONS)


@pytest.fixture
def selected_engine(engine: IntentEngine) -> IntentEngine:
    result = engine.consume(point(0.0, T0))
    assert result.status is IntentStatus.PENDING
    assert result.target_device_id == "fan-01"
    return engine


# --- HELP ------------------------------------------------------------------


def test_help_is_confirmed_without_target(engine):
    result = engine.consume(gesture(GestureType.HELP, T0))
    assert result.action is IntentAction.HELP
    assert result.status is IntentStatus.CONFIRMED
    assert result.target_device_id is None
    assert result.confirmed_at_ms is not None
    assert result.cancel_reason is None


def test_holding_help_confirms_only_once(engine):
    assert engine.consume(gesture(GestureType.HELP, T0)).status is IntentStatus.CONFIRMED
    assert engine.consume(gesture(GestureType.HELP, T0 + 100)) is None


def test_help_needs_a_different_gesture_before_next_request(engine):
    engine.consume(gesture(GestureType.HELP, T0))
    assert engine.consume(gesture(GestureType.HELP, T0 + COOLDOWN_MS + 1_000)) is None


def test_help_cooldown_blocks_quick_repeat(engine):
    engine.consume(gesture(GestureType.HELP, T0))
    assert engine.consume(gesture(GestureType.UNKNOWN, T0 + 100)) is None
    assert engine.consume(gesture(GestureType.HELP, T0 + 1_000)) is None
    assert engine.consume(gesture(GestureType.HELP, T0 + COOLDOWN_MS)).status is IntentStatus.CONFIRMED


def test_help_drops_device_selection(selected_engine):
    assert selected_engine.consume(gesture(GestureType.HELP, T0 + 500)).status is IntentStatus.CONFIRMED
    assert selected_engine.state.state is IntentState.IDLE
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_000))
    assert result.cancel_reason == TARGET_NOT_FOUND


# --- 포인팅으로 대상 선택 -------------------------------------------------------


def test_pointing_at_device_selects_it(engine):
    result = engine.consume(point(0.0, T0))
    assert result.status is IntentStatus.PENDING
    assert result.target_device_id == "fan-01"
    assert result.confirmed_at_ms is None
    assert result.cancel_reason is None
    assert engine.state.target_device_id == "fan-01"
    assert engine.state.selected_angle_deg == pytest.approx(0.0, abs=1e-9)


def test_keeping_pointing_at_same_device_returns_none_and_keeps_selection_alive(selected_engine):
    assert selected_engine.consume(point(2.0, T0 + 2_000)) is None
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 4_500)).status is IntentStatus.CONFIRMED


def test_small_move_keeps_selection_even_over_neighbouring_region():
    lamp = DeviceRegion("lamp-01", 16.0, 40.0)
    engine = IntentEngine([FAN, lamp])
    engine.consume(point(5.0, T0))
    assert engine.consume(point(18.0, T0 + 100)) is None  # 13° 이동: 허용 각도 안
    assert engine.state.target_device_id == "fan-01"


def test_large_move_cancels_with_direction_changed(selected_engine):
    result = selected_engine.consume(point(PARAMS.max_angle_delta_deg + 5, T0 + 100))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == DIRECTION_CHANGED
    assert result.target_device_id == "fan-01"
    assert selected_engine.state.state is IntentState.IDLE


def test_new_device_is_selected_on_the_frame_after_direction_change(selected_engine):
    selected_engine.consume(point(90.0, T0 + 100))
    result = selected_engine.consume(point(90.0, T0 + 200))
    assert result.status is IntentStatus.PENDING
    assert result.target_device_id == "light-01"


def test_pointing_at_nothing_reports_target_not_found_once(engine):
    first = engine.consume(point(45.0, T0))
    assert first.status is IntentStatus.CANCELLED
    assert first.cancel_reason == TARGET_NOT_FOUND
    assert first.target_device_id is None
    assert engine.consume(point(50.0, T0 + 100)) is None


def test_target_not_found_is_reported_again_after_another_gesture(engine):
    engine.consume(point(45.0, T0))
    engine.consume(gesture(GestureType.UNKNOWN, T0 + 100))
    assert engine.consume(point(45.0, T0 + 200)).cancel_reason == TARGET_NOT_FOUND


def test_pointing_at_overlap_reports_ambiguous_target():
    engine = IntentEngine([FAN, TV])
    result = engine.consume(point(0.0, T0))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == AMBIGUOUS_TARGET
    assert engine.state.state is IntentState.IDLE


def test_pointing_reason_change_is_reported():
    engine = IntentEngine([FAN, TV])
    assert engine.consume(point(0.0, T0)).cancel_reason == AMBIGUOUS_TARGET
    assert engine.consume(point(45.0, T0 + 100)).cancel_reason == TARGET_NOT_FOUND


def test_disabled_device_is_not_selected():
    engine = IntentEngine([DISABLED_FAN])
    assert engine.consume(point(0.0, T0)).cancel_reason == TARGET_NOT_FOUND


def test_wraparound_region_is_selected():
    engine = IntentEngine([DeviceRegion("door-01", 170.0, -170.0)])
    assert engine.consume(point(180.0, T0)).target_device_id == "door-01"


# --- 프레임 크기 (D2: 프레임마다, 없으면 기본 640x480) ---------------------------


DIAGONAL = PointingVector(0.5, 0.5, 0.6, 0.6)  # 640x480에서 약 36.9°, 480x480에서 45°
SHELF = DeviceRegion("shelf-01", 30.0, 40.0)
LAMP = DeviceRegion("lamp-01", 42.0, 50.0)


def test_default_frame_size_is_640_by_480():
    engine = IntentEngine([SHELF, LAMP])
    assert engine.consume(gesture(GestureType.POINTING, T0, vector=DIAGONAL)).target_device_id == "shelf-01"


def test_frame_size_per_frame_is_used():
    engine = IntentEngine([SHELF, LAMP])
    result = engine.consume(gesture(GestureType.POINTING, T0, vector=DIAGONAL), frame_width=480, frame_height=480)
    assert result.target_device_id == "lamp-01"


def test_frame_size_from_constructor_is_used():
    engine = IntentEngine([SHELF, LAMP], frame_width=480, frame_height=480)
    assert engine.consume(gesture(GestureType.POINTING, T0, vector=DIAGONAL)).target_device_id == "lamp-01"


def test_invalid_frame_size_raises(engine):
    with pytest.raises(ValueError):
        engine.consume(point(0.0, T0), frame_width=0)


# --- 기기 영역 바꾸기 (update_regions) ------------------------------------------


def test_update_regions_is_used_for_next_pointing():
    engine = IntentEngine()
    assert engine.consume(point(0.0, T0)).cancel_reason == TARGET_NOT_FOUND
    engine.update_regions([FAN])
    assert engine.regions == (FAN,)
    assert engine.consume(point(0.0, T0 + 100)).target_device_id == "fan-01"


@pytest.mark.parametrize(
    "new_regions",
    [[LIGHT], [DISABLED_FAN, LIGHT]],
    ids=["removed", "disabled"],
)
def test_removing_or_disabling_selected_device_drops_selection(selected_engine, new_regions):
    selected_engine.update_regions(new_regions)
    assert selected_engine.state.state is IntentState.IDLE
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 500)).cancel_reason == TARGET_NOT_FOUND


def test_updating_regions_keeps_selection_when_device_remains(selected_engine):
    selected_engine.update_regions([FAN, LIGHT, DeviceRegion("tv-01", 160.0, 175.0)])
    assert selected_engine.state.target_device_id == "fan-01"


# --- 명령 (엄지 위·아래) ------------------------------------------------------


@pytest.mark.parametrize(
    "kind, action",
    [(GestureType.THUMB_UP, IntentAction.ON), (GestureType.THUMB_DOWN, IntentAction.OFF)],
)
def test_thumb_after_selection_confirms_command(selected_engine, kind, action):
    result = selected_engine.consume(gesture(kind, T0 + 1_000))
    assert result.status is IntentStatus.CONFIRMED
    assert result.action is action
    assert result.target_device_id == "fan-01"
    assert result.confirmed_at_ms is not None
    assert result.cancel_reason is None


def test_confirm_returns_state_to_idle(selected_engine):
    selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_000))
    assert selected_engine.state.state is IntentState.IDLE


def test_holding_thumb_up_confirms_only_once(selected_engine):
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_000)).status is IntentStatus.CONFIRMED
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_100)) is None


def test_new_command_needs_a_new_selection(selected_engine):
    selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_000))
    selected_engine.consume(gesture(GestureType.UNKNOWN, T0 + 1_100))
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_200))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == TARGET_NOT_FOUND


def test_thumb_without_selection_is_cancelled(engine):
    result = engine.consume(gesture(GestureType.THUMB_UP, T0))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == TARGET_NOT_FOUND
    assert result.target_device_id is None
    assert result.action is IntentAction.ON


def test_holding_thumb_without_selection_cancels_once(engine):
    assert engine.consume(gesture(GestureType.THUMB_UP, T0)).status is IntentStatus.CANCELLED
    assert engine.consume(gesture(GestureType.THUMB_UP, T0 + 100)) is None


# --- 제스처 매핑 (D4: 매핑이 꺼진 제스처는 INVALID_GESTURE) ----------------------


def without(disabled: GestureType):
    return lambda kind: None if kind is disabled else DEFAULT_GESTURE_ACTIONS.get(kind)


def test_disabled_command_gesture_cancels_with_invalid_gesture():
    engine = IntentEngine(REGIONS, action_for=without(GestureType.THUMB_UP))
    engine.consume(point(0.0, T0))
    result = engine.consume(gesture(GestureType.THUMB_UP, T0 + 500))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == INVALID_GESTURE
    assert result.target_device_id == "fan-01"
    assert engine.state.state is IntentState.IDLE
    assert engine.consume(gesture(GestureType.THUMB_UP, T0 + 600)) is None


def test_disabled_help_gesture_cancels_with_invalid_gesture():
    engine = IntentEngine(REGIONS, action_for=without(GestureType.HELP))
    result = engine.consume(gesture(GestureType.HELP, T0))
    assert result.cancel_reason == INVALID_GESTURE
    assert result.target_device_id is None


def test_remapped_gestures_are_used():
    swapped = {GestureType.THUMB_UP: IntentAction.OFF, GestureType.THUMB_DOWN: IntentAction.HELP}
    engine = IntentEngine(REGIONS, action_for=swapped.get)
    engine.consume(point(0.0, T0))
    assert engine.consume(gesture(GestureType.THUMB_UP, T0 + 500)).action is IntentAction.OFF
    help_result = engine.consume(gesture(GestureType.THUMB_DOWN, T0 + 600))
    assert help_result.action is IntentAction.HELP
    assert help_result.status is IntentStatus.CONFIRMED


# --- 선택 시간 초과 -----------------------------------------------------------


def test_selection_timeout_is_cancelled_with_gesture_timeout(selected_engine):
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + TIMEOUT_MS + 1))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == GESTURE_TIMEOUT
    assert result.target_device_id == "fan-01"
    assert selected_engine.state.state is IntentState.IDLE


def test_timeout_is_reported_once_on_any_frame(selected_engine):
    assert selected_engine.consume(gesture(GestureType.UNKNOWN, T0 + TIMEOUT_MS + 1)).cancel_reason == GESTURE_TIMEOUT
    assert selected_engine.consume(gesture(GestureType.UNKNOWN, T0 + TIMEOUT_MS + 2)) is None


def test_frame_from_before_selection_is_ignored(selected_engine):
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, T0 - 1)) is None
    assert selected_engine.state.target_device_id == "fan-01"
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 100)).status is IntentStatus.CONFIRMED


# --- 안정화 기준 (스펙 15장: 안정화 미충족 제스처는 확정하지 않음) ------------


@pytest.mark.parametrize(
    "stable_frames, hold_time_ms",
    [(PARAMS.min_stable_frames - 1, PARAMS.min_hold_ms), (PARAMS.min_stable_frames, PARAMS.min_hold_ms - 1)],
)
def test_unstable_gesture_is_not_confirmed(selected_engine, stable_frames, hold_time_ms):
    unstable = gesture(GestureType.THUMB_UP, T0 + 1_000, stable_frames=stable_frames, hold_time_ms=hold_time_ms)
    assert selected_engine.consume(unstable) is None
    assert selected_engine.state.target_device_id == "fan-01"


def test_unstable_help_is_not_confirmed(engine):
    assert engine.consume(gesture(GestureType.HELP, T0, stable_frames=PARAMS.min_stable_frames - 1)) is None


def test_unstable_pointing_does_not_select(engine):
    assert engine.consume(point(0.0, T0, hold_time_ms=PARAMS.min_hold_ms - 1)) is None
    assert engine.state.state is IntentState.IDLE


def test_unknown_gesture_returns_none_and_keeps_selection(selected_engine):
    assert selected_engine.consume(gesture(GestureType.UNKNOWN, T0 + 500)) is None
    assert selected_engine.state.target_device_id == "fan-01"


# --- 받은 메시지 검사 (스펙 3.3, 14.6, 14.7) ------------------------------------


def broken(field: str, value, kind: GestureType = GestureType.THUMB_UP) -> GestureResult:
    result = gesture(kind, T0 + 500, correlation_id="corr-bad")
    setattr(result, field, value)
    return result


@pytest.mark.parametrize(
    "field, value, problem",
    [
        ("schema_version", "2.0", "UNSUPPORTED_VERSION"),
        ("gesture", "WAVE", "INVALID_SCHEMA: gesture"),
        ("gesture", None, "INVALID_SCHEMA: gesture"),
        ("detected_at_ms", None, "INVALID_SCHEMA: detected_at_ms"),
        ("detected_at_ms", 10_500.5, "INVALID_SCHEMA: detected_at_ms"),
        ("stable_frames", True, "INVALID_SCHEMA: stable_frames"),
        ("hold_time_ms", "500", "INVALID_SCHEMA: hold_time_ms"),
    ],
)
def test_bad_message_is_ignored_and_logged(selected_engine, caplog, field, value, problem):
    with caplog.at_level("WARNING", logger="server.intent.engine"):
        assert selected_engine.consume(broken(field, value)) is None
    assert selected_engine.state.target_device_id == "fan-01"
    assert caplog.messages == [f"gesture result ignored: {problem} (frame_id=frame-{T0 + 500}, correlation_id=corr-bad)"]


def test_pointing_without_vector_is_ignored_and_logged(engine, caplog):
    with caplog.at_level("WARNING", logger="server.intent.engine"):
        assert engine.consume(broken("pointing_vector", None, GestureType.POINTING)) is None
    assert engine.state.state is IntentState.IDLE
    assert caplog.messages == [
        f"gesture result ignored: INVALID_SCHEMA: pointing_vector (frame_id=frame-{T0 + 500}, correlation_id=corr-bad)"
    ]


def test_pointing_vector_outside_0_to_1_is_rejected(engine, caplog):
    result = point(0.0, T0)
    result.pointing_vector.end_x = 1.5  # 만든 뒤에 바뀐 좌표도 잡는다
    with caplog.at_level("WARNING", logger="server.intent.engine"):
        assert engine.consume(result) is None
    assert "INVALID_SCHEMA: pointing_vector" in caplog.messages[0]
    assert "1.5" not in caplog.text


def test_gesture_given_as_plain_string_is_accepted(selected_engine):
    result = gesture(GestureType.THUMB_UP, T0 + 500)
    result.gesture = "THUMB_UP"
    confirmed = selected_engine.consume(result)
    assert confirmed.status is IntentStatus.CONFIRMED
    assert confirmed.action is IntentAction.ON


# --- 결과 형식 (스펙 6.2) -----------------------------------------------------


def test_correlation_id_is_passed_through():
    engine = IntentEngine(REGIONS)
    results = [
        engine.consume(gesture(GestureType.HELP, 10_000, correlation_id="c-help")),
        engine.consume(point(0.0, 10_100, correlation_id="c-point")),
        engine.consume(gesture(GestureType.THUMB_UP, 10_200, correlation_id="c-thumb")),
        engine.consume(gesture(GestureType.THUMB_DOWN, 10_300, correlation_id="c-cancel")),
    ]
    assert [result.correlation_id for result in results] == ["c-help", "c-point", "c-thumb", "c-cancel"]


def all_kinds_of_results() -> list:
    engine = IntentEngine(REGIONS)
    return [
        engine.consume(point(0.0, T0)),  # PENDING
        engine.consume(gesture(GestureType.THUMB_UP, T0 + 100)),  # CONFIRMED
        engine.consume(gesture(GestureType.THUMB_DOWN, T0 + 200)),  # CANCELLED: TARGET_NOT_FOUND
        engine.consume(point(0.0, T0 + 300)),  # PENDING
        engine.consume(point(90.0, T0 + 400)),  # CANCELLED: DIRECTION_CHANGED
        engine.consume(gesture(GestureType.HELP, T0 + 500)),  # CONFIRMED: HELP
    ]


def test_result_fields_follow_spec_6_2():
    results = all_kinds_of_results()
    assert [result.status for result in results] == [
        IntentStatus.PENDING, IntentStatus.CONFIRMED, IntentStatus.CANCELLED,
        IntentStatus.PENDING, IntentStatus.CANCELLED, IntentStatus.CONFIRMED,
    ]
    for result in results:
        data = result.as_dict()
        assert data["schema_version"] == "1.0"
        assert (data["confirmed_at_ms"] is not None) == (result.status is IntentStatus.CONFIRMED)
        if result.status is IntentStatus.CANCELLED:
            assert data["cancel_reason"] in CANCEL_REASONS
        else:
            assert data["cancel_reason"] is None


def test_each_result_gets_its_own_intent_id():
    results = all_kinds_of_results()
    assert len({result.intent_id for result in results}) == len(results)


def test_confirmed_result_serializes_to_spec_values(selected_engine):
    data = selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_000)).as_dict()
    assert data["action"] == "ON"
    assert data["status"] == "CONFIRMED"
    assert data["target_device_id"] == "fan-01"


# --- 지연시간 기록 (NFR-01) ---------------------------------------------------


@pytest.fixture
def fixed_clock(monkeypatch):
    """확정 시각(now_ms)을 고정한다. 제스처 감지 시각은 detected_at_ms로 직접 넣는다."""
    monkeypatch.setattr("server.intent.engine.now_ms", lambda: T0 + 1_250)


def test_confirmed_command_records_latency(selected_engine, fixed_clock):
    selected_engine.consume(gesture(GestureType.THUMB_UP, T0 + 1_000, correlation_id="c-cmd"))
    assert selected_engine.latency_ms("c-cmd") == 250


def test_confirmed_help_records_latency(engine, fixed_clock):
    engine.consume(gesture(GestureType.HELP, T0 + 1_100, correlation_id="c-help"))
    assert engine.latency_ms("c-help") == 150


def test_only_confirmed_results_record_latency(engine, fixed_clock):
    assert engine.consume(point(0.0, T0, correlation_id="c-pending")).status is IntentStatus.PENDING
    assert engine.consume(gesture(GestureType.THUMB_DOWN, T0 + 100, correlation_id="c-confirm")).status is IntentStatus.CONFIRMED
    assert engine.consume(gesture(GestureType.THUMB_UP, T0 + 200, correlation_id="c-cancel")).status is IntentStatus.CANCELLED
    assert engine.latency_ms("c-pending") is None
    assert engine.latency_ms("c-confirm") == 1_150
    assert engine.latency_ms("c-cancel") is None


def test_latency_is_none_for_unknown_correlation_id(engine):
    assert engine.latency_ms("unknown") is None


def test_empty_correlation_id_is_not_tracked(engine, fixed_clock):
    engine.consume(gesture(GestureType.HELP, T0, correlation_id=""))
    assert engine.latency.timestamps == {}


# --- 기준값 ------------------------------------------------------------------


def test_default_help_cooldown_is_5_seconds():
    assert PARAMS.help_cooldown_ms == 5_000


def test_custom_parameters_are_used():
    params = IntentParameters(selection_timeout_ms=500, max_angle_delta_deg=5.0, min_stable_frames=2, min_hold_ms=100)
    engine = IntentEngine(REGIONS, parameters=params)
    assert engine.state.timeout_ms == 500
    assert engine.state.max_angle_delta_deg == 5.0
    engine.consume(point(0.0, T0, stable_frames=2, hold_time_ms=100))
    assert engine.consume(point(6.0, T0 + 100, stable_frames=2, hold_time_ms=100)).cancel_reason == DIRECTION_CHANGED


# --- tick: 프레임이 없어도 선택 시간 만료 ----------------------------------------


def test_tick_does_nothing_without_selection(engine):
    assert engine.tick(T0 + TIMEOUT_MS * 10) is None


def test_tick_within_timeout_keeps_selection(selected_engine):
    assert selected_engine.tick(T0 + TIMEOUT_MS) is None
    assert selected_engine.state.state is IntentState.TARGET_SELECTED


def test_tick_after_timeout_cancels_once_with_gesture_timeout(selected_engine):
    result = selected_engine.tick(T0 + TIMEOUT_MS + 1)
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == GESTURE_TIMEOUT
    assert result.target_device_id == "fan-01"
    assert result.correlation_id == "corr-1"
    assert selected_engine.state.state is IntentState.IDLE
    assert selected_engine.tick(T0 + TIMEOUT_MS + 2) is None


def test_tick_uses_correlation_id_of_latest_pointing_frame(engine):
    engine.consume(point(0.0, T0, correlation_id="first"))
    engine.consume(point(0.0, T0 + 1_000, correlation_id="second"))
    assert engine.tick(T0 + 1_000 + TIMEOUT_MS + 1).correlation_id == "second"


def test_keep_alive_pointing_postpones_tick_timeout(selected_engine):
    selected_engine.consume(point(0.0, T0 + 2_000))
    assert selected_engine.tick(T0 + TIMEOUT_MS + 1) is None
    assert selected_engine.tick(T0 + 2_000 + TIMEOUT_MS + 1).cancel_reason == GESTURE_TIMEOUT


def test_frame_after_tick_timeout_is_not_reported_again(selected_engine):
    selected_engine.tick(T0 + TIMEOUT_MS + 1)
    assert selected_engine.consume(gesture(GestureType.UNKNOWN, T0 + TIMEOUT_MS + 2)) is None


def test_tick_without_time_uses_current_clock(selected_engine, monkeypatch):
    monkeypatch.setattr("server.intent.engine.now_ms", lambda: T0 + TIMEOUT_MS)
    assert selected_engine.tick() is None
    monkeypatch.setattr("server.intent.engine.now_ms", lambda: T0 + TIMEOUT_MS + 1)
    assert selected_engine.tick().cancel_reason == GESTURE_TIMEOUT
