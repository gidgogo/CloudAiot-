"""송출 원격 ON/OFF용 MQTT 연결. cmd를 구독하고 ack·state·status를 발행한다.

LWT(유언 메시지)로 ``aiot/v1/{home_id}/{device_id}/status``에 OFFLINE을 남긴다(규격 11.8).

Topic·QoS·Retain (규격 11.5)
- cmd    구독  QoS 1
- ack    발행  QoS 1, retain false
- state  발행  QoS 1, retain true
- status 발행  QoS 1, retain true (+ LWT OFFLINE)
- Clean Session, 초기 자동 재전송 없음
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import paho.mqtt.client as mqtt

from shared.mqtt_topics import ack_topic, command_topic, state_topic, status_topic
from shared.types import DeviceConnectionStatus, DeviceStatusMessage

from edge.stream_control.command_handler import CommandHandler, payload_of

log = logging.getLogger(__name__)

QOS = 1
RECONNECT_MIN_SEC, RECONNECT_MAX_SEC = 1, 30


class DeviceMqttAgent:
    def __init__(self, home_id: str, agent_id: str, handler: CommandHandler, mqtt_cfg: dict[str, Any]) -> None:
        self.home_id = home_id
        self.device_id = handler.device_id
        self.handler = handler
        self.host = mqtt_cfg.get("host", "localhost")
        self.port = int(mqtt_cfg.get("port", 1883))
        self.keepalive = int(mqtt_cfg.get("keepalive_sec", 30))

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{agent_id}-{self.device_id}",
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        if mqtt_cfg.get("tls"):
            self.client.tls_set()
        if mqtt_cfg.get("username"):
            self.client.username_pw_set(mqtt_cfg["username"], mqtt_cfg.get("password"))
        self.client.will_set(status_topic(home_id, self.device_id), self._status_payload(False), qos=QOS, retain=True)
        self.client.reconnect_delay_set(RECONNECT_MIN_SEC, RECONNECT_MAX_SEC)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        # 명령 처리 직후 호출된다. 여기서 상태 LED를 맞춘다.
        self.after_command: Callable[[], None] | None = None

    def publish_state(self) -> None:
        """명령이 아닌 경로(물리 버튼, 프로세스 종료)로 상태가 바뀌었을 때 state를 retain으로 발행한다."""
        if not self.client.is_connected():
            return  # 재접속하면 _on_connect가 현재 state를 다시 발행한다
        self.client.publish(
            state_topic(self.home_id, self.device_id), payload_of(self.handler.state_message()), qos=QOS, retain=True
        )

    def start(self) -> None:
        # connect_async: 브로커가 아직 없어도 백그라운드에서 재시도한다
        self.client.connect_async(self.host, self.port, keepalive=self.keepalive)
        self.client.loop_start()

    def stop(self) -> None:
        """정상 종료 시에는 LWT가 발행되지 않으므로 OFFLINE을 직접 남기고 끊는다."""
        if self.client.is_connected():
            info = self.client.publish(status_topic(self.home_id, self.device_id), self._status_payload(False), qos=QOS, retain=True)
            info.wait_for_publish(timeout=2)
        self.client.disconnect()
        self.client.loop_stop()

    # --- paho callbacks (네트워크 스레드에서 호출) ---

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code.is_failure:
            log.warning("[%s] MQTT connect refused: %s", self.device_id, reason_code)
            return
        log.info("[%s] connected to %s:%d", self.device_id, self.host, self.port)
        client.subscribe(command_topic(self.home_id, self.device_id), qos=QOS)
        client.publish(status_topic(self.home_id, self.device_id), self._status_payload(True), qos=QOS, retain=True)
        client.publish(state_topic(self.home_id, self.device_id), payload_of(self.handler.state_message()), qos=QOS, retain=True)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        log.warning("[%s] disconnected (%s); paho will reconnect", self.device_id, reason_code)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        result = self.handler.handle(message.payload)
        if result.ack is not None:
            client.publish(ack_topic(self.home_id, self.device_id), payload_of(result.ack), qos=QOS, retain=False)
            log.info("[%s] command %s -> %s", self.device_id, result.ack.command_id, result.ack.result.value)
        if result.state is not None:
            client.publish(state_topic(self.home_id, self.device_id), payload_of(result.state), qos=QOS, retain=True)
        if self.after_command is not None:
            self.after_command()

    def _status_payload(self, online: bool) -> str:
        status = DeviceConnectionStatus.ONLINE if online else DeviceConnectionStatus.OFFLINE
        return payload_of(DeviceStatusMessage(device_id=self.device_id, status=status))
