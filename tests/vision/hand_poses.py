"""Synthetic upright MediaPipe hand landmarks (21 points, y grows downward) for vision tests."""
from __future__ import annotations

import math

Point = tuple[float, float, float]

WRIST = (0.50, 0.80, 0.0)
FINGER_MCPS = ((0.45, 0.62), (0.50, 0.61), (0.55, 0.62), (0.59, 0.64))


def _finger(mcp: tuple[float, float], extended: bool) -> list[Point]:
    x, y = mcp
    if extended:
        offsets = ((0, 0), (0, -0.06), (0, -0.10), (0, -0.13))
    else:  # curled back toward the palm
        offsets = ((0, 0), (0, -0.04), (0.01, -0.01), (0.01, 0.02))
    return [(x + dx, y + dy, 0.0) for dx, dy in offsets]


STRAIGHT_THUMB = [(0.44, 0.76, 0.0), (0.40, 0.72, 0.0), (0.37, 0.68, 0.0), (0.35, 0.64, 0.0)]
TUCKED_THUMB = [(0.44, 0.76, 0.0), (0.42, 0.72, 0.0), (0.45, 0.68, 0.0), (0.48, 0.70, 0.0)]
RAISED_THUMB = [(0.43, 0.68, 0.0), (0.42, 0.62, 0.0), (0.42, 0.55, 0.0), (0.42, 0.48, 0.0)]


def hand(fingers: tuple[bool, bool, bool, bool], thumb: list[Point] = TUCKED_THUMB) -> list[Point]:
    """fingers are the extended states of index, middle, ring and pinky."""
    points = [WRIST, *thumb]
    for mcp, extended in zip(FINGER_MCPS, fingers):
        points.extend(_finger(mcp, extended))
    return points


def pointing() -> list[Point]:
    return hand((True, False, False, False))


def open_palm() -> list[Point]:
    return hand((True, True, True, True), STRAIGHT_THUMB)


def v_sign() -> list[Point]:
    return hand((True, True, False, False))


def rotate(points: list[Point], angle_deg: float, center: tuple[float, float] = (0.5, 0.6)) -> list[Point]:
    """Rotate the hand clockwise on screen (y down) around center."""
    rad = math.radians(angle_deg)
    cx, cy = center
    rotated = []
    for x, y, z in points:
        dx, dy = x - cx, y - cy
        rotated.append((cx + dx * math.cos(rad) - dy * math.sin(rad), cy + dx * math.sin(rad) + dy * math.cos(rad), z))
    return rotated
