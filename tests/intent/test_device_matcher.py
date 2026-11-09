"""포인팅 방향과 기기 영역 매칭 테스트.

server/intent/device_matcher.py의 현재 동작을 고정한다.
"""

import pytest

from server.intent.device_matcher import DeviceRegion, match_device

FAN = DeviceRegion("fan-01", -15.0, 15.0)
LIGHT = DeviceRegion("light-01", 30.0, 60.0)


@pytest.mark.parametrize("angle, expected", [(0.0, "fan-01"), (45.0, "light-01")])
def test_angle_inside_one_region_returns_that_device(angle, expected):
    assert match_device(angle, [FAN, LIGHT]) == expected


@pytest.mark.parametrize("angle", [20.0, -90.0, 180.0])
def test_angle_outside_every_region_returns_none(angle):
    assert match_device(angle, [FAN, LIGHT]) is None


def test_overlapping_regions_return_none():
    tv = DeviceRegion("tv-01", 10.0, 40.0)
    assert match_device(12.0, [FAN, tv]) is None
    assert match_device(35.0, [tv, LIGHT]) is None


def test_angle_outside_the_overlap_still_matches():
    tv = DeviceRegion("tv-01", 10.0, 40.0)
    assert match_device(5.0, [FAN, tv]) == "fan-01"
    assert match_device(20.0, [FAN, tv]) == "tv-01"


@pytest.mark.parametrize("angle", [-15.0, 15.0])
def test_region_boundaries_are_inclusive(angle):
    assert match_device(angle, [FAN]) == "fan-01"


def test_touching_boundaries_count_as_overlap():
    right = DeviceRegion("right-01", 15.0, 45.0)
    assert match_device(15.0, [FAN, right]) is None


def test_empty_regions_return_none():
    assert match_device(0.0, []) is None
