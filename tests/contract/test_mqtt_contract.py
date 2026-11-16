"""MQTT 명령 변환 경계의 안전성 계약을 검증한다."""

import pytest

from server.iot.command_service import command_from_intent
from shared.types import IntentAction, IntentResult, IntentStatus


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


@pytest.mark.parametrize("status", [IntentStatus.PENDING, IntentStatus.CANCELLED])
def test_unconfirmed_intent_never_becomes_mqtt_command(status: IntentStatus) -> None:
    intent = IntentResult(
        target_device_id="fan-01",
        action=IntentAction.ON,
        status=status,
    )

    with pytest.raises(ValueError, match="confirmed"):
        command_from_intent(intent)

