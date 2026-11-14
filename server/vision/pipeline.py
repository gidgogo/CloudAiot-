"""Turn one received frame (spec 5.4) into a gesture result for the intent engine (spec 6.1)."""
from __future__ import annotations

import numpy as np

from server.vision.gesture_rules import GestureRuleParameters, classify_gesture
from server.vision.hand_detector import HandDetector
from server.vision.landmark_processor import orient_landmarks, user_handedness
from server.vision.pointing_detector import detect_pointing_vector
from server.vision.stability_checker import NOT_STABLE, Stability, StabilityChecker
from shared.types import FrameMetadata, GestureResult, GestureType, Handedness, PointingVector


class GesturePipeline:
    """One pipeline per camera, because the detector and the stability count follow one video stream."""

    def __init__(
        self,
        detector: HandDetector | None = None,
        *,
        rules: GestureRuleParameters | None = None,
        stability: StabilityChecker | None = None,
    ) -> None:
        self._detector = detector or HandDetector()
        self._rules = rules or GestureRuleParameters()
        self._stability = stability or StabilityChecker()

    def process_jpeg(self, jpeg: bytes, metadata: FrameMetadata) -> GestureResult:
        """Decode in memory only (spec 5.6). ValueError means the frame is INVALID (spec 5.5)."""
        import cv2

        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("frame is not a JPEG image")
        if frame.shape[:2] != (metadata.height, metadata.width):
            raise ValueError("JPEG size does not match the frame metadata")
        return self.process(frame, metadata)

    def process(self, frame_bgr: np.ndarray, metadata: FrameMetadata) -> GestureResult:
        detection = self._detector.detect(frame_bgr, metadata.captured_at_ms)
        if detection is None:
            self._stability.reset()
            return _result(metadata, GestureType.UNKNOWN, Handedness.UNKNOWN, None, NOT_STABLE)
        landmarks = orient_landmarks(detection.landmarks, mirrored=metadata.mirrored, rotation_deg=metadata.rotation_deg)
        gesture = classify_gesture(landmarks, self._rules)
        vector = detect_pointing_vector(landmarks) if gesture is GestureType.POINTING else None
        if gesture is GestureType.POINTING and vector is None:
            # The intent engine rejects POINTING without a vector.
            gesture = GestureType.UNKNOWN
        handedness = user_handedness(detection.mediapipe_label, mirrored=metadata.mirrored)
        stability = self._stability.update(gesture, metadata.captured_at_ms)
        return _result(metadata, gesture, handedness, vector, stability)

    def close(self) -> None:
        self._detector.close()


def _result(
    metadata: FrameMetadata,
    gesture: GestureType,
    handedness: Handedness,
    vector: PointingVector | None,
    stability: Stability,
) -> GestureResult:
    return GestureResult(
        frame_id=metadata.frame_id,
        correlation_id=metadata.correlation_id,
        handedness=handedness,
        gesture=gesture,
        pointing_vector=vector,
        stable_frames=stability.frames,
        hold_time_ms=stability.hold_ms,
    )
