"""Build a 2D pointing vector from wrist to index fingertip."""
from __future__ import annotations
import math
from shared.types import PointingVector
def detect_pointing_vector(landmarks: list[tuple[float, float, float]]) -> PointingVector | None:
    if len(landmarks) != 21: return None
    wrist, index_tip = landmarks[0], landmarks[8]
    if math.dist(wrist[:2], index_tip[:2]) < .08: return None
    return PointingVector(wrist[0], wrist[1], index_tip[0], index_tip[1])
def pointing_angle_deg(vector: PointingVector, width: int, height: int) -> float:
    return math.degrees(math.atan2((vector.end_y-vector.start_y)*height, (vector.end_x-vector.start_x)*width))
