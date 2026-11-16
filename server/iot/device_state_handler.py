"""Validate and parse retained state/status messages from MQTT devices."""

from shared.constants import SCHEMA_VERSION
from shared.types import DeviceConnectionStatus, DeviceState, DeviceStateMessage, DeviceStatusMessage


def _validate(payload: dict, fields: set[str], timestamp_field: str) -> None:
    if set(payload) != fields or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid MQTT state/status schema")
    if not isinstance(payload.get("device_id"), str) or not payload["device_id"]:
        raise ValueError("invalid device_id")
    timestamp = payload.get(timestamp_field)
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise ValueError(f"invalid {timestamp_field}")


def parse_state(payload: dict) -> DeviceStateMessage:
    _validate(payload, {"schema_version", "device_id", "state", "updated_at_ms"}, "updated_at_ms")
    return DeviceStateMessage(device_id=payload["device_id"], state=DeviceState(payload["state"]),
                              updated_at_ms=payload["updated_at_ms"])


def parse_status(payload: dict) -> DeviceStatusMessage:
    _validate(payload, {"schema_version", "device_id", "status", "timestamp_ms"}, "timestamp_ms")
    return DeviceStatusMessage(device_id=payload["device_id"], status=DeviceConnectionStatus(payload["status"]),
                               timestamp_ms=payload["timestamp_ms"])
