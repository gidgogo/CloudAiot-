from cloudaiot.intent.fusion import IntentFusion
from cloudaiot.types import Action, GazeResult, GestureResult

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
