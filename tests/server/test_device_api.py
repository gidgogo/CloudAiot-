"""방·기기·방향 영역 API 테스트."""

from server.intent.device_matcher import match_device
from server.services.device_service import DeviceService


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
