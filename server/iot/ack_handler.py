"""Validate and hand off MQTT ACK messages to the application service."""
from shared.types import AckResult, DeviceState, MqttAck
def parse_ack(payload:dict) -> MqttAck:
    return MqttAck(command_id=payload["command_id"], correlation_id=payload["correlation_id"], device_id=payload["device_id"], result=AckResult(payload["result"]), state=DeviceState(payload.get("state","UNKNOWN")), processed_at_ms=payload["processed_at_ms"], error_code=payload.get("error_code"))
