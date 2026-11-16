"""AI 의도 결과의 상태별 action 계약을 검증한다."""

from shared.types import IntentAction, IntentResult, IntentStatus


def test_pending_and_cancelled_intents_serialize_null_action() -> None:
    pending = IntentResult(status=IntentStatus.PENDING)
    cancelled = IntentResult(status=IntentStatus.CANCELLED, cancel_reason="TARGET_NOT_FOUND")

    assert pending.as_dict()["action"] is None
    assert cancelled.as_dict()["action"] is None


def test_confirmed_intent_keeps_its_action() -> None:
    confirmed = IntentResult(status=IntentStatus.CONFIRMED, action=IntentAction.ON)

    assert confirmed.as_dict()["action"] == "ON"

