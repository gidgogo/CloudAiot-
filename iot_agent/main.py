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
from iot_agent.panel import GpioButton, LogIndicator, StreamPanel, gpio_led
from iot_agent.relay import build_relays
from iot_agent.stream_switch import ProcessSwitch
from iot_agent.time_sync import NtpSyncChecker

log = logging.getLogger("iot_agent")

POLL_SEC = 0.5  # 송출 프로세스가 스스로 죽었는지 확인하는 주기


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

    panels, buttons = build_panels(config["devices"], relays, agents, mock=mock)

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):  # systemd stop은 SIGTERM
        signal.signal(sig, lambda *_: stop.set())

    for agent in agents:
        agent.start()
    log.info("controlling %s (home_id=%s)", ", ".join(relays), agent_cfg["home_id"])
    try:
        while not stop.wait(POLL_SEC):
            for panel in panels:
                panel.poll()
    finally:
        for button in buttons:
            button.close()
        for agent in agents:
            agent.stop()
        for relay in relays.values():
            relay.close()
        for panel in panels:
            panel.close()
        log.info("stopped")


def build_panels(devices_cfg: dict, relays: dict, agents: list[DeviceMqttAgent], *, mock: bool) -> tuple[list, list]:
    """edge_stream 기기마다 상태 LED와 버튼을 붙인다. 핀을 안 적으면 LED는 로그로 대신하고 버튼은 없다."""
    panels: list[StreamPanel] = []
    buttons: list[GpioButton] = []
    for agent in agents:
        spec = devices_cfg[agent.device_id]
        switch = relays[agent.device_id]
        if spec.get("type") != "edge_stream" or not isinstance(switch, ProcessSwitch):
            continue
        led_pin, button_pin = spec.get("led_pin"), spec.get("button_pin")
        led = gpio_led(int(led_pin)) if led_pin is not None and not mock else LogIndicator(agent.device_id)
        panel = StreamPanel(switch, led, agent.publish_state)
        agent.after_command = panel.after_command
        panels.append(panel)
        if button_pin is not None and not mock:
            buttons.append(GpioButton(int(button_pin), panel.press))
            log.info("[%s] button on GPIO%s, LED on GPIO%s", agent.device_id, button_pin, led_pin)
    return panels, buttons


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
