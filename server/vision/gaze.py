"""시선(주시 대상) 인식.

얼굴 방향/시선 벡터를 추정해 설정된 기기 영역 중 어디를 보고 있는지 판단한다.
"""

from typing import Dict

import numpy as np

from shared.types import GazeResult


class GazeEstimator:
    def __init__(self, targets: Dict[str, dict], dwell_sec: float = 0.8):
        self.targets = targets
        self.dwell_sec = dwell_sec

    def estimate(self, frame: np.ndarray) -> GazeResult:
        # TODO: MediaPipe Face Mesh 로 시선 좌표(0~1) 추정
        # TODO: targets 영역과 비교하고 dwell_sec 이상 유지되면 target 확정
        return GazeResult(target=None, confidence=0.0)
