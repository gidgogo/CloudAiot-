import json
from types import SimpleNamespace

from pi_led_agent.command_handler import CommandHandler
from pi_led_agent.config import PiLedAgentConfig
from pi_led_agent.led_controller import LedController
from pi_led_agent.mqtt_client import PiLedMqttAgent
from shared.types import IntentAction, MqttCommand, now_ms


class FakeLed:
    is_lit = False

    def on(self): self.is_lit = True
    def off(self): self.is_lit = False
    def close(self): pass


class FakeClient:
    def __init__(self):
        self.published, self.subscribed = [], []
        self.will = None
        self.connected = True

    def will_set(self, topic, payload, qos, retain): self.will = (topic, json.loads(payload), qos, retain)
    def publish(self, topic, payload, qos=0, retain=False): self.published.append((topic, json.loads(payload), qos, retain))
    def subscribe(self, topic, qos=0): self.subscribed.append((topic, qos))
    def is_connected(self): return self.connected
    def disconnect(self): self.connected = False
    def loop_stop(self): pass


def config():
    return PiLedAgentConfig.from_env({
        "MQTT_HOST": "192.168.1.10", "MQTT_HOME_ID": "home-01", "MQTT_DEVICE_ID": "pi-led-01",
    })


def agent():
    handler = CommandHandler("pi-led-01", LedController(FakeLed()))
    client = FakeClient()
    return PiLedMqttAgent(config(), handler, client=client), client


def test_connect_subscribes_then_publishes_retained_online_and_state():
    instance, client = agent()
    instance._on_connect(client, None, None, SimpleNamespace(is_failure=False), None)
    assert client.subscribed == [("aiot/v1/home-01/pi-led-01/cmd", 1)]
    assert {(topic, payload.get("status") or payload.get("state"), qos, retain) for topic, payload, qos, retain in client.published} == {
        ("aiot/v1/home-01/pi-led-01/status", "ONLINE", 1, True),
        ("aiot/v1/home-01/pi-led-01/state", "OFF", 1, True),
    }


def test_message_publishes_non_retained_ack_and_retained_changed_state():
    instance, client = agent()
    issued = now_ms()
    payload = json.dumps(MqttCommand(correlation_id="corr-1", device_id="pi-led-01", action=IntentAction.ON, issued_at_ms=issued, expires_at_ms=issued + 5_000).as_dict())
    instance._on_message(client, None, SimpleNamespace(payload=payload.encode()))
    assert [(topic, qos, retain) for topic, _, qos, retain in client.published] == [
        ("aiot/v1/home-01/pi-led-01/ack", 1, False),
        ("aiot/v1/home-01/pi-led-01/state", 1, True),
    ]
    assert client.published[0][1]["result"] == "OK"
    assert client.published[1][1]["state"] == "ON"


def test_lwt_is_retained_offline_status():
    instance, client = agent()
    assert client.will == ("aiot/v1/home-01/pi-led-01/status", {
        "schema_version": "1.0", "device_id": "pi-led-01", "status": "OFFLINE", "timestamp_ms": client.will[1]["timestamp_ms"],
    }, 1, True)
