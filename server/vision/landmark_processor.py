"""Landmark geometry for MediaPipe Hands; coordinates stay normalized to 0.0..1.0 (spec 4.1)."""
from __future__ import annotations

import math
from collections.abc import Sequence

from shared.types import Handedness

Landmark = tuple[float, float, float]
Landmarks = Sequence[Landmark]

LANDMARK_COUNT = 21
WRIST = 0
THUMB_MCP, THUMB_IP, THUMB_TIP = 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

# (mcp, pip, tip) of the four fingers, thumb excluded.
INDEX = (INDEX_MCP, INDEX_PIP, INDEX_TIP)
MIDDLE = (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP)
RING = (RING_MCP, RING_PIP, RING_TIP)
PINKY = (PINKY_MCP, PINKY_PIP, PINKY_TIP)
FINGERS = (INDEX, MIDDLE, RING, PINKY)


def is_complete(landmarks: Landmarks) -> bool:
    return len(landmarks) == LANDMARK_COUNT


def orient_landmarks(landmarks: Landmarks, *, mirrored: bool, rotation_deg: int) -> list[Landmark]:
    """Map JPEG coordinates to the upright, unmirrored view (spec 4.4).

    The mirror is undone first, then the points turn clockwise by rotation_deg,
    the rotation that makes the received image upright.
    """
    oriented = []
    for x, y, z in landmarks:
        if mirrored:
            x = 1.0 - x
        x, y = _rotate_clockwise(x, y, rotation_deg)
        oriented.append((x, y, z))
    return oriented


def _rotate_clockwise(x: float, y: float, rotation_deg: int) -> tuple[float, float]:
    if rotation_deg == 0:
        return x, y
    if rotation_deg == 90:
        return 1.0 - y, x
    if rotation_deg == 180:
        return 1.0 - x, 1.0 - y
    if rotation_deg == 270:
        return y, 1.0 - x
    raise ValueError("rotation_deg must be 0, 90, 180 or 270")


def oriented_frame_size(width: int, height: int, rotation_deg: int) -> tuple[int, int]:
    """Frame size of the upright view; 90° and 270° swap width and height."""
    return (height, width) if rotation_deg in (90, 270) else (width, height)


def user_handedness(mediapipe_label: str, *, mirrored: bool) -> Handedness:
    """The user's real hand. MediaPipe labels hands as if the input image were mirrored."""
    label = mediapipe_label.upper()
    if label not in (Handedness.LEFT.value, Handedness.RIGHT.value):
        return Handedness.UNKNOWN
    if not mirrored:
        label = Handedness.RIGHT.value if label == Handedness.LEFT.value else Handedness.LEFT.value
    return Handedness(label)


def distance(a: Landmark, b: Landmark) -> float:
    return math.dist(a[:2], b[:2])


def joint_angle_deg(a: Landmark, joint: Landmark, b: Landmark) -> float:
    """Angle at joint between the segments to a and b; 180° is a straight line."""
    ax, ay = a[0] - joint[0], a[1] - joint[1]
    bx, by = b[0] - joint[0], b[1] - joint[1]
    norms = math.hypot(ax, ay) * math.hypot(bx, by)
    if norms == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / norms))
    return math.degrees(math.acos(cosine))


def direction_deg(start: Landmark, end: Landmark) -> float:
    """Screen direction from start to end: 0° right, +90° down, -90° up."""
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))


def finger_extended(landmarks: Landmarks, finger: tuple[int, int, int], straight_deg: float) -> bool:
    """A straight finger whose tip is farther from the wrist than its middle joint."""
    mcp, pip, tip = (landmarks[index] for index in finger)
    wrist = landmarks[WRIST]
    return joint_angle_deg(mcp, pip, tip) >= straight_deg and distance(wrist, tip) > distance(wrist, pip)
