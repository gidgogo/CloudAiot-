"""MediaPipe Hand Landmarker adapter. It returns normalized landmarks of the JPEG as sent."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from server.vision.landmark_processor import Landmark

DEFAULT_MODEL_PATH = Path(__file__).with_name("models") / "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"


@dataclass(frozen=True, slots=True)
class HandDetection:
    landmarks: list[Landmark]
    # As MediaPipe reports it; landmark_processor.user_handedness gives the user's real hand.
    mediapipe_label: str
    score: float


class HandDetector:
    """One detector per camera: VIDEO mode tracks the hand across that camera's frames."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        *,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        landmarker: Any = None,
    ) -> None:
        self._landmarker = landmarker or _create_landmarker(
            Path(model_path), min_detection_confidence, min_tracking_confidence
        )
        self._last_timestamp_ms = -1

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int) -> HandDetection | None:
        import cv2
        import mediapipe as mp

        # VIDEO mode rejects a timestamp that is not larger than the previous one.
        self._last_timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        result = self._landmarker.detect_for_video(image, self._last_timestamp_ms)
        if not result.hand_landmarks:
            return None
        category = result.handedness[0][0]
        points = [(lm.x, lm.y, lm.z) for lm in result.hand_landmarks[0]]
        return HandDetection(points, category.category_name, category.score)

    def close(self) -> None:
        self._landmarker.close()


def _create_landmarker(model_path: Path, min_detection_confidence: float, min_tracking_confidence: float) -> Any:
    if not model_path.is_file():
        raise FileNotFoundError(f"hand landmarker model not found at {model_path}; download it from {MODEL_URL}")
    from mediapipe.tasks.python.core.base_options import BaseOptions
    from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode

    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )
    return HandLandmarker.create_from_options(options)
