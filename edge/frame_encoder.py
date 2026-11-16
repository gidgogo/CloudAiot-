"""JPEG encoding for the Edge-AI frame contract."""
from __future__ import annotations

import cv2
import numpy as np

from shared.types import FrameMetadata, now_ms


class FrameEncoder:
    def __init__(self, width: int = 640, height: int = 480, jpeg_quality: int = 95) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        if not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")
        self.width, self.height, self.jpeg_quality = width, height, jpeg_quality

    def encode(
        self,
        frame: np.ndarray,
        *,
        edge_id: str,
        camera_id: str,
        mirrored: bool = False,
        rotation_deg: int = 0,
        captured_at_ms: int | None = None,
    ) -> tuple[FrameMetadata, bytes]:
        """프레임을 설정 해상도로 맞춰 JPEG로 인코딩한다.

        mirrored/rotation_deg는 영상을 변환하지 않고 메타데이터로만 전달한다(규격 4.4: AI가 반영).
        captured_at_ms는 인코딩 시각이 아니라 카메라에서 프레임을 읽은 시각이어야 한다.
        """
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        metadata = FrameMetadata(
            edge_id=edge_id,
            camera_id=camera_id,
            captured_at_ms=captured_at_ms if captured_at_ms is not None else now_ms(),
            width=self.width,
            height=self.height,
            jpeg_quality=self.jpeg_quality,
            mirrored=mirrored,
            rotation_deg=rotation_deg,
        )
        return metadata, encoded.tobytes()
