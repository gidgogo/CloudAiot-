"""카메라 입력.

프레임은 메모리에서만 처리하고 파일로 저장하지 않는다 (NFR-03).
"""

from typing import Iterator

import numpy as np


class Camera:
    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: int = 15):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self._cap = None

    def open(self) -> None:
        import cv2

        self._cap = cv2.VideoCapture(self.device_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not self._cap.isOpened():
            raise RuntimeError(f"카메라 {self.device_index} 를 열 수 없습니다")

    def frames(self) -> Iterator[np.ndarray]:
        while self._cap is not None:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
