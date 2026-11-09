"""최종 의도 판단 테스트.

server/intent/engine.py(IntentEngine.consume)의 현재 동작을 고정한다.
아직 고치지 않은 동작은 xfail(strict=True)로 미리 적어 둔다. 고치면 이 테스트가 통과로 바뀌므로 xfail 표시를 지운다.
"""

import pytest

from server.intent.engine import IntentEngine
from server.intent.parameters import IntentParameters
from shared.types import GestureResult, GestureType, IntentAction, IntentStatus, PointingVector

PARAMS = IntentParameters()
SELECTED_AT = 10_000


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
    engine.consume(gesture(GestureType.POINTING, SELECTED_AT), target_device_id="fan-01")
    return engine


# --- 현재 동작 고정 -------------------------------------------------------


def test_help_is_confirmed_without_target(engine):
    result = engine.consume(gesture(GestureType.HELP, SELECTED_AT))
    assert result.action is IntentAction.HELP
    assert result.status is IntentStatus.CONFIRMED
    assert result.target_device_id is None
    assert result.confirmed_at_ms is not None
    assert result.cancel_reason is None


def test_pointing_with_target_selects_device(engine):
    result = engine.consume(gesture(GestureType.POINTING, SELECTED_AT), target_device_id="fan-01")
    assert result.status is IntentStatus.PENDING
    assert result.target_device_id == "fan-01"
    assert result.confirmed_at_ms is None
    assert engine.state.target_device_id == "fan-01"


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


def test_thumb_without_selection_is_cancelled(engine):
    result = engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT))
    assert result.status is IntentStatus.CANCELLED
    assert result.cancel_reason == "TARGET_NOT_FOUND"
    assert result.target_device_id is None


def test_thumb_after_selection_timeout_is_cancelled(selected_engine):
    result = selected_engine.consume(
        gesture(GestureType.THUMB_UP, SELECTED_AT + PARAMS.selection_timeout_ms + 1)
    )
    assert result.status is IntentStatus.CANCELLED
    assert result.target_device_id is None


@pytest.mark.parametrize(
    "kind",
    [GestureType.HELP, GestureType.POINTING, GestureType.THUMB_UP, GestureType.UNKNOWN],
)
def test_correlation_id_is_passed_through(engine, kind):
    engine.consume(gesture(GestureType.POINTING, SELECTED_AT), target_device_id="fan-01")
    result = engine.consume(
        gesture(kind, SELECTED_AT + 500, correlation_id="corr-xyz"), target_device_id="fan-01"
    )
    assert result.correlation_id == "corr-xyz"


def test_each_result_gets_its_own_intent_id(engine):
    first = engine.consume(gesture(GestureType.HELP, SELECTED_AT))
    second = engine.consume(gesture(GestureType.HELP, SELECTED_AT + 100))
    assert first.intent_id != second.intent_id


def test_confirmed_result_serializes_to_spec_values(selected_engine):
    data = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000)).as_dict()
    assert data["schema_version"] == "1.0"
    assert data["action"] == "ON"
    assert data["status"] == "CONFIRMED"
    assert data["target_device_id"] == "fan-01"


# --- 아직 고치지 않은 동작 (xfail) ----------------------------------------


@pytest.mark.xfail(strict=True, reason="확정 후 상태를 초기화하지 않아 엄지를 유지하면 매 프레임 확정된다")
def test_holding_thumb_up_confirms_only_once(selected_engine):
    first = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_000))
    second = selected_engine.consume(gesture(GestureType.THUMB_UP, SELECTED_AT + 1_100))
    assert first.status is IntentStatus.CONFIRMED
    assert second.status is not IntentStatus.CONFIRMED


@pytest.mark.xfail(strict=True, reason="HELP 중복 방지가 없어 HELP를 유지하면 매 프레임 확정된다")
def test_holding_help_confirms_only_once(engine):
    first = engine.consume(gesture(GestureType.HELP, SELECTED_AT))
    second = engine.consume(gesture(GestureType.HELP, SELECTED_AT + 100))
    assert first.status is IntentStatus.CONFIRMED
    assert second.status is not IntentStatus.CONFIRMED


@pytest.mark.xfail(strict=True, reason="엔진이 stable_frames, hold_time_ms 기준을 검사하지 않는다")
@pytest.mark.parametrize(
    "stable_frames, hold_time_ms",
    [(PARAMS.min_stable_frames - 1, PARAMS.min_hold_ms), (PARAMS.min_stable_frames, PARAMS.min_hold_ms - 1)],
)
def test_unstable_gesture_is_not_confirmed(selected_engine, stable_frames, hold_time_ms):
    result = selected_engine.consume(
        gesture(
            GestureType.THUMB_UP,
            SELECTED_AT + 1_000,
            stable_frames=stable_frames,
            hold_time_ms=hold_time_ms,
        )
    )
    assert result.status is not IntentStatus.CONFIRMED
