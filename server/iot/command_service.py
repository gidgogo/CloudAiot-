"""Build v1 MQTT commands; HELP is deliberately excluded."""
from shared.constants import COMMAND_TTL_MS
from shared.types import CommandSource, IntentAction, IntentResult, MqttCommand, now_ms
def command_from_intent(intent: IntentResult, source: CommandSource = CommandSource.GESTURE) -> MqttCommand:
    if intent.action not in (IntentAction.ON, IntentAction.OFF) or not intent.target_device_id: raise ValueError("only confirmed ON/OFF intents can become MQTT commands")
    issued=now_ms()
    return MqttCommand(correlation_id=intent.correlation_id, device_id=intent.target_device_id, action=intent.action, source=source, issued_at_ms=issued, expires_at_ms=issued+COMMAND_TTL_MS)
