"""의도 판단 상태 전이 테스트.

server/intent/state_machine.py(SelectionStateMachine)의 동작을 고정한다.
상태는 IDLE과 TARGET_SELECTED 두 가지이고, 확정(confirm)이나 취소(cancel) 후에는 IDLE로 돌아간다.
시각은 timestamp_ms 인자로 직접 넣어 실제 시간에 의존하지 않는다.
"""

import pytest

from server.intent.cancel_reasons import DIRECTION_CHANGED, GESTURE_TIMEOUT
from server.intent.parameters import IntentParameters
from server.intent.state_machine import IntentState, SelectionStateMachine, angle_difference_deg

SELECTED_AT = 10_000
TIMEOUT_MS = IntentParameters().selection_timeout_ms
MAX_DELTA = IntentParameters().max_angle_delta_deg


@pytest.fixture
def selected() -> SelectionStateMachine:
    machine = SelectionStateMachine()
    machine.select("fan-01", SELECTED_AT)
    return machine


def assert_idle(machine: SelectionStateMachine) -> None:
    assert machine.state is IntentState.IDLE
    assert machine.target_device_id is None
    assert machine.selected_at_ms == 0


def test_only_idle_and_target_selected_states_exist():
    assert {state.value for state in IntentState} == {"IDLE", "TARGET_SELECTED"}


def test_starts_idle_without_target():
    machine = SelectionStateMachine()
    assert_idle(machine)
    assert machine.last_cancel_reason is None


def test_default_timeout_comes_from_intent_parameters():
    assert SelectionStateMachine().timeout_ms == TIMEOUT_MS == 3000


def test_select_stores_target_and_time(selected):
    assert selected.state is IntentState.TARGET_SELECTED
    assert selected.target_device_id == "fan-01"
    assert selected.selected_at_ms == SELECTED_AT


@pytest.mark.parametrize("elapsed_ms", [0, 1_000, TIMEOUT_MS])
def test_target_stays_active_within_timeout_including_boundary(selected, elapsed_ms):
    assert selected.active_target(SELECTED_AT + elapsed_ms) == "fan-01"
    assert selected.state is IntentState.TARGET_SELECTED


def test_timeout_cancels_with_gesture_timeout_and_returns_to_idle(selected):
    assert selected.active_target(SELECTED_AT + TIMEOUT_MS + 1) is None
    assert_idle(selected)
    assert selected.last_cancel_reason == GESTURE_TIMEOUT


def test_cancelled_target_does_not_come_back(selected):
    selected.active_target(SELECTED_AT + TIMEOUT_MS + 1)
    assert selected.active_target(SELECTED_AT + TIMEOUT_MS + 2) is None


def test_active_target_in_idle_keeps_idle_without_reason():
    machine = SelectionStateMachine()
    assert machine.active_target(SELECTED_AT) is None
    assert_idle(machine)
    assert machine.last_cancel_reason is None


def test_frame_from_before_selection_is_ignored_and_selection_kept(selected):
    assert selected.active_target(SELECTED_AT - 1) is None
    assert selected.state is IntentState.TARGET_SELECTED
    assert selected.target_device_id == "fan-01"
    assert selected.active_target(SELECTED_AT + 100) == "fan-01"


def test_confirm_returns_to_idle_so_selection_cannot_confirm_twice(selected):
    selected.confirm()
    assert_idle(selected)
    assert selected.last_cancel_reason is None
    assert selected.active_target(SELECTED_AT + 100) is None


def test_clear_returns_to_idle_without_reason(selected):
    selected.cancel(DIRECTION_CHANGED)
    selected.select("light-01", SELECTED_AT + 5_000, angle_deg=90.0)
    selected.clear()
    assert_idle(selected)
    assert selected.selected_angle_deg is None
    assert selected.last_cancel_reason is None


def test_cancel_returns_to_idle_and_keeps_reason(selected):
    selected.cancel(DIRECTION_CHANGED)
    assert_idle(selected)
    assert selected.last_cancel_reason == DIRECTION_CHANGED


def test_confirm_clears_previous_cancel_reason(selected):
    selected.active_target(SELECTED_AT + TIMEOUT_MS + 1)
    selected.select("light-01", SELECTED_AT + 5_000)
    selected.confirm()
    assert selected.last_cancel_reason is None


def test_select_again_replaces_target_and_restarts_timer(selected):
    selected.select("light-01", SELECTED_AT + 2_000)
    assert selected.target_device_id == "light-01"
    assert selected.active_target(SELECTED_AT + 4_500) == "light-01"


def test_select_after_cancel_works_again_and_clears_reason(selected):
    selected.cancel(DIRECTION_CHANGED)
    selected.select("light-01", SELECTED_AT + 5_000)
    assert selected.state is IntentState.TARGET_SELECTED
    assert selected.last_cancel_reason is None
    assert selected.active_target(SELECTED_AT + 5_100) == "light-01"


def test_custom_timeout_is_used():
    machine = SelectionStateMachine(timeout_ms=500)
    machine.select("fan-01", SELECTED_AT)
    assert machine.active_target(SELECTED_AT + 500) == "fan-01"
    assert machine.active_target(SELECTED_AT + 501) is None
    assert machine.last_cancel_reason == GESTURE_TIMEOUT


# --- 선택 시간 연장 (keep_alive) ----------------------------------------------


def test_keep_alive_restarts_timer_and_keeps_target():
    machine = SelectionStateMachine()
    machine.select("fan-01", SELECTED_AT, angle_deg=5.0)
    machine.keep_alive(SELECTED_AT + 2_000)
    assert machine.target_device_id == "fan-01"
    assert machine.selected_angle_deg == 5.0
    assert machine.active_target(SELECTED_AT + 4_500) == "fan-01"


def test_keep_alive_does_not_move_timer_backwards(selected):
    selected.keep_alive(SELECTED_AT - 500)
    assert selected.selected_at_ms == SELECTED_AT


def test_keep_alive_does_nothing_when_idle():
    machine = SelectionStateMachine()
    machine.keep_alive(SELECTED_AT)
    assert_idle(machine)


# --- 방향 변경 감지 (DIRECTION_CHANGED) ----------------------------------------


@pytest.mark.parametrize(
    "a, b, expected",
    [(0.0, 0.0, 0.0), (10.0, -10.0, 20.0), (170.0, -170.0, 20.0), (-170.0, 170.0, 20.0),
     (180.0, -180.0, 0.0), (90.0, -90.0, 180.0), (350.0, 10.0, 20.0)],
)
def test_angle_difference_uses_shortest_way_around(a, b, expected):
    assert angle_difference_deg(a, b) == pytest.approx(expected)


@pytest.fixture
def pointed() -> SelectionStateMachine:
    machine = SelectionStateMachine()
    machine.select("fan-01", SELECTED_AT, angle_deg=0.0)
    return machine


def test_default_max_angle_delta_comes_from_intent_parameters():
    assert SelectionStateMachine().max_angle_delta_deg == MAX_DELTA == 15.0


def test_select_stores_reference_angle(pointed):
    assert pointed.selected_angle_deg == 0.0


@pytest.mark.parametrize("angle", [0.0, 10.0, -10.0, MAX_DELTA, -MAX_DELTA])
def test_small_direction_change_keeps_selection(pointed, angle):
    assert pointed.cancel_if_direction_changed(angle) is False
    assert pointed.state is IntentState.TARGET_SELECTED
    assert pointed.target_device_id == "fan-01"


@pytest.mark.parametrize("angle", [MAX_DELTA + 0.1, -(MAX_DELTA + 0.1), 90.0, 180.0])
def test_large_direction_change_cancels_with_direction_changed(pointed, angle):
    assert pointed.cancel_if_direction_changed(angle) is True
    assert_idle(pointed)
    assert pointed.selected_angle_deg is None
    assert pointed.last_cancel_reason == DIRECTION_CHANGED


@pytest.mark.parametrize("new_angle, changed", [(-170.0, True), (-175.0, False), (175.0, False)])
def test_direction_change_across_180_degrees(new_angle, changed):
    machine = SelectionStateMachine()
    machine.select("door-01", SELECTED_AT, angle_deg=170.0 if changed else 175.0)
    assert machine.cancel_if_direction_changed(new_angle) is changed


def test_direction_check_does_nothing_when_idle():
    machine = SelectionStateMachine()
    assert machine.cancel_if_direction_changed(90.0) is False
    assert_idle(machine)
    assert machine.last_cancel_reason is None


def test_direction_check_needs_a_reference_angle(selected):
    assert selected.selected_angle_deg is None
    assert selected.cancel_if_direction_changed(90.0) is False
    assert selected.state is IntentState.TARGET_SELECTED


def test_keep_alive_does_not_move_reference_angle(pointed):
    pointed.keep_alive(SELECTED_AT + 1_000)
    assert pointed.cancel_if_direction_changed(MAX_DELTA + 1) is True


def test_custom_max_angle_delta_is_used():
    machine = SelectionStateMachine(max_angle_delta_deg=5.0)
    machine.select("fan-01", SELECTED_AT, angle_deg=0.0)
    assert machine.cancel_if_direction_changed(5.0) is False
    assert machine.cancel_if_direction_changed(5.1) is True


@pytest.mark.parametrize("finish", ["confirm", "cancel"])
def test_confirm_and_cancel_clear_reference_angle(pointed, finish):
    if finish == "confirm":
        pointed.confirm()
    else:
        pointed.cancel(GESTURE_TIMEOUT)
    assert pointed.selected_angle_deg is None
