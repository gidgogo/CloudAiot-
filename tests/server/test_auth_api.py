"""로그인·JWT Cookie·CSRF·Origin·역할 권한 테스트(규격 8장, SAD 6장)."""

import os
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Settings
from server.db.models import Base, ControlEvent, HelpRequestRecord
from server.security import authentication
from server.security.jwt import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, create_access_token
from server.services.control_event_service import DAY_MS, purge_expired
from server.services.device_service import GestureMappingService
from server.services.user_service import UserService
from shared.types import IntentAction

PASSWORD = "password123"
ORIGIN = "http://localhost:5173"
TEST_SETTINGS = Settings(database_url="sqlite://", jwt_secret="test-secret-for-cloudaiot-web-server-0123456789",
                         allowed_origins=(ORIGIN,))


def email_of(user_id: str) -> str:
    return f"{user_id}@example.com"


def login_response(test_client, user_id: str, password: str = PASSWORD):
    return test_client.post("/api/v1/auth/login", json={"email": email_of(user_id), "password": password})


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    monkeypatch.setattr(authentication, "BCRYPT_ROUNDS", 4)
    authentication._dummy_hash.cache_clear()


@pytest.fixture
def settings():
    """테스트마다 바꾸려면 @pytest.mark.parametrize("settings", [Settings(...)])로 덮어쓴다."""
    return TEST_SETTINGS


@pytest.fixture
def app(settings):
    """TEST_DATABASE_URL이 있으면 그 DB(예: PostgreSQL)를 테스트마다 비우고 쓴다."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return create_app(settings)
    application = create_app(replace(settings, database_url=url))
    Base.metadata.drop_all(application.state.db.engine)
    return application


@pytest.fixture
def anon(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(app, anon):
    def _make(user_id: str = "user-01", role: str = "USER") -> str:
        with app.state.db.session() as session:
            user = UserService(session).create(email=email_of(user_id), password=PASSWORD,
                                               name=user_id, role=role, user_id=user_id)
            return user.user_id
    return _make


@pytest.fixture
def login(app, anon):
    def _login(user_id: str) -> TestClient:
        test_client = TestClient(app)
        response = login_response(test_client, user_id)
        assert response.status_code == 200, response.text
        test_client.headers[CSRF_HEADER] = test_client.cookies[CSRF_COOKIE]
        return test_client
    return _login


@pytest.fixture
def client(make_user, login):
    make_user("admin-01", "ADMIN")
    return login("admin-01")


@pytest.fixture
def events(app):
    """발행된 실시간 이벤트를 순서대로 모은다."""
    received = []
    app.state.events.subscribe(received.append)
    return received


@pytest.fixture
def room(client):
    response = client.post("/api/v1/rooms", json={"room_id": "room-01", "name": "안방"})
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture
def device_payload():
    return {
        "device_id": "fan-01",
        "room_id": "room-01",
        "name": "선풍기",
        "device_type": "FAN",
        "map_position": {"x": 0.72, "y": 0.35},
        "pointing_region": {"min_angle_deg": -15.0, "max_angle_deg": 15.0},
        "enabled": True,
    }


@pytest.fixture
def device(client, room, device_payload):
    response = client.post("/api/v1/devices", json=device_payload)
    assert response.status_code == 201
    return response.json()["data"]


def test_login_sets_httponly_jwt_and_readable_csrf_cookie(app, make_user):
    make_user("user-01")
    response = login_response(TestClient(app), "user-01")
    cookies = response.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith(f"{ACCESS_COOKIE}="))
    csrf = next(c for c in cookies if c.startswith(f"{CSRF_COOKIE}="))

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["user"]["user_id"] == "user-01"
    assert "password_hash" not in body["user"]
    assert "token" not in response.text  # JWT는 본문에 넣지 않는다.
    assert "HttpOnly" in access and "SameSite=strict" in access and "Max-Age=1800" in access and "Path=/" in access
    assert "HttpOnly" not in csrf
    assert "Secure" not in access  # 개발 설정(COOKIE_SECURE=false)


def test_login_email_is_case_insensitive(app, make_user):
    make_user("user-01")
    response = TestClient(app).post("/api/v1/auth/login", json={"email": " USER-01@Example.com ", "password": PASSWORD})
    assert response.status_code == 200


def test_wrong_credentials_look_the_same(app, make_user):
    make_user("user-01")
    wrong_password = login_response(TestClient(app), "user-01", "wrong-password")
    unknown_user = login_response(TestClient(app), "nobody")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_repeated_failures_are_rate_limited(app, make_user):
    make_user("user-01")
    test_client = TestClient(app)
    for _ in range(5):
        login_response(test_client, "user-01", "wrong-password")
    locked = login_response(test_client, "user-01")
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_me_and_logout(make_user, login, client):
    make_user("user-01")
    make_user("guardian-01", "GUARDIAN")
    client.post("/api/v1/guardian-links", json={"guardian_id": "guardian-01", "user_id": "user-01"})
    guardian = login("guardian-01")

    me = guardian.get("/api/v1/auth/me").json()["data"]
    assert me["user"]["role"] == "GUARDIAN"
    assert me["linked_user_ids"] == ["user-01"]
    assert me["expires_at_ms"] > time.time() * 1000

    assert guardian.post("/api/v1/auth/logout").status_code == 200
    assert guardian.get("/api/v1/auth/me").status_code == 401


def test_requests_without_login_are_rejected(anon):
    for path in ("/api/v1/rooms", "/api/v1/devices", "/api/v1/help-requests", "/api/v1/control-events",
                 "/api/v1/users", "/api/v1/gesture-mappings", "/api/v1/auth/me"):
        response = anon.get(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert anon.get("/health").status_code == 200


def test_invalid_and_expired_tokens(app, settings, make_user):
    make_user("user-01")
    expired = create_access_token("user-01", settings.jwt_secret, 60, "csrf", now=time.time() - 3600)
    forged = create_access_token("user-01", "another-secret-0123456789-0123456789", 60, "csrf")
    for token in (expired, forged, "not-a-jwt"):
        test_client = TestClient(app)
        test_client.cookies.set(ACCESS_COOKIE, token)
        assert test_client.get("/api/v1/auth/me").status_code == 401


def test_deleted_user_token_stops_working(client, make_user, login):
    make_user("user-01")
    user = login("user-01")
    assert client.delete("/api/v1/users/user-01").status_code == 204
    assert user.get("/api/v1/auth/me").status_code == 401


def test_csrf_token_is_required_for_changes(client):
    without = TestClient(client.app, cookies=client.cookies)
    response = without.post("/api/v1/rooms", json={"name": "안방"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

    mismatched = TestClient(client.app, cookies=client.cookies, headers={CSRF_HEADER: "other-token"})
    assert mismatched.post("/api/v1/rooms", json={"name": "안방"}).status_code == 403

    # 다른 세션의 CSRF Cookie·헤더 쌍으로 바꿔 끼워도 JWT에 묶인 값과 달라 거부된다.
    swapped = TestClient(client.app, cookies=client.cookies, headers={CSRF_HEADER: "attacker"})
    swapped.cookies.set(CSRF_COOKIE, "attacker")
    assert swapped.post("/api/v1/rooms", json={"name": "안방"}).status_code == 403

    assert without.get("/api/v1/rooms").status_code == 200  # 조회는 CSRF 불필요
    assert client.post("/api/v1/rooms", json={"name": "안방"}).status_code == 201


def test_foreign_origin_is_rejected(client):
    assert client.post("/api/v1/rooms", json={"name": "a"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/rooms", json={"name": "b"}, headers={"Origin": ORIGIN}).status_code == 201
    assert client.post("/api/v1/rooms", json={"name": "c"}, headers={"Origin": "http://testserver"}).status_code == 201
    bad_login = client.post("/api/v1/auth/login", json={"email": "admin-01@example.com", "password": PASSWORD},
                            headers={"Origin": "https://evil.example"})
    assert bad_login.status_code == 403


def test_cors_allows_only_configured_origin_with_credentials(anon):
    allowed = anon.options("/api/v1/rooms", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = anon.options("/api/v1/rooms", headers={"Origin": "https://evil.example",
                                                    "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in denied.headers


def test_role_permissions(client, make_user, login, room):
    make_user("user-01")
    make_user("guardian-01", "GUARDIAN")
    for user_id in ("user-01", "guardian-01"):
        other = login(user_id)
        assert other.get("/api/v1/rooms").status_code == 200
        assert other.get("/api/v1/devices").status_code == 200
        assert other.get("/api/v1/control-events").status_code == 200
        assert other.post("/api/v1/rooms", json={"name": "x"}).status_code == 403
        assert other.patch("/api/v1/rooms/room-01", json={"name": "x"}).status_code == 403
        assert other.post("/api/v1/users", json={"email": "a@b.c", "password": PASSWORD, "name": "a",
                                                 "role": "ADMIN"}).status_code == 403
        assert other.patch("/api/v1/gesture-mappings/HELP", json={"enabled": False}).status_code == 403


def test_change_own_password(make_user, login, app):
    make_user("user-01")
    user = login("user-01")
    wrong = user.post("/api/v1/auth/password", json={"current_password": "nope", "new_password": "new-password-1"})
    assert wrong.status_code == 401
    assert user.post("/api/v1/auth/password", json={"current_password": PASSWORD,
                                                    "new_password": "new-password-1"}).status_code == 200
    assert login_response(TestClient(app), "user-01", "new-password-1").status_code == 200


# --- 사용자·보호자 연결·제스처 매핑·보존 기간 테스트.

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
