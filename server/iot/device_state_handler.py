"""Parse retained state/status messages from ESP32."""
from shared.types import DeviceConnectionStatus, DeviceState, DeviceStateMessage, DeviceStatusMessage
def parse_state(payload:dict) -> DeviceStateMessage: return DeviceStateMessage(device_id=payload["device_id"],state=DeviceState(payload["state"]),updated_at_ms=payload["updated_at_ms"])
def parse_status(payload:dict) -> DeviceStatusMessage: return DeviceStatusMessage(device_id=payload["device_id"],status=DeviceConnectionStatus(payload["status"]),timestamp_ms=payload["timestamp_ms"])
