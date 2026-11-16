"""카메라 백엔드 추상화 테스트. 실제 카메라·Raspberry Pi 없이 실행된다."""
import sys
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from edge.camera import BACKENDS, Camera, CameraError, PiCamera2Backend, SyntheticBackend
from edge.config import EXAMPLE_PATH, load_config
from edge.main import camera_settings


def test_default_source_is_opencv_and_skeleton_signature_still_works():
    camera = Camera(0, 640, 480, 10)
    assert camera.source == "opencv"
    assert (camera.device_index, camera.width, camera.height, camera.fps) == (0, 640, 480, 10)


def test_example_config_builds_camera():
    config = load_config(EXAMPLE_PATH)["camera"]
    assert config["source"] in BACKENDS
    Camera(**config)  # 설정의 추가 키(jpeg_quality 등)는 무시된다


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="unknown camera source"):
        Camera(source="kinect")


def test_synthetic_camera_produces_changing_bgr_frames():
    camera = Camera(width=320, height=240, source="synthetic")
    assert camera.read() is None  # 열기 전
    camera.open()
    first, second = camera.read(), camera.read()
    camera.close()
    assert first.shape == (240, 320, 3) and first.dtype == np.uint8
    assert not np.array_equal(first, second)
    assert camera.read() is None  # 닫은 뒤


def test_frames_iterator_stops_when_backend_fails():
    class TwoFrames:
        def __init__(self):
            self.left = 2

        def open(self): pass
        def close(self): pass

        def read(self):
            self.left -= 1
            return np.zeros((2, 2, 3), np.uint8) if self.left >= 0 else None

    camera = Camera(backend=TwoFrames())
    camera.open()
    assert len(list(camera.frames())) == 2


def test_camera_close_waits_for_in_flight_read():
    events = []

    class SlowBackend:
        def open(self): pass

        def read(self):
            events.append("read-start"); time.sleep(0.2); events.append("read-end")
            return np.zeros((2, 2, 3), np.uint8)

        def close(self):
            events.append("close")

    camera = Camera(backend=SlowBackend())
    reader = threading.Thread(target=camera.read)
    reader.start()
    time.sleep(0.05)
    camera.close()
    reader.join()
    assert events == ["read-start", "read-end", "close"]


def test_picamera2_missing_gives_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)  # import 실패 흉내
    with pytest.raises(CameraError, match="python3-picamera2"):
        PiCamera2Backend(0, 640, 480, 10).open()


def test_picamera2_backend_configures_and_reads(monkeypatch):
    calls = {}

    class FakePicamera2:
        def __init__(self, camera_num):
            calls["camera_num"] = camera_num

        def create_video_configuration(self, main, controls, buffer_count):
            calls["main"], calls["controls"] = main, controls
            return "config"

        def configure(self, config): calls["configured"] = config
        def start(self): calls["started"] = True
        def capture_array(self, name): return np.zeros((480, 640, 4), np.uint8)  # XBGR 형식 대비
        def stop(self): calls["stopped"] = True
        def close(self): calls["closed"] = True

    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=FakePicamera2))
    camera = Camera(1, 640, 480, 15, source="picamera2")
    camera.open()
    frame = camera.read()
    camera.close()
    assert calls["camera_num"] == 1
    assert calls["main"] == {"size": (640, 480), "format": "RGB888"}
    assert calls["controls"] == {"FrameRate": 15.0}
    assert frame.shape == (480, 640, 3)
    assert calls["stopped"] and calls["closed"]


def test_picamera2_open_failure_is_camera_error(monkeypatch):
    class Busy:
        def __init__(self, camera_num):
            raise IndexError("list index out of range")  # 장치 없음 시 실제 picamera2 동작

    monkeypatch.setitem(sys.modules, "picamera2", SimpleNamespace(Picamera2=Busy))
    with pytest.raises(CameraError, match="cannot open Pi camera"):
        Camera(source="picamera2").open()


def test_source_override_priority(monkeypatch):
    monkeypatch.delenv("EDGE_CAMERA_SOURCE", raising=False)
    assert camera_settings({"source": "opencv"})["source"] == "opencv"
    monkeypatch.setenv("EDGE_CAMERA_SOURCE", "picamera2")
    assert camera_settings({"source": "opencv"})["source"] == "picamera2"
    assert camera_settings({"source": "opencv"}, "synthetic")["source"] == "synthetic"


def test_synthetic_backend_handles_tiny_frames():
    backend = SyntheticBackend(0, 4, 4, 10)
    backend.open()
    assert backend.read().shape == (4, 4, 3)


# --- file 소스: 협업용 더미 송출 ---------------------------------------------

def _write_images(folder, count=3, size=(48, 64)):
    import cv2

    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        image = np.full((*size, 3), i * 80, dtype=np.uint8)
        cv2.imwrite(str(folder / f"{i:03d}.png"), image)
    return folder


def _write_video(path, count=4, size=(48, 64)):
    import cv2

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (size[1], size[0]))
    assert writer.isOpened()
    for i in range(count):
        writer.write(np.full((*size, 3), i * 60, dtype=np.uint8))
    writer.release()
    return path


def test_file_source_is_registered():
    assert "file" in BACKENDS


def test_file_source_loops_image_folder_in_name_order(tmp_path):
    camera = Camera(source="file", file_path=str(_write_images(tmp_path / "frames")))
    camera.open()
    values = [int(camera.read()[0, 0, 0]) for _ in range(5)]
    camera.close()
    assert values == [0, 80, 160, 0, 80]


def test_file_source_without_loop_stops_at_end(tmp_path):
    camera = Camera(source="file", file_path=str(_write_images(tmp_path / "frames", count=2)), file_loop=False)
    camera.open()
    assert len(list(camera.frames())) == 2


def test_file_source_repeats_single_image(tmp_path):
    folder = _write_images(tmp_path / "one", count=1)
    camera = Camera(source="file", file_path=str(folder / "000.png"))
    camera.open()
    assert all(camera.read().shape == (48, 64, 3) for _ in range(3))


def test_file_source_loops_video(tmp_path):
    camera = Camera(source="file", file_path=str(_write_video(tmp_path / "clip.avi", count=4)))
    camera.open()
    frames = [camera.read() for _ in range(9)]
    camera.close()
    assert all(f is not None and f.shape == (48, 64, 3) for f in frames)


@pytest.mark.parametrize("path", [None, "does-not-exist.mp4"])
def test_file_source_reports_missing_path(tmp_path, path):
    camera = Camera(source="file", file_path=None if path is None else str(tmp_path / path))
    with pytest.raises(CameraError):
        camera.open()


def test_empty_image_folder_is_rejected(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(CameraError, match="no images"):
        Camera(source="file", file_path=str(tmp_path / "empty")).open()


def test_file_option_implies_file_source(monkeypatch):
    monkeypatch.delenv("EDGE_CAMERA_SOURCE", raising=False)
    monkeypatch.delenv("EDGE_CAMERA_FILE", raising=False)
    settings = camera_settings({"source": "opencv"}, file_path="hands.mp4")
    assert settings["source"] == "file" and settings["file_path"] == "hands.mp4"
    monkeypatch.setenv("EDGE_CAMERA_FILE", "env.mp4")
    assert camera_settings({"source": "opencv"})["file_path"] == "env.mp4"
    assert camera_settings({"source": "opencv"}, "synthetic", "x.mp4")["source"] == "synthetic"  # --source가 우선
