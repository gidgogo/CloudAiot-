"""최종 의도 판단 테스트.

server/intent/engine.py(IntentEngine.consume)의 동작을 고정한다.
consume은 의미 있는 일(대상 선택, 의도 확정, 취소)이 있을 때만 IntentResult를 돌려주고, 나머지 프레임에는 None을 돌려준다.
시각은 detected_at_ms로 직접 넣어 실제 시간에 의존하지 않는다.
"""

import pytest

from server.intent.cancel_reasons import GESTURE_TIMEOUT, TARGET_NOT_FOUND
from server.intent.engine import IntentEngine
from server.intent.parameters import IntentParameters
from server.intent.state_machine import IntentState
from shared.types import GestureResult, GestureType, IntentAction, IntentStatus, PointingVector

PARAMS = IntentParameters()
SELECTED_AT = 10_000
TIMEOUT_MS = PARAMS.selection_timeout_ms
COOLDOWN_MS = PARAMS.help_cooldown_ms


def gesture(
    kind: GestureType,
    at_ms: int,
    *,
    correlation_id: str = "corr-1",
    stable_frames: int = PARAMS.min_stable_frames,
    hold_time_ms: int = PARAMS.min_hold_ms,
) -> GestureResult:
    """기본값은 안정화 기준을 딱 맞춘 제스처다."""
    vector = PointingVector(0.42, 0.61, 0.75, 0.38) if kind is GestureType.POINTING else None
    return GestureResult(
        frame_id=f"frame-{at_ms}",
        correlation_id=correlation_id,
        gesture=kind,
        pointing_vector=vector,
        stable_frames=stable_frames,
        hold_time_ms=hold_time_ms,
        detected_at_ms=at_ms,
    )


@pytest.fixture
def engine() -> IntentEngine:
    return IntentEngine()


@pytest.fixture
def selected_engine(engine: IntentEngine) -> IntentEngine:
    result = engine.consume(gesture(GestureType.POINTING, SELECTED_AT), target_device_id="fan-01")
    assert result.status is IntentStatus.PENDING
    return engine


# --- HELP ------------------------------------------------------------------


def test_help_is_confirmed_without_target(engine):
    result = engine.consume(gesture(GestureType.HELP, SELECTED_AT))
    assert result.action is IntentAction.HELP
    assert result.status is IntentStatus.CONFIRMED
    assert result.target_device_id is None
    assert result.confirmed_at_ms is not None
    assert result.cancel_reason is None


def test_holding_help_confirms_only_once(engine):
    assert engine.consume(gesture(GestureType.HELP, SELECTED_AT)).status is IntentStatus.CONFIRMED
    assert engine.consume(gesture(GestureType.HELP, SELECTED_AT + 100)) is None


def test_help_needs_a_different_gesture_before_next_request(engine):
    engine.consume(gesture(GestureType.HELP, SELECTED_AT))
    assert engine.consume(gesture(GestureType.HELP, SELECTED_AT + COOLDOWN_MS + 1_000)) is None


def test_help_cooldown_blocks_quick_repeat(engine):
    engine.consume(gesture(GestureType.HELP, SELECTED_AT))
    assert engine.consume(gesture(GestureType.UNKNOWN, SELECTED_AT + 100)) is None
    assert engine.consume(gesture(GestureType.HELP, SELECTED_AT + 1_000)) is None
    again = engine.consume(gesture(GestureType.HELP, SELECTED_AT + COOLDOWN_MS))
    assert again.status is IntentStatus.CONFIRMED


# --- 대상 선택 ---------------------------------------------------------------


def test_pointing_with_target_selects_device(engine):
    result = engine.consume(gesture(GestureType.POINTING, SELECTED_AT), target_device_id="fan-01")
    assert result.status is IntentStatus.PENDING
    assert result.target_device_id == "fan-01"
    assert result.confirmed_at_ms is None
    assert engine.state.target_device_id == "fan-01"


def test_keeping_pointing_at_same_device_returns_none_and_keeps_selection_alive(selected_engine):
    still_pointing = gesture(GestureType.POINTING, SELECTED_AT + 2_000)
    assert selected_engine.consume(still_pointing, target_device_id="fan-01") is None
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 4_500))
    assert result.status is IntentStatus.CONFIRMED


def test_pointing_at_another_device_selects_it(selected_engine):
    result = selected_engine.consume(
        gesture(GestureType.POINTING, SELECTED_AT + 500), target_device_id="light-01"
    )
    assert result.status is IntentStatus.PENDING
    assert result.target_device_id == "light-01"


def test_pointing_without_target_returns_none(engine):
    assert engine.consume(gesture(GestureType.POINTING, SELECTED_AT)) is None
    assert engine.state.state is IntentState.IDLE


# --- 명령 (엄지 위·아래) ------------------------------------------------------


@pytest.mark.parametrize(
    "kind, action",
    [(GestureType.THUMB_UP, IntentAction.ON), (GestureType.THUMB_DOWN, IntentAction.OFF)],
)
def test_thumb_after_selection_confirms_command(selected_engine, kind, action):
    result = selected_engine.consume(gesture(kind, SELECTED_AT + 1_000))
    assert result.status is IntentStatus.CONFIRMED
    assert result.action is action
    assert result.target_device_id == "fan-01"
    assert result.confirmed_at_ms is not None
    assert result.cancel_reason is None


def test_confirm_returns_state_to_idle(selected_engine):
    selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000))
    assert selected_engine.state.state is IntentState.IDLE


def test_holding_thumb_up_confirms_only_once(selected_engine):
    first = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000))
    second = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_100))
    assert first.status is IntentStatus.CONFIRMED
    assert second is None


def test_new_command_needs_a_new_selection(selected_engine):
    selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000))
    selected_engine.consume(gesture(GestureType.UNKNOWN, SELECTED_AT + 1_100))
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_200))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == TARGET_NOT_FOUND


def test_thumb_without_selection_is_cancelled(engine):
    result = engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == TARGET_NOT_FOUND
    assert result.target_device_id is None
    assert result.action is IntentAction.ON


def test_holding_thumb_without_selection_cancels_once(engine):
    assert engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT)).status is IntentStatus.CANCELLED
    assert engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 100)) is None


# --- 선택 시간 초과 -----------------------------------------------------------


def test_selection_timeout_is_cancelled_with_gesture_timeout(selected_engine):
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + TIMEOUT_MS + 1))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == GESTURE_TIMEOUT
    assert result.target_device_id == "fan-01"
    assert selected_engine.state.state is IntentState.IDLE


def test_timeout_is_reported_once_on_any_frame(selected_engine):
    timed_out = selected_engine.consume(gesture(GestureType.UNKNOWN, SELECTED_AT + TIMEOUT_MS + 1))
    assert timed_out.cancel_reason == GESTURE_TIMEOUT
    assert selected_engine.consume(gesture(GestureType.UNKNOWN, SELECTED_AT + TIMEOUT_MS + 2)) is None


def test_frame_from_before_selection_is_ignored(selected_engine):
    assert selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT - 1)) is None
    assert selected_engine.state.target_device_id == "fan-01"
    result = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 100))
    assert result.status is IntentStatus.CONFIRMED


# --- 안정화 기준 (스펙 15장: 안정화 미충족 제스처는 확정하지 않음) ------------


@pytest.mark.parametrize(
    "stable_frames, hold_time_ms",
    [(PARAMS.min_stable_frames - 1, PARAMS.min_hold_ms), (PARAMS.min_stable_frames, PARAMS.min_hold_ms - 1)],
)
def test_unstable_gesture_is_not_confirmed(selected_engine, stable_frames, hold_time_ms):
    unstable = gesture(
        GestureType.THUMB_UP,
        SELECTED_AT + 1_000,
        stable_frames=stable_frames,
        hold_time_ms=hold_time_ms,
    )
    assert selected_engine.consume(unstable) is None
    assert selected_engine.state.target_device_id == "fan-01"


def test_unstable_help_is_not_confirmed(engine):
    unstable = gesture(GestureType.HELP, SELECTED_AT, stable_frames=PARAMS.min_stable_frames - 1)
    assert engine.consume(unstable) is None


def test_unstable_pointing_does_not_select(engine):
    unstable = gesture(GestureType.POINTING, SELECTED_AT, hold_time_ms=PARAMS.min_hold_ms - 1)
    assert engine.consume(unstable, target_device_id="fan-01") is None
    assert engine.state.state is IntentState.IDLE


# --- 아무 일도 없는 프레임 -----------------------------------------------------


def test_unknown_gesture_returns_none_and_keeps_selection(selected_engine):
    assert selected_engine.consume(gesture(GestureType.UNKNOWN, SELECTED_AT + 500)) is None
    assert selected_engine.state.target_device_id == "fan-01"


# --- 결과 형식 ---------------------------------------------------------------


def test_correlation_id_is_passed_through():
    engine = IntentEngine()
    results = [
        engine.consume(gesture(GestureType.HELP, 10_000, correlation_id="c-help")),
        engine.consume(gesture(GestureType.POINTING, 10_100, correlation_id="c-point"), target_device_id="fan-01"),
        engine.consume(gesture(GestureType.THUMB_UP, 10_200, correlation_id="c-thumb")),
        engine.consume(gesture(GestureType.THUMB_DOWN, 10_300, correlation_id="c-cancel")),
    ]
    assert [result.correlation_id for result in results] == ["c-help", "c-point", "c-thumb", "c-cancel"]


def test_each_result_gets_its_own_intent_id(engine):
    pending = engine.consume(gesture(GestureType.POINTING, SELECTED_AT), target_device_id="fan-01")
    confirmed = engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000))
    help_result = engine.consume(gesture(GestureType.HELP, SELECTED_AT + 1_100))
    assert len({pending.intent_id, confirmed.intent_id, help_result.intent_id}) == 3


def test_confirmed_result_serializes_to_spec_values(selected_engine):
    data = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000)).as_dict()
    assert data["schema_version"] == "1.0"
    assert data["action"] == "ON"
    assert data["status"] == "CONFIRMED"
    assert data["target_device_id"] == "fan-01"


# --- 기준값 ------------------------------------------------------------------


def test_default_help_cooldown_is_5_seconds():
    assert PARAMS.help_cooldown_ms == 5_000


def test_custom_parameters_are_used():
    engine = IntentEngine(parameters=IntentParameters(selection_timeout_ms=500, min_stable_frames=2, min_hold_ms=100))
    assert engine.state.timeout_ms == 500
    engine.consume(gesture(GestureType.POINTING, SELECTED_AT, stable_frames=2, hold_time_ms=100), target_device_id="fan-01")
    result = engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 501, stable_frames=2, hold_time_ms=100))
    assert result.cancel_reason == GESTURE_TIMEOUT
