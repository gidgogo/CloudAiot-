"""기기 제어 이력(ControlEventService)과 조회 API 테스트."""

import pytest

from server.services.control_event_service import ControlEventService
from shared.errors import InterfaceError
from shared.types import AckResult, DeviceState, IntentAction, MqttAck, MqttCommand


@pytest.fixture
def service(app, device):
    with app.state.db.session() as session:
        yield ControlEventService(session, app.state.events)


def command(command_id="cmd-1", issued=1_000, action=IntentAction.ON):
    return MqttCommand(command_id=command_id, correlation_id=f"corr-{command_id}", device_id="fan-01",
                       action=action, issued_at_ms=issued, expires_at_ms=issued + 5_000)


def ack(command_id="cmd-1", result=AckResult.OK, state=DeviceState.ON, error_code=None):
    return MqttAck(command_id=command_id, correlation_id=f"corr-{command_id}", device_id="fan-01",
                   result=result, state=state, processed_at_ms=1_200, error_code=error_code)


def test_successful_command_records_latency_and_device_state(client, service, events):
    service.record_command(command(), gesture_confirmed_at_ms=900)
    record = service.record_ack(ack(), received_at_ms=1_250)

    assert record.status == "COMPLETED"
    assert record.latency_ms == 350  # 제스처 확정(900) → ACK 수신(1250)
    assert client.get("/api/v1/devices/fan-01").json()["data"]["state"] == "ON"
    assert [event.event_type for event in events] == ["command.created", "device.state_changed", "command.completed"]
    assert events[0].correlation_id == "corr-cmd-1"


def test_failed_acks(service):
    service.record_command(command("cmd-err"))
    service.record_command(command("cmd-exp"))
    assert service.record_ack(ack("cmd-err", AckResult.ERROR, error_code="RELAY_FAULT")).error_code == "RELAY_FAULT"
    expired = service.record_ack(ack("cmd-exp", AckResult.EXPIRED))
    assert (expired.status, expired.error_code) == ("FAILED", "COMMAND_EXPIRED")


def test_timeout_then_late_ack_is_ignored(service, events):
    service.record_command(command())
    assert service.mark_timeout("cmd-1").error_code == "ACK_TIMEOUT"
    late = service.record_ack(ack())
    assert late.status == "FAILED"
    assert late.ack_received_at_ms is None
    assert [event.event_type for event in events] == ["command.created", "command.failed"]


def test_command_errors(service):
    service.record_command(command())
    with pytest.raises(InterfaceError) as duplicate:
        service.record_command(command())
    assert duplicate.value.code == "COMMAND_ALREADY_EXISTS"

    other = command("cmd-2")
    other.device_id = "nope"
    with pytest.raises(InterfaceError) as missing:
        service.record_command(other)
    assert missing.value.code == "DEVICE_NOT_FOUND"


def test_list_is_newest_first_with_pagination(client, service):
    for index in range(3):
        service.record_command(command(f"cmd-{index}", issued=1_000 + index))

    body = client.get("/api/v1/control-events", params={"limit": 2}).json()
    assert [item["command_id"] for item in body["data"]] == ["cmd-2", "cmd-1"]
    assert body["meta"] == {"total": 3, "limit": 2, "offset": 0}
    assert client.get("/api/v1/control-events", params={"device_id": "other"}).json()["meta"]["total"] == 0
    assert client.get("/api/v1/control-events/cmd-0").json()["data"]["status"] == "PENDING"
    assert client.get("/api/v1/control-events", params={"limit": 0}).status_code == 422
