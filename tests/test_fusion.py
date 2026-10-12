import pytest

from server.intent.fusion import IntentFusion
from shared.types import Action, GazeResult, GestureResult

MAPPING = {"open_palm": "on", "fist": "off", "v_sign": "call_caregiver"}


def test_both_inputs_give_intent():
    f = IntentFusion(MAPPING)
    intent = f.decide(GazeResult("light", 0.9), GestureResult("open_palm", 0.9))
    assert intent.target == "light"
    assert intent.action is Action.ON


def test_no_gaze_no_action():
    f = IntentFusion(MAPPING)
    assert f.decide(GazeResult(None, 0.0), GestureResult("open_palm", 0.9)) is None


def test_no_gesture_no_action():
    f = IntentFusion(MAPPING)
    assert f.decide(GazeResult("fan", 0.9), GestureResult(None, 0.0)) is None


def test_cooldown_blocks_repeat():
    f = IntentFusion(MAPPING, cooldown_sec=10)
    assert f.decide(GazeResult("fan", 0.9), GestureResult("fist", 0.9)) is not None
    assert f.decide(GazeResult("fan", 0.9), GestureResult("fist", 0.9)) is None


@pytest.mark.parametrize("gesture_name", list(MAPPING))
def test_all_commands_require_gaze(gesture_name):
    f = IntentFusion(MAPPING)
    assert f.decide(GazeResult(None, 0.0), GestureResult(gesture_name, 0.9)) is None


@pytest.mark.parametrize("confidence", [0.1, 0.69, float("nan"), 1.1])
@pytest.mark.parametrize("side", ["gaze", "gesture"])
def test_uncertain_inputs_are_cancelled(confidence, side):
    f = IntentFusion(MAPPING)
    gaze = GazeResult("light", confidence if side == "gaze" else 0.9)
    gesture = GestureResult("open_palm", confidence if side == "gesture" else 0.9)
    assert f.decide(gaze, gesture) is None


def test_configured_confidence_threshold():
    f = IntentFusion(MAPPING, min_confidence=0.95)
    assert f.decide(GazeResult("light", 0.9), GestureResult("open_palm", 0.9)) is None


@pytest.mark.parametrize("gaze_at, gesture_at", [(90, 90), (90, 100), (100, 90), (101, 101)])
def test_stale_or_future_inputs_are_cancelled(monkeypatch, gaze_at, gesture_at):
    monkeypatch.setattr("server.intent.fusion.time.time", lambda: 100.0)
    f = IntentFusion(MAPPING)
    assert f.decide(GazeResult("light", 0.9, gaze_at), GestureResult("open_palm", 0.9, gesture_at)) is None


def test_help_with_both_inputs():
    f = IntentFusion(MAPPING)
    intent = f.decide(GazeResult("light", 0.9), GestureResult("v_sign", 0.9))
    assert intent is not None
    assert intent.action is Action.CALL_CAREGIVER


def test_cooldown_expires_using_monotonic_clock(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("server.intent.fusion.time.monotonic", lambda: clock[0])
    f = IntentFusion(MAPPING, cooldown_sec=2.0)
    assert f.decide(GazeResult("fan", 0.9), GestureResult("fist", 0.9)) is not None
    clock[0] = 11.0
    assert f.decide(GazeResult("fan", 0.9), GestureResult("fist", 0.9)) is None
    clock[0] = 12.0
    assert f.decide(GazeResult("fan", 0.9), GestureResult("fist", 0.9)) is not None
