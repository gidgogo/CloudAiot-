"""Camera capture. Frames remain in memory and are never written to disk.

카메라 하드웨어는 백엔드로 분리한다. ``Camera``는 기존 스켈레톤 인터페이스
(``Camera(device_index, width, height, fps)``, ``open/frames/close``)를 그대로 유지하고,
``source`` 설정에 따라 실제 장치 접근을 백엔드에 맡긴다.

| source      | 용도 |
|-------------|------|
| ``opencv``    | USB 웹캠, 노트북 카메라, V4L2 장치 (기본값) |
| ``picamera2`` | Raspberry Pi 카메라 모듈(CSI). Pi에서 ``sudo apt install python3-picamera2`` |
| ``synthetic`` | 하드웨어 없이 움직이는 테스트 패턴 생성. 라즈베리파이·카메라 없이 개발할 때 |
| ``file``      | 동영상 파일·이미지 폴더·이미지 한 장을 반복 재생. 손이 나오는 같은 입력으로 AI·서버를 협업 테스트할 때 |

모든 백엔드는 OpenCV와 같은 BGR ``uint8`` 배열(height × width × 3)을 돌려준다.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Iterator, Protocol

import numpy as np


class CameraError(RuntimeError):
    """카메라를 열 수 없거나 계속 읽을 수 없음."""


class FrameBackend(Protocol):
    """카메라 하드웨어 접근 계층. 새 장치는 이 세 메서드만 구현하면 된다."""

    def open(self) -> None: ...

    def read(self) -> np.ndarray | None:
        """BGR 프레임 한 장. 일시적으로 읽지 못하면 None."""

    def close(self) -> None: ...


class OpenCVBackend:
    def __init__(self, device_index: int, width: int, height: int, fps: int) -> None:
        self.device_index, self.width, self.height, self.fps = device_index, width, height, fps
        self._cap = None

    def open(self) -> None:
        import cv2

        cap = cv2.VideoCapture(self.device_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        # 드라이버 내부 버퍼에 오래된 프레임이 쌓이지 않도록 최소화한다(지원하지 않는 장치는 무시).
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            cap.release()
            raise CameraError(f"cannot open camera {self.device_index}")
        self._cap = cap

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class PiCamera2Backend:
    """Raspberry Pi 카메라 모듈. picamera2는 Pi OS의 apt 패키지로만 설치되므로 실행 시점에 불러온다."""

    def __init__(self, device_index: int, width: int, height: int, fps: int) -> None:
        self.device_index, self.width, self.height, self.fps = device_index, width, height, fps
        self._cam = None

    def open(self) -> None:
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise CameraError(
                "picamera2 is not available; on Raspberry Pi OS run 'sudo apt install python3-picamera2' "
                "and create the venv with --system-site-packages"
            ) from exc
        try:
            cam = Picamera2(camera_num=self.device_index)
            # picamera2의 "RGB888"은 메모리상 B,G,R 순서라 OpenCV BGR과 바로 호환된다.
            config = cam.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": float(self.fps)},
                buffer_count=2,
            )
            cam.configure(config)
            cam.start()
        except Exception as exc:  # libcamera는 장치 없음·사용 중을 여러 예외 타입으로 알린다
            raise CameraError(f"cannot open Pi camera {self.device_index}: {exc}") from exc
        self._cam = cam

    def read(self) -> np.ndarray | None:
        if self._cam is None:
            return None
        try:
            frame = self._cam.capture_array("main")
        except Exception:
            return None
        return frame[:, :, :3] if frame.ndim == 3 and frame.shape[2] == 4 else frame

    def close(self) -> None:
        if self._cam is not None:
            try:
                self._cam.stop()
            finally:
                self._cam.close()
                self._cam = None


class SyntheticBackend:
    """하드웨어 없이 프레임을 만든다. 실제 카메라처럼 매 프레임 내용이 바뀐다(움직이는 사각형)."""

    def __init__(self, device_index: int, width: int, height: int, fps: int) -> None:
        self.width, self.height = width, height
        self._index = -1
        self._background: np.ndarray | None = None

    def open(self) -> None:
        x = np.linspace(0, 255, self.width, dtype=np.uint8)
        y = np.linspace(0, 255, self.height, dtype=np.uint8)
        background = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        background[:, :, 0] = x[None, :]
        background[:, :, 1] = y[:, None]
        background[:, :, 2] = 96
        self._background, self._index = background, -1

    def read(self) -> np.ndarray | None:
        if self._background is None:
            return None
        self._index += 1
        frame = self._background.copy()
        size = max(8, min(self.width, self.height) // 6)
        span_x, span_y = max(1, self.width - size), max(1, self.height - size)
        left, top = (self._index * 7) % span_x, (self._index * 5) % span_y
        frame[top:top + size, left:left + size] = 255
        return frame

    def close(self) -> None:
        self._background = None


IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp"})


class FileBackend:
    """녹화 파일을 카메라처럼 재생한다. 카메라·라즈베리파이 없이 실제 손 영상을 보낼 때 쓴다.

    - 동영상 파일(.mp4 등 OpenCV가 여는 형식): 프레임을 순서대로 읽고, 끝나면 처음으로 돌아간다.
    - 이미지 폴더: 파일 이름 순서로 한 장씩 돌려준다.
    - 이미지 한 장: 같은 장면을 계속 돌려준다.

    재생 속도는 원본 FPS가 아니라 설정 ``camera.fps``를 따른다(촬영 작업이 주기를 맞춘다).
    해상도가 설정과 다르면 ``FrameEncoder``가 맞춘다. 파일은 읽기만 하고 새로 저장하지 않는다.
    """

    def __init__(
        self, device_index: int, width: int, height: int, fps: int, *, path: str | None = None, loop: bool = True
    ) -> None:
        self.path = Path(path).expanduser() if path else None
        self.loop = loop
        self._cap = None
        self._images: list[Path] = []
        self._index = 0

    def open(self) -> None:
        import cv2

        if self.path is None:
            raise CameraError("camera.file_path (or --file) is required for source 'file'")
        if not self.path.exists():
            raise CameraError(f"file source not found: {self.path}")
        if self.path.is_dir():
            self._images = sorted(p for p in self.path.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
            if not self._images:
                raise CameraError(f"no images ({', '.join(sorted(IMAGE_SUFFIXES))}) in {self.path}")
        elif self.path.suffix.lower() in IMAGE_SUFFIXES:
            self._images = [self.path]
        else:
            cap = cv2.VideoCapture(str(self.path))
            if not cap.isOpened():
                cap.release()
                raise CameraError(f"cannot open video file {self.path}")
            self._cap = cap
        self._index = 0

    def read(self) -> np.ndarray | None:
        if self._cap is not None:
            return self._read_video()
        if not self._images:
            return None
        if self._index >= len(self._images):
            if not self.loop:
                return None
            self._index = 0
        import cv2

        frame = cv2.imread(str(self._images[self._index]), cv2.IMREAD_COLOR)
        self._index += 1
        return frame

    def _read_video(self) -> np.ndarray | None:
        import cv2

        ok, frame = self._cap.read()
        if not ok and self.loop:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._images = []


BackendFactory = Callable[[int, int, int, int], FrameBackend]
BACKENDS: dict[str, BackendFactory] = {
    "opencv": OpenCVBackend,
    "picamera2": PiCamera2Backend,
    "synthetic": SyntheticBackend,
    "file": FileBackend,
}


class Camera:
    def __init__(
        self,
        device_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 10,
        source: str = "opencv",
        backend: FrameBackend | None = None,
        file_path: str | None = None,
        file_loop: bool = True,
        **_: object,
    ) -> None:
        self.device_index, self.width, self.height, self.fps = device_index, width, height, fps
        if backend is None:
            if source not in BACKENDS:
                raise ValueError(f"unknown camera source {source!r}; choose one of {sorted(BACKENDS)}")
            if source == "file":
                backend = FileBackend(device_index, width, height, fps, path=file_path, loop=file_loop)
            else:
                backend = BACKENDS[source](device_index, width, height, fps)
        self.source = source
        self._backend = backend
        # read()는 작업 스레드에서 호출되므로, close()가 진행 중인 read()와 겹치지 않도록 잠근다.
        self._lock = threading.Lock()

    def open(self) -> None:
        with self._lock:
            self._backend.open()

    def read(self) -> np.ndarray | None:
        """프레임 한 장을 읽는다. 카메라가 닫혔거나 읽기에 실패하면 None."""
        with self._lock:
            return self._backend.read()

    def frames(self) -> Iterator[np.ndarray]:
        while (frame := self.read()) is not None:
            yield frame

    def close(self) -> None:
        with self._lock:
            self._backend.close()
