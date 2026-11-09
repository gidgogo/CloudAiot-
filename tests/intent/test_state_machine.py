"""의도 판단 상태 전이 테스트.

server/intent/state_machine.py(SelectionStateMachine)의 현재 동작을 고정한다.
시각은 timestamp_ms 인자로 직접 넣어 실제 시간에 의존하지 않는다.
"""

import pytest

from server.intent.state_machine import IntentState, SelectionStateMachine

SELECTED_AT = 10_000


@pytest.fixture
def selected() -> SelectionStateMachine:
    machine = SelectionStateMachine()
    machine.select("fan-01", SELECTED_AT)
    return machine


def test_starts_idle_without_target():
    machine = SelectionStateMachine()
    assert machine.state is IntentState.IDLE
    assert machine.target_device_id is None
    assert machine.selected_at_ms == 0
    assert machine.timeout_ms == 3000


def test_select_stores_target_and_time(selected):
    assert selected.state is IntentState.TARGET_SELECTED
    assert selected.target_device_id == "fan-01"
    assert selected.selected_at_ms == SELECTED_AT


@pytest.mark.parametrize("elapsed_ms", [0, 1_000, 3_000])
def test_target_stays_active_within_timeout_including_boundary(selected, elapsed_ms):
    assert selected.active_target(SELECTED_AT + elapsed_ms) == "fan-01"
    assert selected.state is IntentState.TARGET_SELECTED


def test_target_is_cancelled_after_timeout(selected):
    assert selected.active_target(SELECTED_AT + 3_001) is None
    assert selected.state is IntentState.CANCELLED
    assert selected.target_device_id is None
    assert selected.selected_at_ms == 0


def test_cancelled_target_does_not_come_back(selected):
    selected.active_target(SELECTED_AT + 3_001)
    assert selected.active_target(SELECTED_AT + 3_002) is None


def test_cancel_resets_target_and_time(selected):
    selected.cancel()
    assert selected.state is IntentState.CANCELLED
    assert selected.target_device_id is None
    assert selected.selected_at_ms == 0


def test_select_again_replaces_target_and_restarts_timer(selected):
    selected.select("light-01", SELECTED_AT + 2_000)
    assert selected.target_device_id == "light-01"
    assert selected.active_target(SELECTED_AT + 4_500) == "light-01"


def test_select_after_cancel_works_again(selected):
    selected.cancel()
    selected.select("light-01", SELECTED_AT + 5_000)
    assert selected.state is IntentState.TARGET_SELECTED
    assert selected.active_target(SELECTED_AT + 5_100) == "light-01"


def test_custom_timeout_is_used():
    machine = SelectionStateMachine(timeout_ms=500)
    machine.select("fan-01", SELECTED_AT)
    assert machine.active_target(SELECTED_AT + 500) == "fan-01"
    assert machine.active_target(SELECTED_AT + 501) is None
