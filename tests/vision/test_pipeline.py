"""프레임에서 손동작 인식 결과(규격 6.1)까지의 연결 테스트. 손 검출기는 가짜를 사용한다."""

import cv2
import numpy as np
import pytest

from server.vision.hand_detector import HandDetection
from server.vision.pipeline import GesturePipeline
from shared.constants import SCHEMA_VERSION
from shared.types import FrameMetadata, GestureType, Handedness
from tests.vision.hand_poses import open_palm, pointing

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)
T0 = 1_793_430_000_000


class FakeDetector:
    def __init__(self, landmarks=None, label="Right"):
        self.landmarks, self.label = landmarks, label
        self.closed = False

    def detect(self, frame_bgr, timestamp_ms):
        return None if self.landmarks is None else HandDetection(self.landmarks, self.label, 0.9)

    def close(self):
        self.closed = True


def metadata(at_ms=T0, **kwargs):
    return FrameMetadata(edge_id="raspberrypi-01", camera_id="camera-01", captured_at_ms=at_ms, **kwargs)


def run(pipeline, frames, **kwargs):
    return [pipeline.process(FRAME, metadata(T0 + index * 100, **kwargs)) for index in range(frames)][-1]


def test_no_hand_is_unknown_with_zero_stability():
    meta = metadata()
    result = GesturePipeline(FakeDetector()).process(FRAME, meta)
    assert result.schema_version == SCHEMA_VERSION
    assert (result.frame_id, result.correlation_id) == (meta.frame_id, meta.correlation_id)
    assert (result.gesture, result.handedness, result.pointing_vector) == (GestureType.UNKNOWN, Handedness.UNKNOWN, None)
    assert (result.stable_frames, result.hold_time_ms) == (0, 0)
    assert result.detected_at_ms == meta.captured_at_ms


def test_held_pointing_reports_vector_and_stability():
    result = run(GesturePipeline(FakeDetector(pointing())), 6)
    assert result.gesture is GestureType.POINTING
    assert result.pointing_vector is not None
    assert (result.stable_frames, result.hold_time_ms) == (6, 500)


def test_hand_leaving_the_frame_restarts_stability():
    detector = FakeDetector(open_palm())
    pipeline = GesturePipeline(detector)
    run(pipeline, 6)
    detector.landmarks = None
    assert pipeline.process(FRAME, metadata(T0 + 600)).stable_frames == 0
    detector.landmarks = open_palm()
    assert pipeline.process(FRAME, metadata(T0 + 700)).stable_frames == 1


def test_only_pointing_carries_a_vector():
    result = GesturePipeline(FakeDetector(open_palm())).process(FRAME, metadata())
    assert result.gesture is GestureType.OPEN_PALM and result.pointing_vector is None


def test_pointing_too_small_for_a_direction_becomes_unknown():
    wrist = pointing()[0]
    tiny = [(wrist[0] + (x - wrist[0]) * 0.2, wrist[1] + (y - wrist[1]) * 0.2, z) for x, y, z in pointing()]
    assert GesturePipeline(FakeDetector(tiny)).process(FRAME, metadata()).gesture is GestureType.UNKNOWN


def test_mirrored_frame_flips_vector_and_handedness():
    plain = GesturePipeline(FakeDetector(pointing(), "Right")).process(FRAME, metadata())
    mirrored = GesturePipeline(FakeDetector(pointing(), "Right")).process(FRAME, metadata(mirrored=True))
    assert plain.handedness is Handedness.LEFT and mirrored.handedness is Handedness.RIGHT
    assert mirrored.pointing_vector.end_x == pytest.approx(1.0 - plain.pointing_vector.end_x)


def test_rotated_frame_is_classified_upright():
    # The camera sends the image turned 90° counterclockwise, so rotation_deg=90 turns it back.
    sent = [(y, 1.0 - x, z) for x, y, z in open_palm()]
    result = GesturePipeline(FakeDetector(sent)).process(FRAME, metadata(rotation_deg=90))
    assert result.gesture is GestureType.OPEN_PALM


def test_process_jpeg_decodes_in_memory():
    ok, jpeg = cv2.imencode(".jpg", FRAME)
    assert ok
    result = GesturePipeline(FakeDetector(open_palm())).process_jpeg(jpeg.tobytes(), metadata())
    assert result.gesture is GestureType.OPEN_PALM


def test_process_jpeg_rejects_invalid_frames():
    pipeline = GesturePipeline(FakeDetector())
    with pytest.raises(ValueError):
        pipeline.process_jpeg(b"not a jpeg", metadata())
    ok, jpeg = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))
    with pytest.raises(ValueError):
        pipeline.process_jpeg(jpeg.tobytes(), metadata())


def test_close_releases_the_detector():
    detector = FakeDetector()
    GesturePipeline(detector).close()
    assert detector.closed
