"""의도 판단 지연시간 기록 테스트 (NFR-01).

server/intent/latency_tracker.py(LatencyTracker)는 correlation_id별로 시각을 기록하고 경과 시간을 계산한다.
"""

import pytest

from server.intent.latency_tracker import GESTURE_DETECTED, INTENT_CONFIRMED, LatencyTracker


def test_elapsed_between_two_marks():
    tracker = LatencyTracker()
    tracker.mark("corr-1", GESTURE_DETECTED, 10_000)
    tracker.mark("corr-1", INTENT_CONFIRMED, 10_250)
    assert tracker.elapsed_ms("corr-1", GESTURE_DETECTED, INTENT_CONFIRMED) == 250


@pytest.mark.parametrize("missing", [GESTURE_DETECTED, INTENT_CONFIRMED])
def test_elapsed_is_none_when_a_mark_is_missing(missing):
    tracker = LatencyTracker()
    for name in {GESTURE_DETECTED, INTENT_CONFIRMED} - {missing}:
        tracker.mark("corr-1", name, 10_000)
    assert tracker.elapsed_ms("corr-1", GESTURE_DETECTED, INTENT_CONFIRMED) is None


def test_elapsed_is_none_for_unknown_correlation_id():
    assert LatencyTracker().elapsed_ms("nope", GESTURE_DETECTED, INTENT_CONFIRMED) is None


def test_marking_again_overwrites_the_time():
    tracker = LatencyTracker()
    tracker.mark("corr-1", GESTURE_DETECTED, 10_000)
    tracker.mark("corr-1", GESTURE_DETECTED, 10_100)
    tracker.mark("corr-1", INTENT_CONFIRMED, 10_300)
    assert tracker.elapsed_ms("corr-1", GESTURE_DETECTED, INTENT_CONFIRMED) == 200


def test_default_keeps_1000_correlation_ids():
    assert LatencyTracker().max_entries == 1000


def test_oldest_correlation_ids_are_dropped():
    tracker = LatencyTracker(max_entries=3)
    for index in range(5):
        tracker.mark(f"corr-{index}", GESTURE_DETECTED, index)
    assert list(tracker.timestamps) == ["corr-2", "corr-3", "corr-4"]


def test_updating_an_existing_id_does_not_drop_others():
    tracker = LatencyTracker(max_entries=2)
    tracker.mark("corr-a", GESTURE_DETECTED, 1)
    tracker.mark("corr-b", GESTURE_DETECTED, 2)
    tracker.mark("corr-a", INTENT_CONFIRMED, 3)
    assert set(tracker.timestamps) == {"corr-a", "corr-b"}


@pytest.mark.parametrize("max_entries", [0, -1])
def test_max_entries_must_be_positive(max_entries):
    with pytest.raises(ValueError):
        LatencyTracker(max_entries=max_entries)
