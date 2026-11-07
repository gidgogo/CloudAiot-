"""사용자, 방, 기기, 제어 이력, 도움 요청 모델을 정의한다.

- 시간은 UTC Unix 밀리초 정수(``*_ms``)로 저장한다.
- 영상·손 랜드마크는 저장하지 않는다(NFR-03).
- 웹 배치도 좌표(map_x, map_y)와 포인팅 판정 범위(min/max_angle_deg)는 목적이 달라 분리한다.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.types import DeviceConnectionStatus, DeviceState, StrEnum


class CommandStatus(StrEnum):
    """제어 명령 처리 상태(control_events.status)."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16))  # USER | GUARDIAN | ADMIN
    created_at_ms: Mapped[int] = mapped_column(BigInteger)


class GuardianLink(Base):
    """보호자(GUARDIAN)와 사용자(USER)의 연결 관계."""

    __tablename__ = "guardian_links"

    guardian_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    created_at_ms: Mapped[int] = mapped_column(BigInteger)


class Room(Base):
    __tablename__ = "rooms"

    room_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    # 이 방에서 생활하는 사용자(USER). HELP 제스처를 누구의 요청으로 기록할지 정한다.
    resident_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at_ms: Mapped[int] = mapped_column(BigInteger)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger)


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.room_id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    device_type: Mapped[str] = mapped_column(String(32))
    map_x: Mapped[float] = mapped_column(Float)
    map_y: Mapped[float] = mapped_column(Float)
    min_angle_deg: Mapped[float] = mapped_column(Float)
    max_angle_deg: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    state: Mapped[str] = mapped_column(String(16), default=DeviceState.UNKNOWN.value)
    connection_status: Mapped[str] = mapped_column(
        String(16), default=DeviceConnectionStatus.OFFLINE.value
    )
    state_updated_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    created_at_ms: Mapped[int] = mapped_column(BigInteger)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger)


class ControlEvent(Base):
    """MQTT 명령 1건과 그 결과. NFR-01 지연 측정의 기준 데이터."""

    __tablename__ = "control_events"
    __table_args__ = (Index("ix_control_events_published", "command_published_at_ms"),)

    command_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.device_id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(8))  # ON | OFF
    source: Mapped[str] = mapped_column(String(16))  # GESTURE | WEB | SYSTEM
    status: Mapped[str] = mapped_column(String(16))  # CommandStatus
    result: Mapped[str | None] = mapped_column(
        String(16)
    )  # ACK result: OK | ERROR | EXPIRED | DUPLICATE
    error_code: Mapped[str | None] = mapped_column(String(64))
    gesture_confirmed_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    command_published_at_ms: Mapped[int] = mapped_column(BigInteger)
    ack_received_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)


class HelpRequestRecord(Base):
    __tablename__ = "help_requests"
    __table_args__ = (Index("ix_help_requests_created", "created_at_ms"),)

    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(16))  # GESTURE | WEB
    status: Mapped[str] = mapped_column(
        String(16), index=True
    )  # CREATED | CONFIRMED | COMPLETED
    created_at_ms: Mapped[int] = mapped_column(BigInteger)
    confirmed_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    confirmed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    completed_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    completed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )


class GestureMapping(Base):
    """제스처와 명령의 연결(SAD 4.1 제스처·명령 매핑 모듈)."""

    __tablename__ = "gesture_mappings"

    gesture: Mapped[str] = mapped_column(
        String(16), primary_key=True
    )  # THUMB_UP | THUMB_DOWN | HELP
    action: Mapped[str] = mapped_column(String(8))  # ON | OFF | HELP
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger)
