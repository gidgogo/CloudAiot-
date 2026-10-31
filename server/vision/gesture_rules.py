"""Rule-based gestures: pointing, thumb-up, thumb-down and HELP."""
from __future__ import annotations
from shared.types import GestureType
def classify_gesture(landmarks: list[tuple[float, float, float]]) -> GestureType:
    if len(landmarks) != 21: return GestureType.UNKNOWN
    wrist, thumb_tip, thumb_ip, index_tip, index_pip = landmarks[0], landmarks[4], landmarks[3], landmarks[8], landmarks[6]
    index_extended = abs(index_tip[1]-wrist[1]) > abs(index_pip[1]-wrist[1])
    thumb_up = thumb_tip[1] < thumb_ip[1] and index_tip[1] > index_pip[1]
    thumb_down = thumb_tip[1] > thumb_ip[1] and index_tip[1] < index_pip[1]
    if thumb_up: return GestureType.THUMB_UP
    if thumb_down: return GestureType.THUMB_DOWN
    if index_extended: return GestureType.POINTING
    # v1 default HELP rule must be calibrated by the AI team before demo.
    if all(landmarks[i][1] < wrist[1] for i in (4,8,12,16,20)): return GestureType.HELP
    return GestureType.UNKNOWN
