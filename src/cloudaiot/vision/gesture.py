"""손동작 인식.

최소 3가지 손동작(open_palm, fist, v_sign)을 인식한다.
"""

import numpy as np

from cloudaiot.types import GestureResult

SUPPORTED_GESTURES = ("open_palm", "fist", "v_sign")


class GestureRecognizer:
    def __init__(self, min_confidence: float = 0.7):
        self.min_confidence = min_confidence

    def recognize(self, frame: np.ndarray) -> GestureResult:
        # TODO: MediaPipe Hands 로 손 랜드마크 추출 후 손가락 펴짐 상태로 분류
        return GestureResult(name=None, confidence=0.0)
