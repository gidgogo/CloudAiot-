"""방·기기·방향 영역 API 테스트."""

import pytest

from server.db.models import main
from server.intent.device_matcher import match_device
from server.services.control_event_service import ControlEventService
from server.services.device_service import DeviceService
from shared.errors import InterfaceError
from shared.types import AckResult, DeviceState, IntentAction, MqttAck, MqttCommand
from tests.server.test_auth_api import (  # noqa: F401 (pytest 공통 fixture)
    ORIGIN,
    PASSWORD,
    TEST_SETTINGS,
    anon,
    app,
    client,
    device,
    device_payload,
    email_of,
    events,
    fast_bcrypt,
    login,
    login_response,
    make_user,
    room,
    settings,
)


def error_code(response):
    body = response.json()
    assert body["success"] is False
    return body["error"]["code"]


# 방 ---------------------------------------------------------------------

def test_room_crud(client):
    created = client.post("/api/v1/rooms", json={"room_id": "room-01", "name": "안방", "description": "1층"})
    assert created.status_code == 201
    assert created.json()["data"]["name"] == "안방"

    assert [room["room_id"] for room in client.get("/api/v1/rooms").json()["data"]] == ["room-01"]

    updated = client.patch("/api/v1/rooms/room-01", json={"description": None})
    assert updated.status_code == 200
    assert updated.json()["data"]["description"] is None

    assert client.delete("/api/v1/rooms/room-01").status_code == 204
    assert error_code(client.get("/api/v1/rooms/room-01")) == "ROOM_NOT_FOUND"


def test_room_id_is_generated_when_missing(client):
    data = client.post("/api/v1/rooms", json={"name": "거실"}).json()["data"]
    assert len(data["room_id"]) == 36


def test_room_validation(client, room):
    assert error_code(client.post("/api/v1/rooms", json={"room_id": "room-01", "name": "중복"})) == "ROOM_ALREADY_EXISTS"
    assert error_code(client.post("/api/v1/rooms", json={"name": ""})) == "INVALID_SCHEMA"
    assert error_code(client.patch("/api/v1/rooms/room-01", json={"name": None})) == "INVALID_SCHEMA"
    assert error_code(client.patch("/api/v1/rooms/room-01", json={})) == "INVALID_SCHEMA"


def test_room_with_devices_cannot_be_deleted(client, device):
    response = client.delete("/api/v1/rooms/room-01")
    assert response.status_code == 409
    assert error_code(response) == "ROOM_NOT_EMPTY"


# 기기 -------------------------------------------------------------------

def test_create_device_matches_interface_shape(device, device_payload):
    for key, value in device_payload.items():
        assert device[key] == value
    assert device["state"] == "UNKNOWN"
    assert device["connection_status"] == "OFFLINE"


def test_list_and_filter_devices(client, device, device_payload):
    client.post("/api/v1/rooms", json={"room_id": "room-02", "name": "거실"})
    client.post("/api/v1/devices", json={**device_payload, "device_id": "light-01", "room_id": "room-02",
                                         "device_type": "LIGHT", "enabled": False,
                                         "pointing_region": {"min_angle_deg": 30, "max_angle_deg": 60}})

    def ids(**params):
        return [item["device_id"] for item in client.get("/api/v1/devices", params=params).json()["data"]]

    assert ids() == ["fan-01", "light-01"]
    assert ids(room_id="room-02") == ["light-01"]
    assert ids(enabled="true") == ["fan-01"]


def test_patch_device_updates_only_sent_fields(client, device):
    response = client.patch("/api/v1/devices/fan-01", json={"pointing_region": {"min_angle_deg": 10, "max_angle_deg": 40}})
    data = response.json()["data"]
    assert response.status_code == 200
    assert data["pointing_region"] == {"min_angle_deg": 10, "max_angle_deg": 40}
    assert data["map_position"] == device["map_position"]
    assert data["name"] == "선풍기"


def test_device_validation_errors(client, room, device_payload):
    cases = [
        {**device_payload, "pointing_region": {"min_angle_deg": 20, "max_angle_deg": 10}},
        {**device_payload, "pointing_region": {"min_angle_deg": -200, "max_angle_deg": 10}},
        {**device_payload, "map_position": {"x": 1.2, "y": 0.5}},
        {**device_payload, "device_type": "fan"},
        {**device_payload, "unknown_field": 1},
    ]
    for payload in cases:
        response = client.post("/api/v1/devices", json=payload)
        assert response.status_code == 422, payload
        assert error_code(response) == "INVALID_SCHEMA"


def test_device_reference_errors(client, device, device_payload):
    assert error_code(client.post("/api/v1/devices", json=device_payload)) == "DEVICE_ALREADY_EXISTS"
    assert error_code(client.post("/api/v1/devices", json={**device_payload, "device_id": "x", "room_id": "nope"})) == "ROOM_NOT_FOUND"
    assert error_code(client.patch("/api/v1/devices/fan-01", json={"room_id": "nope"})) == "ROOM_NOT_FOUND"
    assert error_code(client.patch("/api/v1/devices/fan-01", json={"enabled": None})) == "INVALID_SCHEMA"
    missing = client.get("/api/v1/devices/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "요청한 기기를 찾을 수 없습니다."


def test_delete_device(client, device):
    assert client.delete("/api/v1/devices/fan-01").status_code == 204
    assert error_code(client.get("/api/v1/devices/fan-01")) == "DEVICE_NOT_FOUND"


def test_unknown_route_uses_error_format(client):
    response = client.get("/api/v1/nothing")
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


# 상태·포인팅 연동 -------------------------------------------------------

def test_state_change_event_only_when_changed(app, device, events):
    with app.state.db.session() as session:
        service = DeviceService(session, app.state.events)
        service.update_state("fan-01", "ON")
        service.update_state("fan-01", "ON")
        service.update_connection_status("fan-01", "ONLINE")

    assert [event.event_type for event in events] == ["device.state_changed", "device.state_changed"]
    assert events[-1].data["state"] == "ON"
    assert events[-1].data["connection_status"] == "ONLINE"


def test_pointing_regions_feed_intent_matcher(app, client, device, device_payload):
    client.post("/api/v1/devices", json={**device_payload, "device_id": "light-01",
                                         "pointing_region": {"min_angle_deg": 30, "max_angle_deg": 60}})
    client.post("/api/v1/devices", json={**device_payload, "device_id": "tv-01", "enabled": False,
                                         "pointing_region": {"min_angle_deg": 90, "max_angle_deg": 120}})
    with app.state.db.session() as session:
        regions = DeviceService(session).pointing_regions()

    assert match_device(0, regions) == "fan-01"
    assert match_device(45, regions) == "light-01"
    assert match_device(100, regions) is None  # 비활성 기기는 제외


# --- 기기 제어 이력(ControlEventService)과 조회 API 테스트.

@pytest.fixture
def service(app, device):
    with app.state.db.session() as session:
        yield ControlEventService(session, app.state.events)


def command(command_id="cmd-1", issued=1_000, action=IntentAction.ON):
    return MqttCommand(command_id=command_id, correlation_id=f"corr-{command_id}", device_id="fan-01",
                       action=action, issued_at_ms=issued, expires_at_ms=issued + 5_000)


def ack(command_id="cmd-1", result=AckResult.OK, state=DeviceState.ON, error_code=None):
    return MqttAck(command_id=command_id, correlation_id=f"corr-{command_id}", device_id="fan-01",
                   result=result, state=state, processed_at_ms=1_200, error_code=error_code)


def test_successful_command_records_latency_and_device_state(client, service, events):
    service.record_command(command(), gesture_confirmed_at_ms=900)
    record = service.record_ack(ack(), received_at_ms=1_250)

    assert record.status == "COMPLETED"
    assert record.latency_ms == 350  # 제스처 확정(900) → ACK 수신(1250)
    assert client.get("/api/v1/devices/fan-01").json()["data"]["state"] == "ON"
    assert [event.event_type for event in events] == ["command.created", "device.state_changed", "command.completed"]
    assert events[0].correlation_id == "corr-cmd-1"


def test_failed_acks(service):
    service.record_command(command("cmd-err"))
    service.record_command(command("cmd-exp"))
    assert service.record_ack(ack("cmd-err", AckResult.ERROR, error_code="RELAY_FAULT")).error_code == "RELAY_FAULT"
    expired = service.record_ack(ack("cmd-exp", AckResult.EXPIRED))
    assert (expired.status, expired.error_code) == ("FAILED", "COMMAND_EXPIRED")


def test_timeout_then_late_ack_is_ignored(service, events):
    service.record_command(command())
    assert service.mark_timeout("cmd-1").error_code == "ACK_TIMEOUT"
    late = service.record_ack(ack())
    assert late.status == "FAILED"
    assert late.ack_received_at_ms is None
    assert [event.event_type for event in events] == ["command.created", "command.failed"]


def test_command_errors(service):
    service.record_command(command())
    with pytest.raises(InterfaceError) as duplicate:
        service.record_command(command())
    assert duplicate.value.code == "COMMAND_ALREADY_EXISTS"

    other = command("cmd-2")
    other.device_id = "nope"
    with pytest.raises(InterfaceError) as missing:
        service.record_command(other)
    assert missing.value.code == "DEVICE_NOT_FOUND"


def test_list_is_newest_first_with_pagination(client, service):
    for index in range(3):
        service.record_command(command(f"cmd-{index}", issued=1_000 + index))

    body = client.get("/api/v1/control-events", params={"limit": 2}).json()
    assert [item["command_id"] for item in body["data"]] == ["cmd-2", "cmd-1"]
    assert body["meta"] == {"total": 3, "limit": 2, "offset": 0}
    assert client.get("/api/v1/control-events", params={"device_id": "other"}).json()["meta"]["total"] == 0
    assert client.get("/api/v1/control-events/cmd-0").json()["data"]["status"] == "PENDING"
    assert client.get("/api/v1/control-events", params={"limit": 0}).status_code == 422


# --- initial_schema.sql이 모델과 일치하는지 확인한다.

def test_initial_schema_is_up_to_date():
    assert main(["--check"]) == 0, "모델이 바뀌었습니다. python -m server.db.models 을 실행하세요."
