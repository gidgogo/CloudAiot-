"""사용자·보호자 연결·제스처 매핑·보존 기간 테스트."""

from dataclasses import replace

import pytest

from server.db.models import ControlEvent, HelpRequestRecord
from server.services.gesture_mapping_service import GestureMappingService
from server.services.retention_service import DAY_MS, purge_expired
from shared.types import IntentAction

from web_testing import PASSWORD, TEST_SETTINGS


def new_user(user_id, role="USER"):
    return {"user_id": user_id, "email": f"{user_id}@example.com", "password": PASSWORD, "name": user_id, "role": role}


# 사용자 -------------------------------------------------------------------

def test_admin_manages_users(client):
    created = client.post("/api/v1/users", json=new_user("user-01"))
    assert created.status_code == 201
    assert "password" not in created.json()["data"] and "password_hash" not in created.json()["data"]

    assert client.post("/api/v1/users", json=new_user("user-01")).json()["error"]["code"] == "USER_ALREADY_EXISTS"
    assert client.post("/api/v1/users", json={**new_user("x"), "password": "short"}).status_code == 422
    assert client.post("/api/v1/users", json={**new_user("y"), "email": "no-at-sign"}).status_code == 422

    updated = client.patch("/api/v1/users/user-01", json={"name": "홍길동"}).json()["data"]
    assert updated["name"] == "홍길동"
    roles = [user["role"] for user in client.get("/api/v1/users").json()["data"]]
    assert sorted(roles) == ["ADMIN", "USER"]
    assert [u["user_id"] for u in client.get("/api/v1/users", params={"role": "USER"}).json()["data"]] == ["user-01"]


def test_admin_cannot_demote_or_delete_self(client):
    assert client.patch("/api/v1/users/admin-01", json={"role": "USER"}).json()["error"]["code"] == "CANNOT_MODIFY_SELF"
    assert client.delete("/api/v1/users/admin-01").json()["error"]["code"] == "CANNOT_MODIFY_SELF"


def test_users_see_only_themselves_or_linked_users(client, make_user, login):
    make_user("user-01")
    make_user("user-02")
    make_user("guardian-01", "GUARDIAN")
    client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"})

    guardian = login("guardian-01")
    assert {u["user_id"] for u in guardian.get("/api/v1/users").json()["data"]} == {"guardian-01", "user-01"}
    assert guardian.get("/api/v1/users/user-01").status_code == 200
    assert guardian.get("/api/v1/users/user-02").status_code == 403

    user = login("user-02")
    assert [u["user_id"] for u in user.get("/api/v1/users").json()["data"]] == ["user-02"]
    assert user.get("/api/v1/guardian-links").status_code == 403


def test_guardian_links(client, make_user):
    make_user("user-01")
    make_user("guardian-01", "GUARDIAN")

    assert client.post("/api/v1/guardian-links", json={"guardian_id": "user-01", "user_id": "guardian-01"}).json()["error"]["code"] == "INVALID_USER_ROLE"
    assert client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"}).status_code == 201
    assert client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"}).status_code == 201
    assert len(client.get("/api/v1/guardian-links", params={"guardian_id": "guardian-01"}).json()["data"]) == 1

    assert client.delete("/api/v1/guardian-links/guardian-01/user-01").status_code == 204
    assert client.get("/api/v1/guardian-links").json()["data"] == []


def test_role_change_drops_guardian_links(client, make_user):
    make_user("user-01")
    make_user("guardian-01", "GUARDIAN")
    client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"})
    client.patch("/api/v1/users/guardian-01", json={"role": "USER"})
    assert client.get("/api/v1/guardian-links").json()["data"] == []


# 제스처 매핑 ----------------------------------------------------------------

def test_default_gesture_mappings(client):
    mappings = {m["gesture"]: (m["action"], m["enabled"]) for m in client.get("/api/v1/gesture-mappings").json()["data"]}
    assert mappings == {"THUMB_UP": ("ON", True), "THUMB_DOWN": ("OFF", True), "HELP": ("HELP", True)}


def test_update_gesture_mapping(app, client):
    conflict = client.patch("/api/v1/gesture-mappings/THUMB_UP", json={"action": "OFF"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MAPPING_CONFLICT"

    assert client.patch("/api/v1/gesture-mappings/HELP", json={"enabled": False}).json()["data"]["enabled"] is False
    assert client.patch("/api/v1/gesture-mappings/POINTING", json={"enabled": False}).status_code == 404
    assert client.patch("/api/v1/gesture-mappings/HELP", json={"action": "DANCE"}).status_code == 422

    with app.state.db.session() as session:
        service = GestureMappingService(session)
        assert service.action_for("THUMB_UP") == IntentAction.ON
        assert service.action_for("HELP") is None


# 보존 기간 ------------------------------------------------------------------

def test_purge_keeps_pending_and_unresolved(app, client, make_user, device):
    make_user("user-01")
    now = 100 * DAY_MS
    old = now - 31 * DAY_MS
    with app.state.db.session() as session:
        for command_id, status in (("old-done", "COMPLETED"), ("old-pending", "PENDING")):
            session.add(ControlEvent(command_id=command_id, correlation_id=command_id, device_id="fan-01",
                                     action="ON", source="WEB", status=status, command_published_at_ms=old))
        session.add(ControlEvent(command_id="new-done", correlation_id="n", device_id="fan-01", action="ON",
                                 source="WEB", status="COMPLETED", command_published_at_ms=now))
        for request_id, status in (("old-completed", "COMPLETED"), ("old-open", "CREATED")):
            session.add(HelpRequestRecord(request_id=request_id, correlation_id=request_id, user_id="user-01",
                                          source="WEB", status=status, created_at_ms=old))
        session.commit()

        result = purge_expired(session, control_event_days=30, help_request_days=30, now=now)
        remaining_events = {e.command_id for e in session.query(ControlEvent)}
        remaining_help = {h.request_id for h in session.query(HelpRequestRecord)}

    assert (result.control_events, result.help_requests) == (1, 1)
    assert remaining_events == {"old-pending", "new-done"}
    assert remaining_help == {"old-open"}


@pytest.mark.parametrize("settings", [replace(TEST_SETTINGS, admin_email="boss@example.com", admin_password=PASSWORD)])
def test_bootstrap_creates_first_admin_from_settings(anon):
    response = anon.post("/api/v1/auth/login", json={"email": "boss@example.com", "password": PASSWORD})
    assert response.json()["data"]["user"]["role"] == "ADMIN"
