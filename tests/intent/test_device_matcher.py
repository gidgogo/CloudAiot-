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
    match_pointing,
    normalize_angle_deg,
    pointing_direction_deg,
)
from shared.types import PointingVector

FAN = DeviceRegion("fan-01", -15.0, 15.0)
LIGHT = DeviceRegion("light-01", 30.0, 60.0)
TV = DeviceRegion("tv-01", 10.0, 40.0)  # FAN, LIGHT와 겹친다
RIGHT = DeviceRegion("right-01", 15.0, 45.0)  # FAN과 15°에서 경계가 맞닿는다
DISABLED_FAN = DeviceRegion("fan-01", -15.0, 15.0, enabled=False)


@pytest.mark.parametrize("angle, expected", [(0.0, "fan-01"), (45.0, "light-01")])
def test_angle_inside_one_region_returns_that_device(angle, expected):
    assert match_device(angle, [FAN, LIGHT]) == expected


@pytest.mark.parametrize("angle", [20.0, -90.0, 180.0])
def test_angle_outside_every_region_returns_none(angle):
    assert match_device(angle, [FAN, LIGHT]) is None


def test_overlapping_regions_return_none():
    assert match_device(12.0, [FAN, TV]) is None
    assert match_device(35.0, [TV, LIGHT]) is None


def test_angle_outside_the_overlap_still_matches():
    assert match_device(5.0, [FAN, TV]) == "fan-01"
    assert match_device(20.0, [FAN, TV]) == "tv-01"


@pytest.mark.parametrize("angle", [-15.0, 15.0])
def test_region_boundaries_are_inclusive(angle):
    assert match_device(angle, [FAN]) == "fan-01"


def test_touching_boundaries_count_as_overlap():
    assert match_device(15.0, [FAN, RIGHT]) is None


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
    assert match_device_detail(12.0, [FAN, TV]) == DeviceMatch(None, AMBIGUOUS_TARGET)


def test_detail_reports_touching_boundary_as_ambiguous():
    assert match_device_detail(15.0, [FAN, RIGHT]) == DeviceMatch(None, AMBIGUOUS_TARGET)


@pytest.mark.parametrize("angle", [-90.0, -15.0, 0.0, 12.0, 15.0, 20.0, 45.0, 180.0])
def test_match_device_agrees_with_detail(angle):
    regions = [FAN, LIGHT, TV]
    assert match_device(angle, regions) == match_device_detail(angle, regions).device_id


# --- 비활성 기기 (enabled=False) --------------------------------------------


def test_regions_are_enabled_by_default():
    assert FAN.enabled is True


def test_disabled_device_is_not_matched():
    assert match_device_detail(0.0, [DISABLED_FAN]) == DeviceMatch(None, TARGET_NOT_FOUND)
    assert match_device(0.0, [DISABLED_FAN]) is None


def test_disabled_device_does_not_make_overlap_ambiguous():
    disabled_tv = DeviceRegion("tv-01", 10.0, 40.0, enabled=False)
    assert match_device_detail(12.0, [FAN, disabled_tv]) == DeviceMatch("fan-01", None)


# --- 각도 정규화와 ±180° 경계 -------------------------------------------------


@pytest.mark.parametrize(
    "angle, expected",
    [(0.0, 0.0), (180.0, 180.0), (-180.0, 180.0), (190.0, -170.0), (-190.0, 170.0), (540.0, 180.0)],
)
def test_normalize_angle_maps_into_minus_180_to_180(angle, expected):
    assert normalize_angle_deg(angle) == pytest.approx(expected)


DOOR = DeviceRegion("door-01", 170.0, -170.0)  # min > max: ±180°(왼쪽)를 넘어가는 범위


@pytest.mark.parametrize("angle", [170.0, 175.0, 180.0, -180.0, -175.0, -170.0])
def test_wraparound_region_contains_angles_across_180(angle):
    assert match_device_detail(angle, [DOOR, FAN]) == DeviceMatch("door-01", None)


@pytest.mark.parametrize("angle", [165.0, -165.0, 0.0, 90.0])
def test_wraparound_region_excludes_angles_outside(angle):
    assert match_device(angle, [DOOR]) is None


def test_wraparound_region_can_overlap_another_region():
    shelf = DeviceRegion("shelf-01", 160.0, 175.0)
    assert match_device_detail(172.0, [DOOR, shelf]) == DeviceMatch(None, AMBIGUOUS_TARGET)


# --- 포인팅 벡터로 매칭 (match_pointing) ----------------------------------------


def vector(dx: float, dy: float) -> PointingVector:
    """화면 가운데에서 (dx, dy)만큼 뻗은 정규화 벡터."""
    return PointingVector(0.5, 0.5, 0.5 + dx, 0.5 + dy)


@pytest.mark.parametrize(
    "direction, pointing, device",
    [
        ("오른쪽 0°", vector(0.3, 0.0), "right-01"),
        ("아래 +90°", vector(0.0, 0.3), "down-01"),
        ("위 -90°", vector(0.0, -0.3), "up-01"),
        ("왼쪽 ±180°", vector(-0.3, 0.0), "left-01"),
    ],
)
def test_pointing_angle_convention(direction, pointing, device):
    regions = [
        DeviceRegion("right-01", -15.0, 15.0),
        DeviceRegion("down-01", 75.0, 105.0),
        DeviceRegion("up-01", -105.0, -75.0),
        DeviceRegion("left-01", 165.0, -165.0),
    ]
    assert match_pointing(pointing, regions).device_id == device, direction


DIAGONAL = vector(0.1, 0.1)  # 640x480에서는 약 36.9°, 480x480에서는 45°
DIAGONAL_REGIONS = [DeviceRegion("shelf-01", 30.0, 40.0), DeviceRegion("lamp-01", 42.0, 50.0)]


def test_aspect_ratio_changes_the_matched_device():
    assert match_pointing(DIAGONAL, DIAGONAL_REGIONS, 640, 480).device_id == "shelf-01"
    assert match_pointing(DIAGONAL, DIAGONAL_REGIONS, 480, 480).device_id == "lamp-01"


def test_default_frame_size_is_640_by_480():
    assert match_pointing(DIAGONAL, DIAGONAL_REGIONS) == match_pointing(DIAGONAL, DIAGONAL_REGIONS, 640, 480)


def test_match_pointing_reports_spec_reasons():
    assert match_pointing(vector(0.0, 0.3), [FAN]) == DeviceMatch(None, TARGET_NOT_FOUND)
    inner_tv = DeviceRegion("tv-01", -5.0, 5.0)
    assert match_pointing(vector(0.3, 0.0), [FAN, inner_tv]) == DeviceMatch(None, AMBIGUOUS_TARGET)


def test_match_pointing_skips_disabled_devices():
    assert match_pointing(vector(0.3, 0.0), [DISABLED_FAN]) == DeviceMatch(None, TARGET_NOT_FOUND)


@pytest.mark.parametrize("width, height", [(0, 480), (640, 0), (-640, 480)])
def test_match_pointing_rejects_invalid_frame_size(width, height):
    with pytest.raises(ValueError):
        match_pointing(vector(0.3, 0.0), [FAN], width, height)


@pytest.mark.parametrize(
    "pointing, expected",
    [(vector(0.3, 0.0), 0.0), (vector(0.0, 0.3), 90.0), (vector(0.0, -0.3), -90.0), (vector(-0.3, 0.0), 180.0)],
)
def test_pointing_direction_is_normalized(pointing, expected):
    assert pointing_direction_deg(pointing) == pytest.approx(expected)


def test_pointing_direction_rejects_invalid_frame_size():
    with pytest.raises(ValueError):
        pointing_direction_deg(vector(0.3, 0.0), 640, 0)
