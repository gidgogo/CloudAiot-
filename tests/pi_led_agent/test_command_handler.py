import json

import pytest

from pi_led_agent.command_handler import CommandHandler
from pi_led_agent.led_controller import LedController
from shared.types import AckResult, CommandSource, IntentAction, MqttCommand

NOW = 1_793_430_000_000


class FakeLed:
    def __init__(self) -> None:
        self.is_lit = False
        self.fail = False

    def on(self) -> None:
        if self.fail:
            raise RuntimeError("gpio failure")
        self.is_lit = True

    def off(self) -> None:
        if self.fail:
            raise RuntimeError("gpio failure")
        self.is_lit = False

    def close(self) -> None:
        pass


def make_handler(*, synced=True, led=None):
    led = led or FakeLed()
    return CommandHandler("pi-led-01", LedController(led), time_synced=lambda: synced, clock_ms=lambda: NOW), led


def command(action=IntentAction.ON, *, device_id="pi-led-01", issued=NOW - 100, ttl=5_000):
    message = MqttCommand(
        correlation_id="corr-1", device_id=device_id, action=action,
        issued_at_ms=issued, expires_at_ms=issued + ttl, source=CommandSource.GESTURE,
    )
    return json.dumps(message.as_dict())


def test_confirmed_on_command_turns_led_on_and_returns_contract_ack():
    handler, led = make_handler()
    result = handler.handle(command())
    assert led.is_lit
    assert result.ack.result is AckResult.OK
    assert result.ack.state.value == "ON"
    assert result.state is not None and result.state.state.value == "ON"


def test_expired_command_does_not_change_led():
    handler, led = make_handler()
    result = handler.handle(command(issued=NOW - 10_000, ttl=5_000))
    assert result.ack.result is AckResult.EXPIRED
    assert not led.is_lit


def test_duplicate_command_is_acknowledged_without_repeating_gpio_operation():
    handler, led = make_handler()
    raw = command()
    handler.handle(raw)
    led.is_lit = False
    result = handler.handle(raw)
    assert result.ack.result is AckResult.DUPLICATE
    assert not led.is_lit


@pytest.mark.parametrize(
    ("change", "error_code"),
    [
        ({"schema_version": "2.0"}, "UNSUPPORTED_VERSION"),
        ({"device_id": "other-led"}, "DEVICE_NOT_FOUND"),
        ({"action": "HELP"}, "INVALID_SCHEMA"),
        ({"source": "UNKNOWN"}, "INVALID_SCHEMA"),
    ],
)
def test_invalid_command_returns_error_ack(change, error_code):
    handler, led = make_handler()
    payload = json.loads(command())
    payload.update(change)
    result = handler.handle(json.dumps(payload))
    assert result.ack.result is AckResult.ERROR
    assert result.ack.error_code == error_code
    assert not led.is_lit


def test_unsynchronized_clock_blocks_actuation():
    handler, led = make_handler(synced=False)
    result = handler.handle(command())
    assert result.ack.error_code == "TIME_NOT_SYNCED"
    assert not led.is_lit


def test_bad_json_without_command_id_is_dropped():
    handler, _ = make_handler()
    assert handler.handle(b"not-json").ack is None
