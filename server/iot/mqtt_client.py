"""Paho-MQTT adapter with v1 QoS and retain defaults."""
from __future__ import annotations
import json
import paho.mqtt.client as mqtt
from shared.mqtt_topics import command_topic
from shared.types import MqttCommand
class MqttClient:
    def __init__(self, host:str, port:int=1883, *, tls:bool=False) -> None:
        self.client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if tls: self.client.tls_set()
        self.host,self.port=host,port
    def connect(self) -> None: self.client.connect(self.host,self.port); self.client.loop_start()
    def publish_command(self, home_id:str, command:MqttCommand) -> None:
        info=self.client.publish(command_topic(home_id,command.device_id),json.dumps(command.as_dict()),qos=1,retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS: raise ConnectionError("MQTT command publish failed")
    def close(self) -> None: self.client.loop_stop(); self.client.disconnect()
