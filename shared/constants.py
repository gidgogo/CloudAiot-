"""공통 인터페이스 v1에서 사용하는 고정 값."""

SCHEMA_VERSION = "1.0"
MQTT_API_VERSION = "v1"
API_PREFIX = "/api/v1"
FRAME_WS_PATH = "/ws/v1/frames"
EVENT_WS_PATH = "/ws/v1/events"

DEFAULT_FRAME_WIDTH = 640
DEFAULT_FRAME_HEIGHT = 480
DEFAULT_FRAME_FPS = 10
DEFAULT_JPEG_QUALITY = 95
MAX_PENDING_FRAMES = 1
MAX_FRAME_BYTES = 2_000_000
FRAME_ACK_TIMEOUT_MS = 2_000  # Edge가 frame_ack를 기다리는 시간. MQTT 명령 ACK(ACK_TIMEOUT_MS)와 별개

ACK_TIMEOUT_MS = 2_000
COMMAND_TTL_MS = 5_000
EDGE_RECONNECT_DELAYS_SEC = (1, 2, 4, 8, 16, 30)

EVENT_TYPES = frozenset({
    "edge.connected", "edge.disconnected", "device.selected",
    "gesture.confirmed", "command.created", "command.completed",
    "command.failed", "device.state_changed", "help.created", "help.updated",
})
FRAME_ACK_STATUSES = frozenset({"PROCESSED", "DROPPED", "INVALID", "ERROR"})
GESTURES = frozenset({"POINTING", "THUMB_UP", "THUMB_DOWN", "HELP", "UNKNOWN"})
INTENT_STATUSES = frozenset({"PENDING", "CONFIRMED", "CANCELLED"})
HELP_STATUSES = frozenset({"CREATED", "CONFIRMED", "COMPLETED"})
ROLES = frozenset({"USER", "GUARDIAN", "ADMIN"})
