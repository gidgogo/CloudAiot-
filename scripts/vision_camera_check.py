"""Run GesturePipeline on a local webcam and overlay the result. Press q to quit."""

import argparse

import cv2

from server.vision.pipeline import GesturePipeline
from shared.types import FrameMetadata


def run(camera_index: int) -> None:
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        raise SystemExit(f"cannot open camera {camera_index}")
    pipeline = GesturePipeline()
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            height, width = frame.shape[:2]
            # Raw webcam frames are not mirrored; flip only the preview so it feels like a mirror.
            result = pipeline.process(frame, FrameMetadata(width=width, height=height, mirrored=False))
            preview = cv2.flip(frame, 1)
            draw_result(preview, result)
            cv2.imshow("vision check", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        pipeline.close()
        capture.release()
        cv2.destroyAllWindows()


def draw_result(preview, result) -> None:
    lines = [
        f"gesture: {result.gesture.value}",
        f"hand: {result.handedness.value}",
        f"stable: {result.stable_frames} frames / {result.hold_time_ms} ms",
    ]
    for row, text in enumerate(lines):
        cv2.putText(preview, text, (10, 30 + 30 * row), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    vector = result.pointing_vector
    if vector is not None:
        height, width = preview.shape[:2]
        # Preview is flipped, so mirror the x coordinates too.
        start = (int((1 - vector.start_x) * width), int(vector.start_y * height))
        end = (int((1 - vector.end_x) * width), int(vector.end_y * height))
        cv2.arrowedLine(preview, start, end, (0, 0, 255), 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    run(parser.parse_args().camera)


if __name__ == "__main__":
    main()
