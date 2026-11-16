"""Entrypoint for the Raspberry Pi MQTT LED agent."""
from __future__ import annotations

import logging
import signal
import threading
import time

from pi_led_agent.command_handler import CommandHandler
from pi_led_agent.config import PiLedAgentConfig
from pi_led_agent.led_controller import LedController
from pi_led_agent.mqtt_client import PiLedMqttAgent

MIN_VALID_UNIX_TIME = 1_704_067_200  # 2024-01-01 UTC


def system_clock_is_synchronized() -> bool:
    """Reject expiry-sensitive commands when the system clock is obviously unset."""
    return time.time() >= MIN_VALID_UNIX_TIME


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = PiLedAgentConfig.from_env()
    led = LedController.from_gpio(config.led_gpio_pin, active_low=config.led_active_low)
    handler = CommandHandler(config.mqtt_device_id, led, time_synced=system_clock_is_synchronized)
    agent = PiLedMqttAgent(config, handler)
    stopping = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        stopping.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        agent.start()
        stopping.wait()
    finally:
        agent.stop()
        led.close()


if __name__ == "__main__":
    run()
