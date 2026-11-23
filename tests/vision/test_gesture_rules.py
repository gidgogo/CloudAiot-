"""규칙 기반 제스처 판정 테스트.

입력 랜드마크는 똑바로 세운 화면 기준(y 아래로 증가)이다.
"""

import pytest

from server.vision.gesture_rules import GestureRuleParameters, classify_gesture
from shared.types import GestureType
from tests.vision.hand_poses import (
    RAISED_THUMB,
    STRAIGHT_THUMB,
    TUCKED_THUMB,
    hand,
    open_palm,
    pointing,
    rotate,
    v_sign,
)


@pytest.mark.parametrize("angle_deg", [0, 30, 90, 135, 180, 225, 270, 315])
def test_pointing_in_every_direction(angle_deg):
    assert classify_gesture(rotate(pointing(), angle_deg)) is GestureType.POINTING


def test_upright_open_palm():
    assert classify_gesture(open_palm()) is GestureType.OPEN_PALM


def test_open_palm_lying_sideways_is_unknown():
    assert classify_gesture(rotate(open_palm(), 90)) is GestureType.UNKNOWN


def test_upright_tolerance_is_configurable():
    leaning = rotate(open_palm(), 40)
    assert classify_gesture(leaning) is GestureType.OPEN_PALM
    assert classify_gesture(leaning, GestureRuleParameters(vertical_tolerance_deg=30.0)) is GestureType.UNKNOWN


@pytest.mark.parametrize("angle_deg", [0, 90, 180])
@pytest.mark.parametrize("thumb", [TUCKED_THUMB, STRAIGHT_THUMB, RAISED_THUMB])
def test_fist_in_any_direction_ignores_thumb(angle_deg, thumb):
    assert classify_gesture(rotate(hand((False, False, False, False), thumb), angle_deg)) is GestureType.FIST


def test_upright_v_sign():
    assert classify_gesture(v_sign()) is GestureType.V_SIGN
    assert classify_gesture(hand((True, True, False, False), STRAIGHT_THUMB)) is GestureType.V_SIGN


def test_v_sign_lying_sideways_is_unknown():
    assert classify_gesture(rotate(v_sign(), 90)) is GestureType.UNKNOWN


def test_three_fingers_is_unknown():
    assert classify_gesture(hand((True, True, True, False))) is GestureType.UNKNOWN


@pytest.mark.parametrize("count", [0, 20, 22])
def test_incomplete_landmarks_are_unknown(count):
    assert classify_gesture([(0.5, 0.5, 0.0)] * count) is GestureType.UNKNOWN
