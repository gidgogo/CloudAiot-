"""2차원 포인팅 계산 테스트."""

import pytest

from server.vision.pointing_detector import detect_pointing_vector, pointing_angle_deg
from shared.types import PointingVector
from tests.vision.hand_poses import pointing


def test_vector_runs_from_wrist_to_index_tip():
    hand = pointing()
    vector = detect_pointing_vector(hand)
    assert vector is not None
    assert (vector.start_x, vector.start_y) == pytest.approx(hand[0][:2])
    assert (vector.end_x, vector.end_y) == pytest.approx(hand[8][:2])


def test_short_or_incomplete_hand_has_no_vector():
    assert detect_pointing_vector([(0.5, 0.5, 0.0)] * 21) is None
    assert detect_pointing_vector(pointing()[:20]) is None


def test_points_outside_the_frame_are_clamped():
    hand = pointing()
    hand[0] = (1.03, 0.9, 0.0)
    hand[8] = (0.7, -0.02, 0.0)
    vector = detect_pointing_vector(hand)
    assert vector is not None
    assert (vector.start_x, vector.end_y) == (1.0, 0.0)


@pytest.mark.parametrize(
    "end, expected",
    [((0.8, 0.5), 0.0), ((0.5, 0.8), 90.0), ((0.5, 0.2), -90.0), ((0.2, 0.5), 180.0)],
)
def test_angle_convention(end, expected):
    assert pointing_angle_deg(PointingVector(0.5, 0.5, *end), 640, 480) == pytest.approx(expected)


def test_angle_uses_frame_aspect_ratio():
    diagonal = PointingVector(0.5, 0.5, 0.6, 0.6)
    assert pointing_angle_deg(diagonal, 480, 480) == pytest.approx(45.0)
    assert pointing_angle_deg(diagonal, 640, 480) == pytest.approx(36.87, abs=0.01)
