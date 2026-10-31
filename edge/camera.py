"""Camera capture. Frames remain in memory and are never written to disk."""
from __future__ import annotations
from typing import Iterator
import numpy as np

class Camera:
    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: int = 10, **_: object) -> None:
        self.device_index, self.width, self.height, self.fps = device_index, width, height, fps
        self._cap = None
    def open(self) -> None:
        import cv2
        self._cap = cv2.VideoCapture(self.device_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not self._cap.isOpened(): raise RuntimeError(f"cannot open camera {self.device_index}")
    def frames(self) -> Iterator[np.ndarray]:
        while self._cap is not None:
            ok, frame = self._cap.read()
            if not ok: break
            yield frame
    def close(self) -> None:
        if self._cap is not None: self._cap.release(); self._cap = None
