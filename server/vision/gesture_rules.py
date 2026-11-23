"""Rule-based gestures (spec 6.1): POINTING, OPEN_PALM, FIST and V_SIGN.

Landmarks must already be oriented upright (landmark_processor.orient_landmarks).
Finger checks use joint angles, so pointing is recognized in every direction.
The thumb is ignored by every rule.
"""
from __future__ import annotations

from dataclasses import dataclass

from server.vision.landmark_processor import (
    FINGERS,
    INDEX,
    MIDDLE,
    MIDDLE_MCP,
    PINKY,
    RING,
    WRIST,
    Landmarks,
    direction_deg,
    finger_extended,
    is_complete,
)
from shared.types import GestureType

UP_DEG = -90.0


@dataclass(frozen=True)
class GestureRuleParameters:
    """Working thresholds until the team calibrates them on the demo camera."""

    straight_finger_deg: float = 150.0  # PIP joint angle at or above this counts as an extended finger
    vertical_tolerance_deg: float = 45.0  # how far an open palm or V sign may lean from upright


def classify_gesture(landmarks: Landmarks, parameters: GestureRuleParameters | None = None) -> GestureType:
    if not is_complete(landmarks):
        return GestureType.UNKNOWN
    rules = parameters or GestureRuleParameters()
    extended = {finger: finger_extended(landmarks, finger, rules.straight_finger_deg) for finger in FINGERS}
    if not any(extended.values()):
        return GestureType.FIST
    if extended[INDEX] and not (extended[MIDDLE] or extended[RING] or extended[PINKY]):
        return GestureType.POINTING
    # OPEN_PALM and V_SIGN must be held upright so a sideways hand does not switch a device or call for help.
    if not _is_upright(landmarks, rules):
        return GestureType.UNKNOWN
    if all(extended.values()):
        return GestureType.OPEN_PALM
    if extended[INDEX] and extended[MIDDLE] and not (extended[RING] or extended[PINKY]):
        return GestureType.V_SIGN
    return GestureType.UNKNOWN


def _is_upright(landmarks: Landmarks, rules: GestureRuleParameters) -> bool:
    palm_deg = direction_deg(landmarks[WRIST], landmarks[MIDDLE_MCP])
    return abs(palm_deg - UP_DEG) <= rules.vertical_tolerance_deg
