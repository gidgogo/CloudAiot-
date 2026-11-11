"""서버 시작 시 필요한 기본 데이터를 준비한다.

- 없는 테이블 생성
- 기본 제스처·명령 매핑(엄지 올림=ON, 엄지 내림=OFF, HELP=도움 요청)
- 사용자가 한 명도 없고 ADMIN_EMAIL·ADMIN_PASSWORD가 있으면 최초 관리자 생성
"""

from __future__ import annotations

import logging

from server.db.session import Database
from server.services.gesture_mapping_service import GestureMappingService
from server.services.user_service import UserService
from server.settings import Settings
from shared.types import UserRole

log = logging.getLogger(__name__)


def bootstrap(db: Database, settings: Settings) -> None:
    db.create_all()
    with db.session() as session:
        GestureMappingService(session).ensure_defaults()
        users = UserService(session)
        if users.count() == 0:
            if settings.admin_email and settings.admin_password:
                users.create(
                    email=settings.admin_email,
                    password=settings.admin_password,
                    name=settings.admin_name,
                    role=UserRole.ADMIN,
                )
                log.info("최초 관리자 계정을 만들었습니다: %s", settings.admin_email)
            else:
                log.warning(
                    "사용자가 없습니다. ADMIN_EMAIL·ADMIN_PASSWORD를 설정하거나 "
                    "python -m scripts.seed_demo_data 로 계정을 만드세요."
                )
