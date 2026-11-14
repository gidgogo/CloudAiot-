"""데모용 계정·방·기기 데이터를 만든다. 이미 있는 데이터는 건너뛴다.

사용:
    python -m scripts.seed_demo_data                 # 비밀번호를 임의로 만들어 출력
    python -m scripts.seed_demo_data --password 비밀번호
DB는 서버와 같은 DATABASE_URL을 쓴다(없으면 로컬 SQLite).

만드는 데이터
- 계정: admin@demo.local(ADMIN), guardian@demo.local(GUARDIAN), user@demo.local(USER)
- 보호자 guardian-01 ↔ 사용자 user-01 연결
- 방 room-01(안방, 사용자 user-01)
- 기기 fan-01(선풍기, 오른쪽), light-01(조명, 위쪽)
"""

from __future__ import annotations

import argparse
import os
import secrets

from server.config import Settings
from server.db.session import Database, bootstrap
from server.security.authentication import validate_password
from server.services.device_service import DeviceService
from server.services.room_service import RoomService
from server.services.user_service import UserService
from shared.errors import InterfaceError

ACCOUNTS = (
    ("admin-01", "admin@demo.local", "관리자", "ADMIN"),
    ("guardian-01", "guardian@demo.local", "보호자", "GUARDIAN"),
    ("user-01", "user@demo.local", "사용자", "USER"),
)
DEVICES = (
    # 화면 기준 각도: 오른쪽 0°, 아래 +90°, 위 -90°
    {"device_id": "fan-01", "name": "선풍기", "device_type": "FAN", "map_x": 0.8, "map_y": 0.5,
     "min_angle_deg": -25.0, "max_angle_deg": 25.0},
    {"device_id": "light-01", "name": "조명", "device_type": "LIGHT", "map_x": 0.5, "map_y": 0.1,
     "min_angle_deg": -115.0, "max_angle_deg": -65.0},
)


def _skip_existing(action) -> bool:
    try:
        action()
        return True
    except InterfaceError as error:
        if error.code.endswith("ALREADY_EXISTS"):
            return False
        raise


def seed(db: Database, password: str) -> list[str]:
    created: list[str] = []
    with db.session() as session:
        users = UserService(session)
        for user_id, email, name, role in ACCOUNTS:
            if _skip_existing(lambda: users.create(user_id=user_id, email=email, password=password, name=name,
                                                   role=role)):
                created.append(f"user {email}")
        users.link_guardian("guardian-01", "user-01")

        rooms = RoomService(session)
        if _skip_existing(lambda: rooms.create(room_id="room-01", name="안방", resident_user_id="user-01")):
            created.append("room room-01")

        devices = DeviceService(session)
        for spec in DEVICES:
            if _skip_existing(lambda spec=spec: devices.create(room_id="room-01", **spec)):
                created.append(f"device {spec['device_id']}")
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="CloudAIoT 데모 데이터 생성")
    parser.add_argument("--password", default=os.environ.get("DEMO_PASSWORD"),
                        help="세 데모 계정의 비밀번호(8자 이상). 없으면 임의로 만든다.")
    args = parser.parse_args()
    password = args.password or secrets.token_urlsafe(9)
    try:
        validate_password(password)
    except ValueError as error:
        parser.error(str(error))

    settings = Settings.from_env()
    db = Database(settings.database_url)
    bootstrap(db, settings)
    created = seed(db, password)
    db.dispose()

    print("만든 데이터:", ", ".join(created) if created else "없음(이미 있음)")
    if any(item.startswith("user ") for item in created):
        print("데모 계정 비밀번호:", password)
        print("계정:", ", ".join(email for _, email, _, _ in ACCOUNTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
