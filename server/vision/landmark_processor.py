"""Landmark helpers; all output coordinates stay normalized to 0.0..1.0."""
from __future__ import annotations
from typing import Sequence
Landmarks = Sequence[tuple[float, float, float]]
def point(landmarks: Landmarks, index: int) -> tuple[float, float, float]:
    if len(landmarks) != 21: raise ValueError("MediaPipe Hands must provide 21 landmarks")
    return landmarks[index]
def finger_extended(landmarks: Landmarks, tip: int, pip: int, wrist: int = 0) -> bool:
    return abs(landmarks[tip][1] - landmarks[wrist][1]) > abs(landmarks[pip][1] - landmarks[wrist][1])
