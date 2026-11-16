"""랜드마크 방향 보정과 손가락 형태 계산 테스트."""

import pytest

from server.vision.landmark_processor import (
    INDEX,
    MIDDLE,
    direction_deg,
    finger_extended,
    joint_angle_deg,
    orient_landmarks,
    oriented_frame_size,
    user_handedness,
)
from shared.types import Handedness
from tests.vision.hand_poses import pointing, rotate

TOP_LEFT = (0.1, 0.2, -0.05)


@pytest.mark.parametrize(
    "mirrored, rotation_deg, expected",
    [
        (False, 0, (0.1, 0.2)),
        (True, 0, (0.9, 0.2)),
        (False, 90, (0.8, 0.1)),
        (False, 180, (0.9, 0.8)),
        (False, 270, (0.2, 0.9)),
        (True, 90, (0.8, 0.9)),
    ],
)
def test_orient_landmarks_undoes_mirror_then_rotates_clockwise(mirrored, rotation_deg, expected):
    (x, y, z), = orient_landmarks([TOP_LEFT], mirrored=mirrored, rotation_deg=rotation_deg)
    assert (x, y) == pytest.approx(expected)
    assert z == TOP_LEFT[2]


def test_orient_landmarks_rejects_unsupported_rotation():
    with pytest.raises(ValueError):
        orient_landmarks([TOP_LEFT], mirrored=False, rotation_deg=45)


@pytest.mark.parametrize("rotation_deg, expected", [(0, (640, 480)), (90, (480, 640)), (180, (640, 480)), (270, (480, 640))])
def test_oriented_frame_size_swaps_sides_for_quarter_turns(rotation_deg, expected):
    assert oriented_frame_size(640, 480, rotation_deg) == expected


@pytest.mark.parametrize(
    "label, mirrored, expected",
    [
        ("Left", True, Handedness.LEFT),
        ("Right", True, Handedness.RIGHT),
        ("Left", False, Handedness.RIGHT),
        ("Right", False, Handedness.LEFT),
        ("", False, Handedness.UNKNOWN),
    ],
)
def test_user_handedness_corrects_mediapipe_mirror_assumption(label, mirrored, expected):
    assert user_handedness(label, mirrored=mirrored) is expected


def test_joint_angle_and_direction():
    assert joint_angle_deg((0, 0, 0), (1, 0, 0), (2, 0, 0)) == pytest.approx(180.0)
    assert joint_angle_deg((0, 0, 0), (1, 0, 0), (1, 1, 0)) == pytest.approx(90.0)
    assert direction_deg((0.5, 0.5, 0), (0.5, 0.2, 0)) == pytest.approx(-90.0)
    assert direction_deg((0.5, 0.5, 0), (0.8, 0.5, 0)) == pytest.approx(0.0)


@pytest.mark.parametrize("angle_deg", [0, 45, 90, 180, 270])
def test_finger_extension_does_not_depend_on_hand_rotation(angle_deg):
    hand = rotate(pointing(), angle_deg)
    assert finger_extended(hand, INDEX, 150.0)
    assert not finger_extended(hand, MIDDLE, 150.0)
