"""실시간 이벤트 WebSocket 인증과 역할별 전달 범위 테스트(규격 8.5, 9장)."""

import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from dataclasses import replace

from server.security.jwt import ACCESS_COOKIE, create_access_token

from web_testing import ORIGIN, TEST_SETTINGS, login_response

PATH = "/ws/v1/events"


def wait_for_clients(app, count, timeout=2.0):
    deadline = time.monotonic() + timeout
    while app.state.events.client_count < count and time.monotonic() < deadline:
        time.sleep(0.01)
    assert app.state.events.client_count >= count


def close_code(test_client, headers):
    with pytest.raises(WebSocketDisconnect) as closed:
        with test_client.websocket_connect(PATH, headers=headers) as socket:
            socket.receive_json()
    return closed.value.code


def test_rejects_missing_or_foreign_origin(client):
    assert close_code(client, {}) == 4403
    assert close_code(client, {"origin": "https://evil.example"}) == 4403


def test_rejects_missing_or_bad_token(anon, app, settings, make_user):
    make_user("user-01")
    assert close_code(anon, {"origin": ORIGIN}) == 4401
    expired = TestClient(app)
    expired.cookies.set(ACCESS_COOKIE, create_access_token("user-01", settings.jwt_secret, 60, "c", now=time.time() - 120))
    assert close_code(expired, {"origin": ORIGIN}) == 4401
    ghost = TestClient(app)
    ghost.cookies.set(ACCESS_COOKIE, create_access_token("ghost", settings.jwt_secret, 60, "c"))
    assert close_code(ghost, {"origin": ORIGIN}) == 4401


def test_same_origin_connection_receives_events(app, client, make_user):
    make_user("user-01")
    with client.websocket_connect(PATH, headers={"origin": "http://testserver"}) as socket:
        wait_for_clients(app, 1)
        created = client.post("/api/v1/help-requests", json={"user_id": "user-01"}).json()["data"]
        message = socket.receive_json()

    assert message["schema_version"] == "1.0"
    assert message["event_type"] == "help.created"
    assert message["correlation_id"] == created["correlation_id"]
    assert message["data"] == {"request_id": created["request_id"], "user_id": "user-01", "status": "CREATED"}


def test_guardian_receives_only_linked_users_help_events(app, client, make_user, login):
    for user_id in ("user-01", "user-02"):
        make_user(user_id)
    make_user("guardian-01", "GUARDIAN")
    client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"})
    guardian = login("guardian-01")

    with guardian.websocket_connect(PATH, headers={"origin": ORIGIN}) as socket:
        wait_for_clients(app, 1)
        client.post("/api/v1/help-requests", json={"user_id": "user-02"})  # 받지 않아야 한다.
        linked = client.post("/api/v1/help-requests", json={"user_id": "user-01"}).json()["data"]
        message = socket.receive_json()

    assert message["data"]["request_id"] == linked["request_id"]


def test_new_guardian_link_applies_to_open_connection(app, client, make_user, login):
    make_user("user-01")
    make_user("guardian-01", "GUARDIAN")
    guardian = login("guardian-01")

    with guardian.websocket_connect(PATH, headers={"origin": ORIGIN}) as socket:
        wait_for_clients(app, 1)
        client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"})
        created = client.post("/api/v1/help-requests", json={"user_id": "user-01"}).json()["data"]
        message = socket.receive_json()

    assert message["data"]["request_id"] == created["request_id"]


@pytest.mark.parametrize("settings", [replace(TEST_SETTINGS, jwt_expire_seconds=1)])
def test_connection_closes_when_login_expires(anon, make_user):
    make_user("user-01")
    login_response(anon, "user-01")
    started = time.monotonic()
    assert close_code(anon, {"origin": ORIGIN}) == 4401
    assert time.monotonic() - started < 5


def test_role_change_refreshes_linked_guardians_connections(app, client, make_user, login):
    make_user("user-01")
    make_user("guardian-01", "GUARDIAN")
    client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"})
    guardian = login("guardian-01")

    with guardian.websocket_connect(PATH, headers={"origin": ORIGIN}):
        wait_for_clients(app, 1)
        assert client.patch("/api/v1/users/user-01", json={"role": "GUARDIAN"}).status_code == 200
        (subscription,) = app.state.events._subscriptions.values()
        assert subscription.principal.visible_user_ids == frozenset()
