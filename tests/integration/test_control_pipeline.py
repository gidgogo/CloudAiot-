"""Vision→Intent 후속 처리와 MQTT→DB→웹 이벤트 통합 테스트."""

import json
from types import SimpleNamespace

from server.db.models import ControlEvent, Device
from server.integration_pipeline import FrameSessionProcessor, IntentDispatcher
from server.iot.mqtt_client import MqttBridge
from server.vision.hand_detector import HandDetection
from shared.mqtt_topics import ack_topic, status_topic
from shared.types import (
    FrameMetadata,
    GestureResult,
    GestureType,
    Handedness,
    IntentAction,
    IntentResult,
    IntentStatus,
    PointingVector,
)
from tests.server.test_auth_api import (  # noqa: F401
    anon,
    app,
    client,
    device,
    device_payload,
    events,
    fast_bcrypt,
    login,
    login_response,
    make_user,
    room,
    settings,
)


class SequenceGesturePipeline:
    def __init__(self, results):
        self.results = iter(results)
        self.closed = False

    def process_jpeg(self, _jpeg, _metadata):
        return next(self.results)

    def close(self):
        self.closed = True


class CapturingPublisher:
    def __init__(self):
        self.intents = []

    def publish_intent(self, intent):
        self.intents.append(intent)


def gesture(kind, at_ms, vector=None):
    return GestureResult(
        frame_id=f"frame-{at_ms}", correlation_id="corr-1", handedness=Handedness.RIGHT,
        gesture=kind, pointing_vector=vector, stable_frames=6, hold_time_ms=500,
        detected_at_ms=at_ms,
    )


def test_pointing_then_thumb_publishes_selected_confirmed_and_mqtt_intent(app, device, events):
    publisher = CapturingPublisher()
    dispatcher = IntentDispatcher(app.state.db, app.state.events, publisher)
    pipeline = SequenceGesturePipeline([
        gesture(GestureType.POINTING, 1_000, PointingVector(0.5, 0.5, 0.8, 0.5)),
        gesture(GestureType.THUMB_UP, 1_500),
    ])
    processor = FrameSessionProcessor(app.state.db, dispatcher, gesture_pipeline=pipeline)
    metadata = FrameMetadata(width=640, height=480, captured_at_ms=1_000)

    pending = processor.process(b"jpeg", metadata)[1]
    confirmed = processor.process(b"jpeg", metadata)[1]

    assert pending.status is IntentStatus.PENDING and pending.target_device_id == "fan-01"
    assert confirmed.status is IntentStatus.CONFIRMED and confirmed.action is IntentAction.ON
    assert publisher.intents == [confirmed]
    assert [event.event_type for event in events] == ["device.selected", "gesture.confirmed"]
    assert events[0].data == {"device_id": "fan-01", "device_name": "선풍기"}


def test_confirmed_help_creates_help_request_and_web_events(app, client, make_user, events):
    make_user("user-01")
    client.post("/api/v1/rooms", json={"room_id": "resident-room", "name": "거실", "resident_user_id": "user-01"})
    dispatcher = IntentDispatcher(app.state.db, app.state.events, None)

    dispatcher.dispatch(IntentResult(
        correlation_id="corr-help", action=IntentAction.HELP,
        status=IntentStatus.CONFIRMED, confirmed_at_ms=1_000,
    ))

    response = client.get("/api/v1/help-requests").json()["data"]
    assert response[0]["correlation_id"] == "corr-help"
    assert [event.event_type for event in events] == ["gesture.confirmed", "help.created"]


class FakeMqttClient:
    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.on_connect = None
        self.on_message = None

    def publish(self, topic, payload, qos, retain):
        self.published.append((topic, json.loads(payload), qos, retain))
        return SimpleNamespace(rc=0)

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))

    def connect(self, host, port):
        pass

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass


def message(topic, payload):
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())


def test_mqtt_bridge_records_command_ack_state_status_and_events(app, device, events):
    client = FakeMqttClient()
    bridge = MqttBridge(app.state.db, app.state.events, host="mqtt", home_id="home-01", client=client)
    bridge.publish_intent(IntentResult(
        correlation_id="corr-command", target_device_id="fan-01", action=IntentAction.ON,
        status=IntentStatus.CONFIRMED, confirmed_at_ms=1_000,
    ))
    topic, command, qos, retain = client.published[0]
    bridge._on_message(None, None, message(ack_topic("home-01", "fan-01"), {
        "schema_version": "1.0", "command_id": command["command_id"],
        "correlation_id": "corr-command", "device_id": "fan-01", "result": "OK",
        "state": "ON", "processed_at_ms": command["issued_at_ms"] + 10, "error_code": None,
    }))
    bridge._on_message(None, None, message(status_topic("home-01", "fan-01"), {
        "schema_version": "1.0", "device_id": "fan-01", "status": "ONLINE", "timestamp_ms": 2_000,
    }))

    with app.state.db.session() as session:
        record = session.get(ControlEvent, command["command_id"])
        saved_device = session.get(Device, "fan-01")
        assert record.status == "COMPLETED" and record.result == "OK"
        assert saved_device.state == "ON" and saved_device.connection_status == "ONLINE"
    assert topic == "aiot/v1/home-01/fan-01/cmd" and qos == 1 and retain is False
    assert [event.event_type for event in events] == [
        "command.created", "device.state_changed", "command.completed", "device.state_changed"
    ]
    bridge.close()

