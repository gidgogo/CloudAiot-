"""MQTT Topic v1 생성·검증 규칙."""

from shared.constants import MQTT_API_VERSION

TOPIC_SUFFIXES = frozenset({"cmd", "ack", "state", "status"})

def device_topic(home_id: str, device_id: str, suffix: str, *, version: str = MQTT_API_VERSION) -> str:
    if suffix not in TOPIC_SUFFIXES:
        raise ValueError(f"unsupported MQTT topic suffix: {suffix}")
    if not home_id or not device_id:
        raise ValueError("home_id and device_id are required")
    return f"aiot/{version}/{home_id}/{device_id}/{suffix}"

def command_topic(home_id: str, device_id: str) -> str:
    return device_topic(home_id, device_id, "cmd")

def ack_topic(home_id: str, device_id: str) -> str:
    return device_topic(home_id, device_id, "ack")

def state_topic(home_id: str, device_id: str) -> str:
    return device_topic(home_id, device_id, "state")

def status_topic(home_id: str, device_id: str) -> str:
    return device_topic(home_id, device_id, "status")

def parse_device_topic(topic: str) -> tuple[str, str, str, str]:
    """Return version, home_id, device_id, suffix or raise ValueError."""
    parts = topic.split("/")
    if len(parts) != 5 or parts[0] != "aiot" or parts[4] not in TOPIC_SUFFIXES:
        raise ValueError(f"invalid device topic: {topic}")
    return parts[1], parts[2], parts[3], parts[4]
