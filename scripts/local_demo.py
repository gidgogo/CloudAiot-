"""로컬 통합 데모. edge/server 모듈을 한 컴퓨터에서 함께 확인하는 개발용 도구."""

import argparse
import logging

from server.notifications.client import AlertClient
from edge.config import load_config as load_edge_config
from server.config import load_config as load_server_config
from edge.devices.controller import DeviceController, build_devices
from server.intent.fusion import IntentFusion
from shared.types import Action

log = logging.getLogger("cloudaiot")


def run(mock: bool = False) -> None:
    from edge.camera import Camera
    from server.vision.gaze import GazeEstimator
    from server.vision.gesture import GestureRecognizer

    edge_cfg = load_edge_config()
    cfg = load_server_config()
    camera = Camera(**edge_cfg["camera"])
    gaze = GazeEstimator(cfg["gaze"]["targets"], cfg["gaze"]["dwell_sec"])
    gesture = GestureRecognizer(cfg["gesture"]["min_confidence"])
    fusion = IntentFusion(
        cfg["gesture"]["mapping"],
        min_confidence=cfg["gesture"]["min_confidence"],
        **cfg["intent"],
    )
    controller = DeviceController(build_devices(edge_cfg["devices"], mock=mock))
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
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock GPIO devices (a camera is still required)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(mock=args.mock)


if __name__ == "__main__":
    main()
