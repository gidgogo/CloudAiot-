"""의도 판단 상태 전이 테스트.

server/intent/state_machine.py(SelectionStateMachine)의 동작을 고정한다.
상태는 IDLE과 TARGET_SELECTED 두 가지이고, 확정(confirm)이나 취소(cancel) 후에는 IDLE로 돌아간다.
시각은 timestamp_ms 인자로 직접 넣어 실제 시간에 의존하지 않는다.
"""

import pytest

from server.intent.cancel_reasons import DIRECTION_CHANGED, GESTURE_TIMEOUT
from server.intent.parameters import IntentParameters
from server.intent.state_machine import IntentState, SelectionStateMachine

SELECTED_AT = 10_000
TIMEOUT_MS = IntentParameters().selection_timeout_ms


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


def test_cancel_returns_to_idle_and_keeps_reason(selected):
    selected.cancel(DIRECTION_CHANGED)
    assert_idle(selected)
    assert selected.last_cancel_reason == DIRECTION_CHANGED


def test_select_clears_previous_cancel_reason(selected):
    selected.cancel(DIRECTION_CHANGED)
    selected.select("light-01", SELECTED_AT + 5_000)
    assert selected.last_cancel_reason is None


def test_confirm_clears_previous_cancel_reason(selected):
    selected.active_target(SELECTED_AT + TIMEOUT_MS + 1)
    selected.select("light-01", SELECTED_AT + 5_000)
    selected.confirm()
    assert selected.last_cancel_reason is None


def test_select_again_replaces_target_and_restarts_timer(selected):
    selected.select("light-01", SELECTED_AT + 2_000)
    assert selected.target_device_id == "light-01"
    assert selected.active_target(SELECTED_AT + 4_500) == "light-01"


def test_select_after_cancel_works_again(selected):
    selected.cancel(DIRECTION_CHANGED)
    selected.select("light-01", SELECTED_AT + 5_000)
    assert selected.state is IntentState.TARGET_SELECTED
    assert selected.active_target(SELECTED_AT + 5_100) == "light-01"


def test_custom_timeout_is_used():
    machine = SelectionStateMachine(timeout_ms=500)
    machine.select("fan-01", SELECTED_AT)
    assert machine.active_target(SELECTED_AT + 500) == "fan-01"
    assert machine.active_target(SELECTED_AT + 501) is None
    assert machine.last_cancel_reason == GESTURE_TIMEOUT
