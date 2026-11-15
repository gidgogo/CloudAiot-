"""송출 스위치·버튼/LED 패널·MQTT 명령 연동 테스트 (프로세스·GPIO·브로커 없이)."""
import json
import signal
import subprocess
import sys

from iot_agent.command_handler import CommandHandler
from iot_agent.mqtt_agent import DeviceMqttAgent
from iot_agent.panel import StreamPanel
from iot_agent.relay import build_relays
from iot_agent.stream_switch import ProcessSwitch
from shared.types import IntentAction, MqttCommand, now_ms


class FakeProc:
    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.returncode = None
        self.signals = []
        self.ignore_sigint = False

    def poll(self):
        return self.returncode

    def send_signal(self, sig):
        self.signals.append(sig)
        if not self.ignore_sigint:
            self.returncode = -sig

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("edge", timeout)
        return self.returncode

    def kill(self):
        self.returncode = -9


class FakePopen:
    def __init__(self):
        self.procs = []

    def __call__(self, *args, **kwargs):
        proc = FakeProc(*args, **kwargs)
        self.procs.append(proc)
        return proc


class FakeLed:
    def __init__(self):
        self.calls = []

    def on(self):
        self.calls.append("on")

    def off(self):
        self.calls.append("off")

    def blink(self, on_time, off_time):
        self.calls.append("blink")

    def close(self):
        self.calls.append("close")


def make_switch():
    popen = FakePopen()
    return ProcessSwitch("edge-stream-01", ["python", "-m", "edge.main", "--stream"], popen=popen), popen


def test_switch_starts_and_stops_with_sigint():
    switch, popen = make_switch()
    switch.set(True)
    assert switch.is_on and len(popen.procs) == 1
    switch.set(True)  # 이미 켜져 있으면 두 번 띄우지 않는다
    assert len(popen.procs) == 1
    switch.set(False)
    assert not switch.is_on
    assert popen.procs[0].signals == [signal.SIGINT]


def test_switch_kills_when_sigint_is_ignored():
    switch, popen = make_switch()
    switch.stop_timeout_sec = 0.01
    switch.set(True)
    popen.procs[0].ignore_sigint = True
    switch.set(False)
    assert popen.procs[0].returncode == -9


def test_crash_is_detected_once_and_cleared_on_restart():
    switch, popen = make_switch()
    switch.set(True)
    popen.procs[0].returncode = 1  # 카메라 오류 등으로 스스로 종료
    assert switch.check_exit() is True
    assert switch.crashed and not switch.is_on
    assert switch.check_exit() is False
    assert switch.toggle() is True
    assert not switch.crashed and len(popen.procs) == 2


def test_panel_button_toggles_led_and_publishes_state():
    switch, _ = make_switch()
    led, published = FakeLed(), []
    panel = StreamPanel(switch, led, lambda: published.append(switch.is_on))
    assert led.calls == ["off"] and published == []
    panel.press()
    assert led.calls[-1] == "on" and published == [True]
    panel.press()
    assert led.calls[-1] == "off" and published == [True, False]


def test_panel_blinks_and_publishes_when_stream_dies():
    switch, popen = make_switch()
    led, published = FakeLed(), []
    panel = StreamPanel(switch, led, lambda: published.append(switch.is_on))
    panel.press()
    popen.procs[0].returncode = 1
    panel.poll()
    assert led.calls[-1] == "blink" and published == [True, False]
    panel.poll()  # 변화가 없으면 다시 발행하지 않는다
    assert published == [True, False]


class FakeClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, json.loads(payload), qos, retain))

    def is_connected(self):
        return True


def test_mqtt_on_command_starts_stream_and_updates_led_without_double_publish():
    switch, _ = make_switch()
    agent = DeviceMqttAgent("home-01", "pi-test", CommandHandler("edge-stream-01", switch), {"host": "localhost"})
    led, published = FakeLed(), []
    panel = StreamPanel(switch, led, lambda: published.append("button-path"))
    agent.after_command = panel.after_command
    client = FakeClient()
    issued = now_ms()
    command = MqttCommand(device_id="edge-stream-01", action=IntentAction.ON, issued_at_ms=issued, expires_at_ms=issued + 5000)

    agent._on_message(client, None, type("Msg", (), {"payload": json.dumps(command.as_dict()).encode()})())

    assert switch.is_on and led.calls[-1] == "on"
    topics = [(t, p.get("result") or p.get("state"), r) for t, p, _, r in client.published]
    assert topics == [
        ("aiot/v1/home-01/edge-stream-01/ack", "OK", False),
        ("aiot/v1/home-01/edge-stream-01/state", "ON", True),
    ]
    assert published == []  # state는 MQTT 경로에서 이미 발행했으므로 패널이 또 보내지 않는다


def test_publish_state_sends_retained_state():
    switch, _ = make_switch()
    agent = DeviceMqttAgent("home-01", "pi-test", CommandHandler("edge-stream-01", switch), {"host": "localhost"})
    agent.client = FakeClient()
    agent.publish_state()
    assert agent.client.published[0][0] == "aiot/v1/home-01/edge-stream-01/state"
    assert agent.client.published[0][1]["state"] == "OFF" and agent.client.published[0][3] is True


def test_build_relays_creates_stream_switch_with_default_command():
    relays = build_relays({"edge-stream-01": {"type": "edge_stream"}}, mock=True)
    switch = relays["edge-stream-01"]
    assert isinstance(switch, ProcessSwitch) and not switch.is_on
    assert switch.command == [sys.executable, "-m", "edge.main", "--stream", "--source", "synthetic"]
