"""디바이스 메인 루프: 카메라 -> 시선/손동작 -> 의도 판단 -> 기기 제어/알림."""

import argparse
import logging

from cloudaiot.alert.client import AlertClient
from cloudaiot.config import load_config
from cloudaiot.devices.controller import DeviceController, build_devices
from cloudaiot.intent.fusion import IntentFusion
from cloudaiot.types import Action

log = logging.getLogger("cloudaiot")


def run(mock: bool = False) -> None:
    from cloudaiot.vision.camera import Camera
    from cloudaiot.vision.gaze import GazeEstimator
    from cloudaiot.vision.gesture import GestureRecognizer

    cfg = load_config()
    camera = Camera(**cfg["camera"])
    gaze = GazeEstimator(cfg["gaze"]["targets"], cfg["gaze"]["dwell_sec"])
    gesture = GestureRecognizer(cfg["gesture"]["min_confidence"])
    fusion = IntentFusion(
        cfg["gesture"]["mapping"],
        min_confidence=cfg["gesture"]["min_confidence"],
        **cfg["intent"],
    )
    controller = DeviceController(build_devices(cfg["devices"], mock=mock))
    alert = AlertClient(cfg["alert"]["server_url"], cfg["alert"]["timeout_sec"])

    camera.open()
    try:
        for frame in camera.frames():
            intent = fusion.decide(gaze.estimate(frame), gesture.recognize(frame))
            if intent is None:
                continue
            log.info("의도: %s", intent)
            if intent.action is Action.CALL_CAREGIVER:
                alert.send(intent)
            else:
                ok = controller.execute(intent)
                alert.send(intent, status="done" if ok else "failed")
    finally:
        camera.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="실제 GPIO 대신 가짜 기기 사용")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(mock=args.mock)


if __name__ == "__main__":
    main()
