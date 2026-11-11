"""로그인·JWT Cookie·CSRF·Origin·역할 권한 테스트(규격 8장, SAD 6장)."""

import time

from fastapi.testclient import TestClient

from server.security.jwt import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, create_access_token

from web_testing import ORIGIN, PASSWORD, login_response


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
