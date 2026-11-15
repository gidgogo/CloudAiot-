"""IoT 제어 Pi의 MQTT 명령 처리 테스트 (공통 인터페이스 v1 11장)."""
import json

import pytest

from iot_agent.command_handler import CommandHandler
from iot_agent.relay import MockRelay, build_relays
from shared.types import AckResult, CommandSource, DeviceState, IntentAction, MqttCommand

NOW = 1_793_430_000_000


def make_handler(*, synced=True, now=NOW, relay=None):
    relay = relay or MockRelay("fan-01")
    return CommandHandler("fan-01", relay, time_synced=lambda: synced, clock_ms=lambda: now), relay


def cmd(action=IntentAction.ON, *, device_id="fan-01", issued=NOW - 100, ttl=5_000):
    payload = MqttCommand(
        correlation_id="corr-1", device_id=device_id, action=action,
        issued_at_ms=issued, expires_at_ms=issued + ttl, source=CommandSource.WEB,
    ).as_dict()
    return json.dumps(payload)


def test_on_command_turns_relay_on_and_acks_ok():
    handler, relay = make_handler()
    result = handler.handle(cmd(IntentAction.ON))
    assert relay.is_on
    ack = result.ack.as_dict()
    assert ack["result"] == "OK" and ack["state"] == "ON" and ack["error_code"] is None
    assert ack["device_id"] == "fan-01" and ack["correlation_id"] == "corr-1" and ack["schema_version"] == "1.0"
    assert ack["processed_at_ms"] == NOW
    assert result.state.as_dict() == {"schema_version": "1.0", "device_id": "fan-01", "state": "ON", "updated_at_ms": NOW}


def test_ack_fields_match_shared_contract():
    handler, _ = make_handler()
    ack = handler.handle(cmd()).ack.as_dict()
    assert set(ack) == {"schema_version", "command_id", "correlation_id", "device_id", "result", "state", "processed_at_ms", "error_code"}


def test_same_state_publishes_no_state_change():
    handler, _ = make_handler()
    result = handler.handle(cmd(IntentAction.OFF))  # 이미 OFF
    assert result.ack.result is AckResult.OK and result.state is None


def test_duplicate_command_does_not_move_relay_again():
    handler, relay = make_handler()
    raw = cmd(IntentAction.ON)
    handler.handle(raw)
    relay.set(False)  # 다른 경로로 꺼진 상태라고 가정
    result = handler.handle(raw)
    assert result.ack.result is AckResult.DUPLICATE and result.ack.error_code == "COMMAND_DUPLICATE"
    assert not relay.is_on and result.state is None


def test_expired_command_is_not_executed():
    handler, relay = make_handler()
    result = handler.handle(cmd(issued=NOW - 10_000, ttl=5_000))
    assert result.ack.result is AckResult.EXPIRED and not relay.is_on


def test_unsynced_clock_blocks_execution():
    handler, relay = make_handler(synced=False)
    result = handler.handle(cmd())
    assert result.ack.result is AckResult.ERROR and result.ack.error_code == "TIME_NOT_SYNCED"
    assert not relay.is_on


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"schema_version": "2.0"}, "UNSUPPORTED_VERSION"),
        ({"device_id": "light-01"}, "DEVICE_NOT_FOUND"),
        ({"action": "HELP"}, "INVALID_SCHEMA"),
        ({"action": "TOGGLE"}, "INVALID_SCHEMA"),
        ({"expires_at_ms": None}, "INVALID_SCHEMA"),
    ],
)
def test_invalid_commands_get_error_ack(override, code):
    handler, relay = make_handler()
    payload = json.loads(cmd())
    payload.update(override)
    result = handler.handle(json.dumps(payload))
    assert result.ack.result is AckResult.ERROR and result.ack.error_code == code
    assert not relay.is_on


def test_missing_field_is_invalid_schema():
    handler, _ = make_handler()
    payload = json.loads(cmd())
    del payload["expires_at_ms"]
    assert handler.handle(json.dumps(payload)).ack.error_code == "INVALID_SCHEMA"


@pytest.mark.parametrize("raw", [b"not json", b"[]", json.dumps({"action": "ON"})])
def test_unaddressable_messages_are_dropped_without_ack(raw):
    handler, relay = make_handler()
    result = handler.handle(raw)
    assert result.ack is None and result.state is None and not relay.is_on


def test_relay_failure_reports_error_and_is_not_retried():
    class BrokenRelay(MockRelay):
        def set(self, on):
            raise OSError("gpio busy")

    handler, _ = make_handler(relay=BrokenRelay("fan-01"))
    raw = cmd()
    assert handler.handle(raw).ack.error_code == "INTERNAL_ERROR"
    assert handler.handle(raw).ack.result is AckResult.DUPLICATE


def test_dedup_memory_is_bounded():
    relay = MockRelay("fan-01")
    handler = CommandHandler("fan-01", relay, clock_ms=lambda: NOW, dedup_capacity=2)
    first = cmd()
    handler.handle(first)
    handler.handle(cmd())
    handler.handle(cmd())
    assert handler.handle(first).ack.result is not AckResult.DUPLICATE  # 가장 오래된 것은 잊음


def test_build_relays_mock_respects_initial_state():
    relays = build_relays({"light-01": {"pin": 17, "initial_state": "ON"}, "fan-01": {"pin": 27}}, mock=True)
    assert relays["light-01"].is_on and not relays["fan-01"].is_on


def test_state_message_reflects_relay():
    handler, relay = make_handler()
    relay.set(True)
    assert handler.state_message().state is DeviceState.ON
