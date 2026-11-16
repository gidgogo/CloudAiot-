"""규칙 기반 제스처 판정 테스트.

입력 랜드마크는 똑바로 세운 화면 기준(y 아래로 증가)이다.
"""

import pytest

from server.vision.gesture_rules import GestureRuleParameters, classify_gesture
from shared.types import GestureType
from tests.vision.hand_poses import fist, hand, open_palm, pointing, rotate, thumb_up


@pytest.mark.parametrize("angle_deg", [0, 30, 90, 135, 180, 225, 270, 315])
def test_pointing_in_every_direction(angle_deg):
    assert classify_gesture(rotate(pointing(), angle_deg)) is GestureType.POINTING


def test_thumb_up_and_down():
    assert classify_gesture(thumb_up()) is GestureType.THUMB_UP
    assert classify_gesture(rotate(thumb_up(), 180)) is GestureType.THUMB_DOWN


def test_sideways_thumb_is_unknown():
    assert classify_gesture(rotate(thumb_up(), 90)) is GestureType.UNKNOWN


def test_thumb_tolerance_is_configurable():
    leaning = rotate(thumb_up(), 40)
    assert classify_gesture(leaning) is GestureType.THUMB_UP
    assert classify_gesture(leaning, GestureRuleParameters(vertical_tolerance_deg=30.0)) is GestureType.UNKNOWN


def test_upright_open_palm_is_help():
    assert classify_gesture(open_palm()) is GestureType.HELP


def test_open_palm_lying_sideways_is_not_help():
    assert classify_gesture(rotate(open_palm(), 90)) is GestureType.UNKNOWN


def test_fist_with_tucked_thumb_is_unknown():
    assert classify_gesture(fist()) is GestureType.UNKNOWN


def test_v_sign_is_unknown():
    assert classify_gesture(hand((True, True, False, False))) is GestureType.UNKNOWN


@pytest.mark.parametrize("count", [0, 20, 22])
def test_incomplete_landmarks_are_unknown(count):
    assert classify_gesture([(0.5, 0.5, 0.0)] * count) is GestureType.UNKNOWN
