"""손 랜드마크 검출 테스트. MediaPipe 모델 대신 가짜 landmarker를 사용한다."""

from types import SimpleNamespace

import numpy as np
import pytest

from server.vision.hand_detector import HandDetector

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


class FakeLandmarker:
    def __init__(self, hands=()):
        self.hands = list(hands)
        self.timestamps = []
        self.closed = False

    def detect_for_video(self, image, timestamp_ms):
        self.timestamps.append(timestamp_ms)
        landmarks = [[SimpleNamespace(x=x, y=y, z=z) for x, y, z in points] for points, _, _ in self.hands]
        handedness = [[SimpleNamespace(category_name=label, score=score)] for _, label, score in self.hands]
        return SimpleNamespace(hand_landmarks=landmarks, handedness=handedness)

    def close(self):
        self.closed = True


def test_returns_first_hand_landmarks_label_and_score():
    points = [(0.1 * i / 21, 0.5, -0.01) for i in range(21)]
    detector = HandDetector(landmarker=FakeLandmarker([(points, "Left", 0.93)]))
    detection = detector.detect(FRAME, 1_000)
    assert detection is not None
    assert detection.landmarks == points
    assert (detection.mediapipe_label, detection.score) == ("Left", 0.93)


def test_no_hand_returns_none():
    assert HandDetector(landmarker=FakeLandmarker()).detect(FRAME, 1_000) is None


def test_timestamps_sent_to_mediapipe_always_increase():
    landmarker = FakeLandmarker()
    detector = HandDetector(landmarker=landmarker)
    for timestamp_ms in (1_000, 1_000, 900, 1_100):
        detector.detect(FRAME, timestamp_ms)
    assert landmarker.timestamps == [1_000, 1_001, 1_002, 1_100]


def test_close_releases_the_landmarker():
    landmarker = FakeLandmarker()
    HandDetector(landmarker=landmarker).close()
    assert landmarker.closed


def test_missing_model_file_explains_where_to_download(tmp_path):
    with pytest.raises(FileNotFoundError, match="download"):
        HandDetector(tmp_path / "missing.task")
