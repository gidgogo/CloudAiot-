"""[임시] 실시간 동작 확인 API 테스트. debug_live를 지울 때 이 파일도 지운다. DEBUG-LIVE"""

import pytest

from server.api import debug_live
from server.app import create_app
from shared.types import FrameMetadata, GestureResult, GestureType
from tests.server.test_auth_api import TEST_SETTINGS, fast_bcrypt, login_response, make_user  # noqa: F401
from fastapi.testclient import TestClient


def admin_client(app):
    from server.services.user_service import UserService
    from tests.server.test_auth_api import PASSWORD, email_of
    with app.state.db.session() as session:
        UserService(session).create(email=email_of("admin-01"), password=PASSWORD, name="a", role="ADMIN", user_id="admin-01")
    client = TestClient(app)
    assert login_response(client, "admin-01").status_code == 200
    return client


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DEBUG_LIVE", raising=False)
    app = create_app(TEST_SETTINGS)
    with TestClient(app):
        client = admin_client(app)
        assert client.get("/api/v1/debug/live/state").status_code == 404
        assert app.state.debug_live is None


def test_enabled_reports_latest_result(monkeypatch):
    monkeypatch.setenv("DEBUG_LIVE", "1")
    app = create_app(TEST_SETTINGS)
    with TestClient(app):
        client = admin_client(app)
        debug_live.record(app, b"\xff\xd8x", FrameMetadata(edge_id="pi"), GestureResult(gesture=GestureType.HELP), None, 12.0)
        data = client.get("/api/v1/debug/live/state").json()["data"]
        assert data["gesture"] == "HELP" and data["edge_id"] == "pi" and data["ai_ms"] == 12.0
        assert TestClient(app).get("/api/v1/debug/live/state").status_code == 401  # 로그인 필요
