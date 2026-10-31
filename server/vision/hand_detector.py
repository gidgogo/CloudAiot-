"""MediaPipe Hands adapter. It returns normalized landmarks only."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np
from shared.types import Handedness

@dataclass(slots=True)
class HandDetection:
    landmarks: list[tuple[float, float, float]]
    handedness: Handedness
    score: float

class HandDetector:
    def __init__(self, min_detection_confidence: float = .5, min_tracking_confidence: float = .5) -> None:
        import mediapipe as mp
        self._hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=min_detection_confidence, min_tracking_confidence=min_tracking_confidence)
    def detect(self, frame_bgr: np.ndarray) -> HandDetection | None:
        import cv2
        result = self._hands.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        if not result.multi_hand_landmarks: return None
        points = [(lm.x, lm.y, lm.z) for lm in result.multi_hand_landmarks[0].landmark]
        label = result.multi_handedness[0].classification[0].label.upper()
        return HandDetection(points, Handedness(label) if label in ("LEFT", "RIGHT") else Handedness.UNKNOWN, result.multi_handedness[0].classification[0].score)
    def close(self) -> None: self._hands.close()
