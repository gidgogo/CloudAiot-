"""포인팅 방향과 기기 영역 매칭 테스트.

server/intent/device_matcher.py의 동작을 고정한다.
match_device는 기기 ID만, match_device_detail은 매칭 실패 사유(스펙 6.2)까지 돌려준다.
"""

import pytest

from server.intent.device_matcher import (
    AMBIGUOUS_TARGET,
    TARGET_NOT_FOUND,
    DeviceMatch,
    DeviceRegion,
    match_device,
    match_device_detail,
)

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


# --- 매칭 실패 사유 구분 (match_device_detail) ------------------------------


def test_cancel_reasons_use_spec_strings():
    assert TARGET_NOT_FOUND == "TARGET_NOT_FOUND"
    assert AMBIGUOUS_TARGET == "AMBIGUOUS_TARGET"


def test_detail_returns_single_match_without_reason():
    assert match_device_detail(0.0, [FAN, LIGHT]) == DeviceMatch("fan-01", None)


@pytest.mark.parametrize("regions", [[FAN, LIGHT], []], ids=["outside-all", "no-regions"])
def test_detail_reports_target_not_found(regions):
    assert match_device_detail(20.0, regions) == DeviceMatch(None, TARGET_NOT_FOUND)


def test_detail_reports_ambiguous_target_on_overlap():
    tv = DeviceRegion("tv-01", 10.0, 40.0)
    assert match_device_detail(12.0, [FAN, tv]) == DeviceMatch(None, AMBIGUOUS_TARGET)


def test_detail_reports_touching_boundary_as_ambiguous():
    right = DeviceRegion("right-01", 15.0, 45.0)
    assert match_device_detail(15.0, [FAN, right]) == DeviceMatch(None, AMBIGUOUS_TARGET)


@pytest.mark.parametrize("angle", [-90.0, -15.0, 0.0, 12.0, 15.0, 20.0, 45.0, 180.0])
def test_match_device_agrees_with_detail(angle):
    regions = [FAN, LIGHT, DeviceRegion("tv-01", 10.0, 40.0)]
    assert match_device(angle, regions) == match_device_detail(angle, regions).device_id


# --- 비활성 기기 (enabled=False) --------------------------------------------


def test_regions_are_enabled_by_default():
    assert FAN.enabled is True


def test_disabled_device_is_not_matched():
    disabled_fan = DeviceRegion("fan-01", -15.0, 15.0, enabled=False)
    assert match_device_detail(0.0, [disabled_fan]) == DeviceMatch(None, TARGET_NOT_FOUND)
    assert match_device(0.0, [disabled_fan]) is None


def test_disabled_device_does_not_make_overlap_ambiguous():
    disabled_tv = DeviceRegion("tv-01", 10.0, 40.0, enabled=False)
    assert match_device_detail(12.0, [FAN, disabled_tv]) == DeviceMatch("fan-01", None)
