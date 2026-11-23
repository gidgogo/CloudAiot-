"""MQTT bridge owned by the single API process.

It publishes confirmed ON/OFF intents and consumes ACK, retained state and LWT status messages.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

import paho.mqtt.client as mqtt

from server.db.session import Database
from server.iot.ack_handler import parse_ack
from server.iot.command_service import command_from_intent
from server.iot.device_state_handler import parse_state, parse_status
from server.services.control_event_service import ControlEventService
from server.services.device_service import DeviceService
from shared.constants import ACK_TIMEOUT_MS, MQTT_API_VERSION
from shared.mqtt_topics import command_topic, parse_device_topic
from shared.types import IntentResult

log = logging.getLogger(__name__)


class MqttBridge:
    def __init__(
        self,
        db: Database,
        events,
        *,
        host: str,
        port: int = 1883,
        home_id: str = "home-01",
        tls: bool = False,
        username: str | None = None,
        password: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.db = db
        self.events = events
        self.host = host
        self.port = port
        self.home_id = home_id
        self.client = client or mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self.client.username_pw_set(username, password)
        if tls:
            self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def connect(self) -> None:
        self.client.connect(self.host, self.port)
        self.client.loop_start()

    def close(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()
        self.client.loop_stop()
        self.client.disconnect()

    def publish_intent(self, intent: IntentResult) -> None:
        command = command_from_intent(intent)
        info = self.client.publish(
            command_topic(self.home_id, command.device_id),
            json.dumps(command.as_dict()),
            qos=1,
            retain=False,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError("MQTT command publish failed")
        with self.db.session() as session:
            ControlEventService(session, self.events).record_command(
                command, gesture_confirmed_at_ms=intent.confirmed_at_ms
            )
        timer = threading.Timer(ACK_TIMEOUT_MS / 1000, self._mark_timeout, args=(command.command_id,))
        timer.daemon = True
        with self._lock:
            self._timers[command.command_id] = timer
        timer.start()

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties=None) -> None:
        is_failure = getattr(reason_code, "is_failure", None)
        connection_failed = bool(is_failure) if is_failure is not None else int(reason_code) != 0
        if connection_failed:
            log.error("MQTT connection failed reason_code=%s", reason_code)
            return
        prefix = f"aiot/{MQTT_API_VERSION}/{self.home_id}/+"
        for suffix in ("ack", "state", "status"):
            client.subscribe(f"{prefix}/{suffix}", qos=1)
        log.info("MQTT connected home_id=%s", self.home_id)

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            payload = json.loads(message.payload)
            if not isinstance(payload, dict):
                raise ValueError("MQTT payload must be an object")
            version, home_id, device_id, suffix = parse_device_topic(message.topic)
            if version != MQTT_API_VERSION or home_id != self.home_id:
                raise ValueError("MQTT topic version or home_id mismatch")
            if suffix == "ack":
                ack = parse_ack(payload)
                if ack.device_id != device_id:
                    raise ValueError("ACK device_id does not match topic")
                with self.db.session() as session:
                    ControlEventService(session, self.events).record_ack(ack)
                self._cancel_timeout(ack.command_id)
            elif suffix == "state":
                state = parse_state(payload)
                if state.device_id != device_id:
                    raise ValueError("state device_id does not match topic")
                with self.db.session() as session:
                    DeviceService(session, self.events).update_state(
                        state.device_id, state.state, state.updated_at_ms
                    )
            else:
                status = parse_status(payload)
                if status.device_id != device_id:
                    raise ValueError("status device_id does not match topic")
                with self.db.session() as session:
                    DeviceService(session, self.events).update_connection_status(
                        status.device_id, status.status, status.timestamp_ms
                    )
        except Exception:
            log.exception("invalid MQTT message topic=%s", message.topic)

    def _cancel_timeout(self, command_id: str) -> None:
        with self._lock:
            timer = self._timers.pop(command_id, None)
        if timer is not None:
            timer.cancel()

    def _mark_timeout(self, command_id: str) -> None:
        with self._lock:
            self._timers.pop(command_id, None)
        try:
            with self.db.session() as session:
                ControlEventService(session, self.events).mark_timeout(command_id)
        except Exception:
            log.exception("failed to mark MQTT ACK timeout command_id=%s", command_id)
