"""라즈베리파이 진입점. 현재는 카메라 입력 점검만 지원한다."""

import argparse
from pathlib import Path

from edge.config import load_config


def check_camera(config_path: Path | None = None) -> None:
    from edge.camera import Camera

    camera = Camera(**load_config(config_path)["camera"])
    try:
        camera.open()
        frame = next(camera.frames(), None)
        if frame is None:
            raise RuntimeError("No camera frame received")
        print(f"Camera OK: {frame.shape[1]}x{frame.shape[0]}")
    finally:
        camera.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi camera input tools")
    parser.add_argument("--config", type=Path, help="Path to edge YAML config")
    parser.add_argument("--check-camera", action="store_true", help="Capture one frame without saving it")
    args = parser.parse_args()
    if args.check_camera:
        check_camera(args.config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
