"""송출 원격 제어의 MQTT Topic·QoS·Retain 규칙 테스트 (브로커 없이 콜백만 호출)."""
import json
from types import SimpleNamespace

from edge.stream_control.command_handler import CommandHandler
from edge.stream_control.mqtt_agent import DeviceMqttAgent
from shared.types import IntentAction, MqttCommand, now_ms


class FakeSwitch:
    is_on = False

    def set(self, on):
        self.is_on = on


class FakeClient:
    def __init__(self):
        self.published, self.subscribed = [], []

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, json.loads(payload), qos, retain))

    def subscribe(self, topic, qos=0):
        self.subscribed.append((topic, qos))


def make_agent():
    handler = CommandHandler("edge-stream-01", FakeSwitch())
    return DeviceMqttAgent("home-01", "pi-test", handler, {"host": "localhost"}), handler


def test_will_is_retained_offline_status():
    agent, _ = make_agent()
    will = agent.client._will_topic.decode(), json.loads(agent.client._will_payload), agent.client._will_qos, agent.client._will_retain
    assert will[0] == "aiot/v1/home-01/edge-stream-01/status"
    assert will[1]["status"] == "OFFLINE" and will[1]["device_id"] == "edge-stream-01"
    assert will[2:] == (1, True)


def test_on_connect_subscribes_and_announces_online_and_state():
    agent, _ = make_agent()
    client = FakeClient()
    agent._on_connect(client, None, None, SimpleNamespace(is_failure=False), None)
    assert client.subscribed == [("aiot/v1/home-01/edge-stream-01/cmd", 1)]
    topics = {(t, p.get("status") or p.get("state"), q, r) for t, p, q, r in client.published}
    assert topics == {
        ("aiot/v1/home-01/edge-stream-01/status", "ONLINE", 1, True),
        ("aiot/v1/home-01/edge-stream-01/state", "OFF", 1, True),
    }


def test_command_publishes_ack_not_retained_and_state_retained():
    agent, handler = make_agent()
    client = FakeClient()
    issued = now_ms()
    payload = json.dumps(MqttCommand(device_id="edge-stream-01", action=IntentAction.ON, issued_at_ms=issued, expires_at_ms=issued + 5000).as_dict())
    agent._on_message(client, None, SimpleNamespace(payload=payload.encode()))
    (ack_topic, ack, ack_qos, ack_retain), (state_topic, state, state_qos, state_retain) = client.published
    assert (ack_topic, ack["result"], ack_qos, ack_retain) == ("aiot/v1/home-01/edge-stream-01/ack", "OK", 1, False)
    assert (state_topic, state["state"], state_qos, state_retain) == ("aiot/v1/home-01/edge-stream-01/state", "ON", 1, True)
