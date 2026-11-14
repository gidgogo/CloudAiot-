"""Rule-based gestures (spec 6.1): POINTING, THUMB_UP, THUMB_DOWN and HELP.

Landmarks must already be oriented upright (landmark_processor.orient_landmarks).
Finger checks use joint angles, so pointing is recognized in every direction.
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
    THUMB_MCP,
    THUMB_TIP,
    WRIST,
    Landmarks,
    direction_deg,
    finger_extended,
    is_complete,
    thumb_straight,
)
from shared.types import GestureType

UP_DEG = -90.0
DOWN_DEG = 90.0


@dataclass(frozen=True)
class GestureRuleParameters:
    """Working thresholds until the team calibrates them on the demo camera."""

    straight_finger_deg: float = 150.0  # PIP joint angle at or above this counts as an extended finger
    straight_thumb_deg: float = 150.0  # thumb IP joint angle at or above this counts as a straight thumb
    vertical_tolerance_deg: float = 45.0  # how far a thumb or palm may lean from vertical


def classify_gesture(landmarks: Landmarks, parameters: GestureRuleParameters | None = None) -> GestureType:
    if not is_complete(landmarks):
        return GestureType.UNKNOWN
    rules = parameters or GestureRuleParameters()
    extended = {finger: finger_extended(landmarks, finger, rules.straight_finger_deg) for finger in FINGERS}
    if not any(extended.values()):
        return _thumb_gesture(landmarks, rules)
    if extended[INDEX] and not (extended[MIDDLE] or extended[RING] or extended[PINKY]):
        return GestureType.POINTING
    # v1 HELP is an open palm held upright; the thumb is ignored.
    if all(extended.values()) and _is_near(direction_deg(landmarks[WRIST], landmarks[MIDDLE_MCP]), UP_DEG, rules):
        return GestureType.HELP
    return GestureType.UNKNOWN


def _thumb_gesture(landmarks: Landmarks, rules: GestureRuleParameters) -> GestureType:
    if not thumb_straight(landmarks, rules.straight_thumb_deg):
        return GestureType.UNKNOWN
    thumb_deg = direction_deg(landmarks[THUMB_MCP], landmarks[THUMB_TIP])
    if _is_near(thumb_deg, UP_DEG, rules):
        return GestureType.THUMB_UP
    if _is_near(thumb_deg, DOWN_DEG, rules):
        return GestureType.THUMB_DOWN
    return GestureType.UNKNOWN


def _is_near(angle_deg: float, target_deg: float, rules: GestureRuleParameters) -> bool:
    return abs(angle_deg - target_deg) <= rules.vertical_tolerance_deg
