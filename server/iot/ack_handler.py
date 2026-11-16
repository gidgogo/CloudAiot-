"""Validate and parse MQTT ACK messages."""

from shared.constants import SCHEMA_VERSION
from shared.types import AckResult, DeviceState, MqttAck

_FIELDS = {"schema_version", "command_id", "correlation_id", "device_id", "result", "state", "processed_at_ms", "error_code"}


def parse_ack(payload: dict) -> MqttAck:
    if set(payload) != _FIELDS or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("invalid MQTT ACK schema")
    if any(not isinstance(payload.get(name), str) or not payload[name]
           for name in ("command_id", "correlation_id", "device_id")):
        raise ValueError("invalid MQTT ACK identifiers")
    processed = payload.get("processed_at_ms")
    if isinstance(processed, bool) or not isinstance(processed, int) or processed < 0:
        raise ValueError("invalid processed_at_ms")
    return MqttAck(
        command_id=payload["command_id"], correlation_id=payload["correlation_id"],
        device_id=payload["device_id"], result=AckResult(payload["result"]),
        state=DeviceState(payload["state"]), processed_at_ms=processed,
        error_code=payload["error_code"],
    )
