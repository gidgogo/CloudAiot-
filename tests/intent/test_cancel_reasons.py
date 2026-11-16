"""의도 취소 사유 상수가 공통 인터페이스 규격 6.2와 같은지 확인한다."""

from server.intent import cancel_reasons


def test_cancel_reasons_match_spec_6_2():
    assert cancel_reasons.CANCEL_REASONS == {
        "TARGET_NOT_FOUND",
        "AMBIGUOUS_TARGET",
        "GESTURE_TIMEOUT",
        "INVALID_GESTURE",
        "DIRECTION_CHANGED",
    }


def test_each_constant_equals_its_name():
    for name in cancel_reasons.CANCEL_REASONS:
        assert getattr(cancel_reasons, name) == name
