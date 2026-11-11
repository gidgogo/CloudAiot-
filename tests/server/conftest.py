"""웹·응용 서버 테스트 공통 준비. 테스트마다 메모리 SQLite로 새 앱을 만든다.

- ``client``: ADMIN으로 로그인한 클라이언트(CSRF 헤더 포함)
- ``login(email)``: 다른 사용자로 로그인한 새 클라이언트
- ``anon``: 로그인하지 않은 클라이언트(앱 시작·종료를 담당)
"""

import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.db.models import Base
from server.security import authentication
from server.security.jwt import CSRF_COOKIE, CSRF_HEADER
from server.services.user_service import UserService
from web_testing import PASSWORD, TEST_SETTINGS, email_of, login_response


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
            user = UserService(session).create(
                email=email_of(user_id),
                password=PASSWORD,
                name=user_id,
                role=role,
                user_id=user_id,
            )
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
