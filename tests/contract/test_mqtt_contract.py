"""MQTT 명령 변환 경계와 v1 JSON Schema 계약을 검증한다."""

import json
from pathlib import Path

import jsonschema
import pytest

from server.iot.command_service import command_from_intent
from shared.types import IntentAction, IntentResult, IntentStatus, MqttAck

SCHEMAS = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "v1"


def schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_confirmed_on_intent_becomes_mqtt_command() -> None:
    command = command_from_intent(
        IntentResult(
            correlation_id="corr-1",
            target_device_id="fan-01",
            action=IntentAction.ON,
            status=IntentStatus.CONFIRMED,
        )
    )

    assert command.device_id == "fan-01"
    assert command.action is IntentAction.ON
    jsonschema.validate(command.as_dict(), schema("mqtt-command.schema.json"))


@pytest.mark.parametrize("status", [IntentStatus.PENDING, IntentStatus.CANCELLED])
def test_unconfirmed_intent_never_becomes_mqtt_command(status: IntentStatus) -> None:
    intent = IntentResult(
        target_device_id="fan-01",
        action=IntentAction.ON,
        status=status,
    )

    with pytest.raises(ValueError, match="confirmed"):
        command_from_intent(intent)


def test_mqtt_ack_type_matches_v1_schema() -> None:
    ack = MqttAck(
        command_id="command-1", correlation_id="corr-1", device_id="fan-01",
        processed_at_ms=1,
    )
    jsonschema.validate(ack.as_dict(), schema("mqtt-ack.schema.json"))

