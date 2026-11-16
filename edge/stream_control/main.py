"""영상 송출 제어 진입점. systemd로 항상 띄워 두고, 송출(edge.main --stream)은 자식 프로세스로 켜고 끈다.

    python -m edge.stream_control.main            # 라즈베리파이: GPIO 버튼·LED
    python -m edge.stream_control.main --mock     # 노트북: 버튼 없음, LED는 로그, 카메라는 synthetic

설정은 edge/config.yaml의 ``stream_control`` 절을 따른다(없으면 예제 파일).
송출 프로세스와 제어 프로세스를 나누는 이유: 송출이 꺼져 있거나 카메라 오류로 죽어도
버튼 입력과 LED 표시는 계속 살아 있어야 하기 때문이다.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import threading
from pathlib import Path
from typing import Any

from edge.config import load_config
from edge.stream_control.panel import GpioButton, Indicator, LogIndicator, StreamPanel, gpio_led
from edge.stream_control.switch import ProcessSwitch, default_stream_command

log = logging.getLogger("edge.stream_control")

POLL_SEC = 0.5  # 송출 프로세스가 스스로 죽었는지 확인하는 주기

# 원격 제어 MQTT 설정은 환경변수가 우선한다. 비밀번호는 파일에 쓰지 않는 것을 권장한다.
MQTT_HOST_ENV = "EDGE_MQTT_HOST"
MQTT_USERNAME_ENV = "EDGE_MQTT_USERNAME"
MQTT_PASSWORD_ENV = "EDGE_MQTT_PASSWORD"

DEFAULTS: dict[str, Any] = {
    "device_id": "edge-stream-01",
    "button_pin": None,
    "led_pin": None,
    "initial_state": "OFF",
    "command": None,
    "remote": {"enabled": False},
}


def stream_control_settings(config: dict[str, Any]) -> dict[str, Any]:
    """config의 stream_control 절에 기본값과 환경변수를 적용한다."""
    settings = {**DEFAULTS, **(config.get("stream_control") or {})}
    remote = {"enabled": False, **(settings.get("remote") or {})}
    if remote["enabled"]:
        if not remote.get("home_id"):
            raise ValueError("stream_control.remote.home_id is required when remote.enabled is true")
        mqtt = dict(remote.get("mqtt") or {})
        mqtt["host"] = os.environ.get(MQTT_HOST_ENV) or mqtt.get("host", "localhost")
        mqtt["username"] = os.environ.get(MQTT_USERNAME_ENV) or mqtt.get("username")
        mqtt["password"] = os.environ.get(MQTT_PASSWORD_ENV) or mqtt.get("password")
        remote["mqtt"] = mqtt
    settings["remote"] = remote
    # YAML 1.1은 따옴표 없는 ON/OFF를 True/False로 읽으므로 둘 다 받는다
    initial = settings["initial_state"]
    settings["initial_on"] = initial is True or str(initial).upper() == "ON"
    return settings


def run(config_path: Path | None = None, *, mock: bool = False) -> None:
    settings = stream_control_settings(load_config(config_path))
    device_id = settings["device_id"]
    switch = ProcessSwitch(device_id, settings["command"] or default_stream_command(mock=mock))
    if settings["initial_on"]:
        switch.set(True)

    led_pin, button_pin = settings["led_pin"], settings["button_pin"]
    led: Indicator = gpio_led(int(led_pin)) if led_pin is not None and not mock else LogIndicator(device_id)

    remote = build_remote(device_id, switch, settings["remote"], mock=mock)
    panel = StreamPanel(switch, led, remote.publish_state if remote else (lambda: None))
    if remote is not None:
        remote.after_command = panel.after_command

    button = None
    if button_pin is not None and not mock:
        button = GpioButton(int(button_pin), panel.press)
        log.info("[%s] button on GPIO%s, LED on GPIO%s", device_id, button_pin, led_pin)

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):  # systemd stop은 SIGTERM
        signal.signal(sig, lambda *_: stop.set())

    if remote is not None:
        remote.start()
    log.info("stream control ready (%s, remote MQTT %s)", device_id, "on" if remote else "off")
    try:
        while not stop.wait(POLL_SEC):
            panel.poll()
    finally:
        if button is not None:
            button.close()
        if remote is not None:
            remote.stop()
        switch.close()
        panel.close()
        log.info("stopped")


def build_remote(device_id: str, switch: ProcessSwitch, remote_cfg: dict[str, Any], *, mock: bool):
    """remote.enabled이면 MQTT 원격 ON/OFF를 붙인다. paho-mqtt는 이때만 필요하다."""
    if not remote_cfg.get("enabled"):
        return None
    from edge.stream_control.command_handler import CommandHandler
    from edge.stream_control.mqtt_agent import DeviceMqttAgent
    from edge.stream_control.time_sync import NtpSyncChecker

    if mock or not remote_cfg.get("time_sync_required", True):
        log.info("time sync check disabled")
        time_synced = lambda: True  # noqa: E731
    else:
        time_synced = NtpSyncChecker()
    handler = CommandHandler(device_id, switch, time_synced=time_synced)
    return DeviceMqttAgent(remote_cfg["home_id"], remote_cfg.get("client_id", "raspberrypi"), handler, remote_cfg["mqtt"])


def main() -> None:
    parser = argparse.ArgumentParser(description="CloudAIoT edge stream control (button/LED, optional MQTT)")
    parser.add_argument("--config", type=Path, help="설정 파일 경로 (기본: edge/config.yaml 또는 예제)")
    parser.add_argument("--mock", action="store_true", help="GPIO 없이 실행, 송출은 synthetic, 시간 동기화 검사 생략")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(args.config, mock=args.mock)


if __name__ == "__main__":
    main()
