"""MQTT v1 client for the Raspberry Pi LED agent."""
from __future__ import annotations

import logging
from typing import Any

from shared.mqtt_topics import ack_topic, command_topic, status_topic

from pi_led_agent.command_handler import CommandHandler, payload_of
from pi_led_agent.config import PiLedAgentConfig
from pi_led_agent.state_publisher import QOS, StatePublisher

log = logging.getLogger(__name__)


class PiLedMqttAgent:
    def __init__(self, config: PiLedAgentConfig, handler: CommandHandler, *, client: Any | None = None) -> None:
        self.config = config
        self.handler = handler
        self.client = client if client is not None else self._create_client()
        self.publisher = StatePublisher(config.mqtt_home_id, handler, self._publish)
        self.client.will_set(
            status_topic(config.mqtt_home_id, handler.device_id), self.publisher.status_payload(False), qos=QOS, retain=True
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _create_client(self) -> Any:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise RuntimeError("paho-mqtt is required; install the pi-led-agent dependency") from exc
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.config.mqtt_client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        if self.config.mqtt_tls:
            client.tls_set()
        if self.config.mqtt_username:
            client.username_pw_set(self.config.mqtt_username, self.config.mqtt_password)
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        return client

    def start(self) -> None:
        self.client.connect_async(self.config.mqtt_host, self.config.mqtt_port, keepalive=self.config.mqtt_keepalive_sec)
        self.client.loop_start()

    def stop(self) -> None:
        if self._is_connected():
            self.publisher.publish_offline()
        self.client.disconnect()
        self.client.loop_stop()

    def _publish(self, topic: str, payload: str, qos: int, retain: bool) -> object:
        return self.client.publish(topic, payload, qos=qos, retain=retain)

    def _is_connected(self) -> bool:
        checker = getattr(self.client, "is_connected", None)
        return bool(checker()) if callable(checker) else True

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        if getattr(reason_code, "is_failure", bool(reason_code)):
            log.warning("MQTT connection refused: %s", reason_code)
            return
        client.subscribe(command_topic(self.config.mqtt_home_id, self.handler.device_id), qos=QOS)
        self.publisher.publish_online()
        self.publisher.publish_state()
        log.info("LED agent connected as %s", self.handler.device_id)

    def _on_disconnect(self, client: Any, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any = None) -> None:
        log.warning("LED agent disconnected: %s", reason_code)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        result = self.handler.handle(message.payload)
        if result.ack is not None:
            self._publish(
                ack_topic(self.config.mqtt_home_id, self.handler.device_id), payload_of(result.ack), QOS, False
            )
        if result.state is not None:
            self.publisher.publish_state()
