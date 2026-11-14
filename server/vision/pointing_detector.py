"""Build a 2D pointing vector from wrist to index fingertip (spec 4.3, 6.1)."""
from __future__ import annotations

import math

from server.vision.landmark_processor import INDEX_TIP, WRIST, Landmarks, is_complete
from shared.types import PointingVector

MIN_POINTING_LENGTH = 0.08


def detect_pointing_vector(landmarks: Landmarks) -> PointingVector | None:
    """None when the hand is incomplete or too small to give a reliable direction."""
    if not is_complete(landmarks):
        return None
    wrist, index_tip = landmarks[WRIST], landmarks[INDEX_TIP]
    if math.dist(wrist[:2], index_tip[:2]) < MIN_POINTING_LENGTH:
        return None
    # MediaPipe places landmarks of a hand at the frame edge slightly outside 0..1.
    return PointingVector(*(_clamp(value) for value in (wrist[0], wrist[1], index_tip[0], index_tip[1])))


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def pointing_angle_deg(vector: PointingVector, width: int, height: int) -> float:
    """0° right, +90° down, -90° up, ±180° left, using the real frame aspect ratio (spec 4.3)."""
    return math.degrees(math.atan2((vector.end_y - vector.start_y) * height, (vector.end_x - vector.start_x) * width))
