"""도움 요청 API·권한·HELP 제스처 연동 테스트."""

import pytest

from server.services.help_service import HelpService
from shared.errors import InterfaceError
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


@pytest.fixture
def people(make_user, client):
    """user-01(보호자 guardian-01과 연결), user-02(연결 없음), guardian-01."""
    make_user("user-01")
    make_user("user-02")
    make_user("guardian-01", "GUARDIAN")
    assert client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"}).status_code == 201


def create_as_admin(client, user_id):
    response = client.post("/api/v1/help-requests", json={"user_id": user_id})
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_user_creates_own_help_request(people, login, events):
    user = login("user-01")
    response = user.post("/api/v1/help-requests", json={})
    data = response.json()["data"]

    assert response.status_code == 201
    assert (data["user_id"], data["source"], data["status"]) == ("user-01", "WEB", "CREATED")
    assert data["correlation_id"] == data["request_id"]
    assert [event.event_type for event in events] == ["help.created"]
    assert events[0].data == {"request_id": data["request_id"], "user_id": "user-01", "status": "CREATED"}
    assert user.post("/api/v1/help-requests", json={"user_id": "user-02"}).status_code == 403


def test_create_rules_by_role(people, client, login):
    assert client.post("/api/v1/help-requests", json={}).json()["error"]["code"] == "INVALID_SCHEMA"
    assert client.post("/api/v1/help-requests", json={"user_id": "ghost"}).json()["error"]["code"] == "USER_NOT_FOUND"
    assert client.post("/api/v1/help-requests", json={"user_id": "guardian-01"}).json()["error"]["code"] == "INVALID_USER_ROLE"
    assert login("guardian-01").post("/api/v1/help-requests", json={"user_id": "user-01"}).status_code == 403


def test_visibility_by_role(people, client, login):
    mine = create_as_admin(client, "user-01")["request_id"]
    other = create_as_admin(client, "user-02")["request_id"]

    def ids(test_client):
        return {item["request_id"] for item in test_client.get("/api/v1/help-requests").json()["data"]}

    assert ids(client) == {mine, other}
    assert ids(login("guardian-01")) == {mine}
    assert ids(login("user-02")) == {other}
    assert login("guardian-01").get(f"/api/v1/help-requests/{other}").status_code == 403


def test_status_moves_forward_only_by_guardian(people, client, login, events):
    request_id = create_as_admin(client, "user-01")["request_id"]
    url = f"/api/v1/help-requests/{request_id}"
    guardian = login("guardian-01")

    skipped = guardian.patch(url, json={"status": "COMPLETED"})
    assert skipped.status_code == 409
    assert skipped.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    confirmed = guardian.patch(url, json={"status": "CONFIRMED"}).json()["data"]
    assert (confirmed["status"], confirmed["confirmed_by"]) == ("CONFIRMED", "guardian-01")

    completed = guardian.patch(url, json={"status": "COMPLETED"}).json()["data"]
    assert completed["status"] == "COMPLETED"
    assert completed["completed_at_ms"] >= completed["confirmed_at_ms"]

    assert guardian.patch(url, json={"status": "CONFIRMED"}).status_code == 409
    assert guardian.patch(url, json={"status": "CREATED"}).status_code == 422
    assert [event.event_type for event in events] == ["help.created", "help.updated", "help.updated"]


def test_only_linked_guardian_or_admin_can_change_status(people, client, login, make_user):
    request_id = create_as_admin(client, "user-01")["request_id"]
    url = f"/api/v1/help-requests/{request_id}"
    make_user("guardian-02", "GUARDIAN")

    assert login("user-01").patch(url, json={"status": "CONFIRMED"}).status_code == 403
    assert login("guardian-02").patch(url, json={"status": "CONFIRMED"}).status_code == 403
    assert client.patch(url, json={"status": "CONFIRMED"}).json()["data"]["confirmed_by"] == "admin-01"


def test_list_filters_by_status(people, client):
    first = create_as_admin(client, "user-01")["request_id"]
    create_as_admin(client, "user-01")
    client.patch(f"/api/v1/help-requests/{first}", json={"status": "CONFIRMED"})

    body = client.get("/api/v1/help-requests", params={"status": "CREATED"}).json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["status"] == "CREATED"
    assert client.get("/api/v1/help-requests").json()["meta"]["total"] == 2
    assert client.get("/api/v1/help-requests", params={"status": "DONE"}).status_code == 422


# HELP 제스처 --------------------------------------------------------------

def test_gesture_help_uses_room_resident(app, people, client):
    client.post("/api/v1/rooms", json={"room_id": "room-01", "name": "안방", "resident_user_id": "user-01"})
    client.post("/api/v1/rooms", json={"room_id": "room-02", "name": "거실"})
    with app.state.db.session() as session:
        service = HelpService(session)
        by_room = service.create_from_gesture("frame-1", room_id="room-01")
        only_resident = service.create_from_gesture("frame-2")
        with pytest.raises(InterfaceError) as no_resident:
            service.create_from_gesture("frame-3", room_id="room-02")

    assert (by_room.user_id, by_room.source, by_room.correlation_id) == ("user-01", "GESTURE", "frame-1")
    assert only_resident.user_id == "user-01"
    assert no_resident.value.code == "HELP_USER_UNKNOWN"


def test_gesture_help_needs_single_resident(app, people, client):
    client.post("/api/v1/rooms", json={"room_id": "room-01", "name": "안방", "resident_user_id": "user-01"})
    client.post("/api/v1/rooms", json={"room_id": "room-02", "name": "작은방", "resident_user_id": "user-02"})
    with app.state.db.session() as session, pytest.raises(InterfaceError) as ambiguous:
        HelpService(session).create_from_gesture("frame-1")
    assert ambiguous.value.code == "HELP_USER_UNKNOWN"


def test_room_resident_must_be_user(people, client):
    response = client.post("/api/v1/rooms", json={"name": "안방", "resident_user_id": "guardian-01"})
    assert response.json()["error"]["code"] == "INVALID_USER_ROLE"
