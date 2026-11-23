"""연속 프레임과 유지 시간 테스트. 10 FPS(100ms 간격)를 기준으로 한다."""

from server.vision.stability_checker import StabilityChecker
from shared.types import GestureType

T0 = 1_000


def feed(checker, gesture, count, start_ms=T0, step_ms=100):
    return [checker.update(gesture, start_ms + index * step_ms) for index in range(count)][-1]


def test_stable_after_six_frames_and_500ms():
    checker = StabilityChecker()
    assert not feed(checker, GestureType.OPEN_PALM, 5).stable
    result = checker.update(GestureType.OPEN_PALM, T0 + 500)
    assert (result.frames, result.hold_ms, result.stable) == (6, 500, True)


def test_enough_frames_but_short_hold_is_not_stable():
    result = feed(StabilityChecker(), GestureType.POINTING, 8, step_ms=50)
    assert result.frames == 8 and result.hold_ms == 350 and not result.stable


def test_different_gesture_starts_a_new_run():
    checker = StabilityChecker()
    feed(checker, GestureType.POINTING, 6)
    result = checker.update(GestureType.OPEN_PALM, T0 + 600)
    assert (result.frames, result.hold_ms) == (1, 0)


def test_unknown_reports_zero_and_restarts_the_run():
    checker = StabilityChecker()
    feed(checker, GestureType.V_SIGN, 6)
    unknown = checker.update(GestureType.UNKNOWN, T0 + 600)
    assert (unknown.frames, unknown.hold_ms, unknown.stable) == (0, 0, False)
    assert checker.update(GestureType.V_SIGN, T0 + 700).frames == 1


def test_long_pause_between_frames_restarts_the_run():
    checker = StabilityChecker()
    feed(checker, GestureType.FIST, 3)
    result = checker.update(GestureType.FIST, T0 + 200 + 501)
    assert (result.frames, result.hold_ms) == (1, 0)


def test_timestamp_going_backwards_restarts_the_run():
    checker = StabilityChecker()
    feed(checker, GestureType.POINTING, 3)
    assert checker.update(GestureType.POINTING, T0).frames == 1


def test_zero_timestamp_is_a_valid_time():
    checker = StabilityChecker()
    checker.update(GestureType.POINTING, 0)
    assert checker.update(GestureType.POINTING, 100).hold_ms == 100
