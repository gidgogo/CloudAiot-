"""AI 의도 결과의 상태별 action 및 JSON Schema 계약을 검증한다."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from shared.types import GestureResult, GestureType, Handedness, IntentAction, IntentResult, IntentStatus, PointingVector


def test_pending_and_cancelled_intents_serialize_null_action() -> None:
    pending = IntentResult(status=IntentStatus.PENDING)
    cancelled = IntentResult(status=IntentStatus.CANCELLED, cancel_reason="TARGET_NOT_FOUND")

    assert pending.as_dict()["action"] is None
    assert cancelled.as_dict()["action"] is None


def test_confirmed_intent_keeps_its_action() -> None:
    confirmed = IntentResult(status=IntentStatus.CONFIRMED, action=IntentAction.ON)

    assert confirmed.as_dict()["action"] == "ON"


SCHEMA_DIR = Path(__file__).parents[2] / "shared" / "schemas" / "v1"


def _schema_errors(schema_name: str, payload: dict) -> list[str]:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    return [error.message for error in Draft202012Validator(schema).iter_errors(payload)]


def test_v1_schema_accepts_pending_and_cancelled_null_action() -> None:
    pending = IntentResult(status=IntentStatus.PENDING).as_dict()
    cancelled = IntentResult(status=IntentStatus.CANCELLED, cancel_reason="TARGET_NOT_FOUND").as_dict()

    assert _schema_errors("intent-result.schema.json", pending) == []
    assert _schema_errors("intent-result.schema.json", cancelled) == []


def test_v1_schema_rejects_unconfirmed_command_action() -> None:
    payload = IntentResult(
        target_device_id="fan-01",
        action=IntentAction.ON,
        status=IntentStatus.CANCELLED,
        cancel_reason="TARGET_NOT_FOUND",
    ).as_dict()

    assert _schema_errors("intent-result.schema.json", payload)


def test_v1_gesture_schema_accepts_normalized_pointing_vector() -> None:
    payload = GestureResult(
        frame_id="frame-1",
        correlation_id="corr-1",
        handedness=Handedness.RIGHT,
        gesture=GestureType.POINTING,
        pointing_vector=PointingVector(0.1, 0.2, 0.8, 0.7),
        stable_frames=6,
        hold_time_ms=500,
        detected_at_ms=1,
    ).as_dict()

    assert _schema_errors("gesture-result.schema.json", payload) == []

