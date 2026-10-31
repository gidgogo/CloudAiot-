"""JPEG encoding for the Edge-AI frame contract."""
from __future__ import annotations
import cv2
import numpy as np
from shared.types import FrameMetadata

class FrameEncoder:
    def __init__(self, width: int = 640, height: int = 480, jpeg_quality: int = 95) -> None:
        self.width, self.height, self.jpeg_quality = width, height, jpeg_quality
    def encode(self, frame: np.ndarray, *, edge_id: str, camera_id: str, mirrored: bool = False, rotation_deg: int = 0) -> tuple[FrameMetadata, bytes]:
        resized = cv2.resize(frame, (self.width, self.height))
        ok, encoded = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok: raise RuntimeError("JPEG encoding failed")
        metadata = FrameMetadata(edge_id=edge_id, camera_id=camera_id, width=self.width, height=self.height, jpeg_quality=self.jpeg_quality, mirrored=mirrored, rotation_deg=rotation_deg)
        return metadata, encoded.tobytes()
