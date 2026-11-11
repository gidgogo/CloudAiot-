"""웹·응용 서버 테스트 공용 상수와 도우미."""

from server.settings import Settings

PASSWORD = "password123"
ORIGIN = "http://localhost:5173"
TEST_SETTINGS = Settings(
    database_url="sqlite://",
    jwt_secret="test-secret-for-cloudaiot-web-server-0123456789",
    allowed_origins=(ORIGIN,),
)


def email_of(user_id: str) -> str:
    return f"{user_id}@example.com"


def login_response(test_client, user_id: str, password: str = PASSWORD):
    return test_client.post(
        "/api/v1/auth/login", json={"email": email_of(user_id), "password": password}
    )
