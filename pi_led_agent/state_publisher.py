"""Build and publish retained LED state and connection status messages."""
from __future__ import annotations

from typing import Callable

from shared.mqtt_topics import state_topic, status_topic
from shared.types import DeviceConnectionStatus, DeviceStatusMessage

from pi_led_agent.command_handler import CommandHandler, payload_of

QOS = 1
Publish = Callable[[str, str, int, bool], object]


class StatePublisher:
    def __init__(self, home_id: str, handler: CommandHandler, publish: Publish) -> None:
        self.home_id = home_id
        self.handler = handler
        self._publish = publish

    def status_payload(self, online: bool) -> str:
        status = DeviceConnectionStatus.ONLINE if online else DeviceConnectionStatus.OFFLINE
        return payload_of(DeviceStatusMessage(device_id=self.handler.device_id, status=status))

    def publish_online(self) -> None:
        self._publish(status_topic(self.home_id, self.handler.device_id), self.status_payload(True), QOS, True)

    def publish_offline(self) -> None:
        self._publish(status_topic(self.home_id, self.handler.device_id), self.status_payload(False), QOS, True)

    def publish_state(self) -> None:
        self._publish(state_topic(self.home_id, self.handler.device_id), payload_of(self.handler.state_message()), QOS, True)
