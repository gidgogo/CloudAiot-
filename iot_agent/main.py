"""IoT 제어 Pi 진입점.

    python -m iot_agent.main                 # 실제 GPIO 릴레이 (라즈베리파이)
    python -m iot_agent.main --mock          # 하드웨어 없이 개발 (시간 동기화 검사도 생략)
"""
from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path

from iot_agent.command_handler import CommandHandler
from iot_agent.config import load_config
from iot_agent.mqtt_agent import DeviceMqttAgent
from iot_agent.relay import build_relays
from iot_agent.time_sync import NtpSyncChecker

log = logging.getLogger("iot_agent")


def run(config_path: Path | None = None, *, mock: bool = False) -> None:
    config = load_config(config_path)
    agent_cfg, mqtt_cfg = config["agent"], config["mqtt"]
    relays = build_relays(config["devices"], mock=mock)

    if mock or not config.get("time_sync", {}).get("required", True):
        log.info("time sync check disabled")
        time_synced = lambda: True  # noqa: E731
    else:
        time_synced = NtpSyncChecker()

    agents = [
        DeviceMqttAgent(
            agent_cfg["home_id"],
            agent_cfg.get("agent_id", "raspberrypi-iot"),
            CommandHandler(device_id, relay, time_synced=time_synced),
            mqtt_cfg,
        )
        for device_id, relay in relays.items()
    ]

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):  # systemd stop은 SIGTERM
        signal.signal(sig, lambda *_: stop.set())

    for agent in agents:
        agent.start()
    log.info("controlling %s (home_id=%s)", ", ".join(relays), agent_cfg["home_id"])
    try:
        stop.wait()
    finally:
        for agent in agents:
            agent.stop()
        for relay in relays.values():
            relay.close()
        log.info("stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudAIoT Raspberry Pi IoT controller")
    parser.add_argument("--config", type=Path, help="설정 파일 경로 (기본: iot_agent/config.yaml 또는 예제)")
    parser.add_argument("--mock", action="store_true", help="GPIO 대신 Mock 릴레이 사용, 시간 동기화 검사 생략")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(args.config, mock=args.mock)


if __name__ == "__main__":
    main()
