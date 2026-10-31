"""CloudAIoT common interface v1 data types."""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from time import time
from typing import Any
from uuid import uuid4
from shared.constants import SCHEMA_VERSION

def now_ms() -> int: return int(time() * 1000)
def new_id() -> str: return str(uuid4())

class StrEnum(str, Enum): pass
class Action(StrEnum):
    ON = "on"
    OFF = "off"
    CALL_CAREGIVER = "call_caregiver"
class GestureType(StrEnum):
    POINTING = "POINTING"
    THUMB_UP = "THUMB_UP"
    THUMB_DOWN = "THUMB_DOWN"
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"
class Handedness(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UNKNOWN = "UNKNOWN"
class IntentAction(StrEnum):
    ON = "ON"
    OFF = "OFF"
    HELP = "HELP"
class IntentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
class CommandSource(StrEnum):
    GESTURE = "GESTURE"
    WEB = "WEB"
    SYSTEM = "SYSTEM"
class AckResult(StrEnum):
    OK = "OK"
    ERROR = "ERROR"
    EXPIRED = "EXPIRED"
    DUPLICATE = "DUPLICATE"
class DeviceState(StrEnum):
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"
class DeviceConnectionStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
class HelpSource(StrEnum):
    GESTURE = "GESTURE"
    WEB = "WEB"
class HelpStatus(StrEnum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
class UserRole(StrEnum):
    USER = "USER"
    GUARDIAN = "GUARDIAN"
    ADMIN = "ADMIN"

@dataclass(slots=True)
class Message:
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if isinstance(value, dict): return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list): return [_jsonable(item) for item in value]
    return value

@dataclass(slots=True)
class FrameMetadata(Message):
    type: str = "frame_metadata"
    frame_id: str = field(default_factory=new_id)
    correlation_id: str = ""
    edge_id: str = ""
    camera_id: str = ""
    captured_at_ms: int = field(default_factory=now_ms)
    width: int = 640
    height: int = 480
    format: str = "jpeg"
    jpeg_quality: int = 95
    mirrored: bool = False
    rotation_deg: int = 0
    def __post_init__(self) -> None:
        if not self.correlation_id: self.correlation_id = self.frame_id
        if self.width <= 0 or self.height <= 0 or self.format.lower() != "jpeg": raise ValueError("invalid JPEG dimensions")
        if not 1 <= self.jpeg_quality <= 100 or self.rotation_deg not in (0, 90, 180, 270): raise ValueError("invalid frame metadata")

@dataclass(slots=True)
class FrameAck(Message):
    type: str = "frame_ack"
    frame_id: str = ""
    status: str = "PROCESSED"
    received_at_ms: int = field(default_factory=now_ms)
    processed_at_ms: int = field(default_factory=now_ms)
    processing_time_ms: int = 0

@dataclass(slots=True)
class PointingVector:
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    def __post_init__(self) -> None:
        if not all(0 <= value <= 1 for value in (self.start_x, self.start_y, self.end_x, self.end_y)): raise ValueError("coordinates must be normalized")

@dataclass(slots=True)
class GestureResult(Message):
    # name/confidence/timestamp keep the previous local demo usable.
    name: str | None = None
    confidence: float = 1.0
    timestamp: float = field(default_factory=time)
    frame_id: str = ""
    correlation_id: str = ""
    handedness: Handedness = Handedness.UNKNOWN
    gesture: GestureType = GestureType.UNKNOWN
    pointing_vector: PointingVector | None = None
    stable_frames: int = 0
    hold_time_ms: int = 0
    detected_at_ms: int = field(default_factory=now_ms)

@dataclass(slots=True)
class IntentResult(Message):
    intent_id: str = field(default_factory=new_id)
    correlation_id: str = ""
    target_device_id: str | None = None
    action: IntentAction = IntentAction.HELP
    status: IntentStatus = IntentStatus.PENDING
    confirmed_at_ms: int | None = None
    cancel_reason: str | None = None

@dataclass(slots=True)
class MqttCommand(Message):
    command_id: str = field(default_factory=new_id)
    correlation_id: str = ""
    device_id: str = ""
    action: IntentAction = IntentAction.ON
    issued_at_ms: int = field(default_factory=now_ms)
    expires_at_ms: int = 0
    source: CommandSource = CommandSource.GESTURE
    def __post_init__(self) -> None:
        if self.action not in (IntentAction.ON, IntentAction.OFF): raise ValueError("MQTT commands support only ON and OFF")
        if self.expires_at_ms and self.expires_at_ms <= self.issued_at_ms: raise ValueError("expires_at_ms must be after issued_at_ms")

@dataclass(slots=True)
class MqttAck(Message):
    command_id: str = ""
    correlation_id: str = ""
    device_id: str = ""
    result: AckResult = AckResult.OK
    state: DeviceState = DeviceState.UNKNOWN
    processed_at_ms: int = field(default_factory=now_ms)
    error_code: str | None = None

@dataclass(slots=True)
class DeviceStateMessage(Message):
    device_id: str = ""
    state: DeviceState = DeviceState.UNKNOWN
    updated_at_ms: int = field(default_factory=now_ms)

@dataclass(slots=True)
class DeviceStatusMessage(Message):
    device_id: str = ""
    status: DeviceConnectionStatus = DeviceConnectionStatus.OFFLINE
    timestamp_ms: int = field(default_factory=now_ms)

@dataclass(slots=True)
class HelpRequest(Message):
    request_id: str = field(default_factory=new_id)
    correlation_id: str = ""
    user_id: str = ""
    source: HelpSource = HelpSource.GESTURE
    status: HelpStatus = HelpStatus.CREATED
    created_at_ms: int = field(default_factory=now_ms)

@dataclass(slots=True)
class RealtimeEvent(Message):
    event_id: str = field(default_factory=new_id)
    event_type: str = ""
    correlation_id: str = ""
    timestamp_ms: int = field(default_factory=now_ms)
    data: dict[str, Any] = field(default_factory=dict)

# Compatibility with the pre-v1 local demo; new code uses GestureResult and IntentResult.
@dataclass(slots=True)
class GazeResult:
    target: str | None
    confidence: float
    timestamp: float = field(default_factory=time)

@dataclass(slots=True)
class Intent:
    target: str | None
    action: Action
    timestamp: float = field(default_factory=time)
