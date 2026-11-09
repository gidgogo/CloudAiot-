"""Match a pointing direction to registered device angle regions.

Angles follow server/vision/pointing_detector.pointing_angle_deg:
0° points right, +90° down, -90° up and ±180° left (screen coordinates, y grows downward).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from server.intent.cancel_reasons import AMBIGUOUS_TARGET, TARGET_NOT_FOUND

# 주의: 포인팅 각도는 AI A 담당 파일(server/vision/pointing_detector.py)의 pointing_angle_deg로 계산한다.
# 이 함수의 각도 기준(오른쪽 0°, 아래 +90°)이나 계산식이 바뀌면 기기 매칭 결과도 바뀌므로,
# 웹에 등록된 기기 방향 영역(pointing_region)을 다시 보정해야 한다.
# tests/intent/test_device_matcher.py의 test_pointing_angle_convention이 이 기준을 확인한다.
from server.vision.pointing_detector import pointing_angle_deg
from shared.constants import DEFAULT_FRAME_HEIGHT, DEFAULT_FRAME_WIDTH
from shared.types import PointingVector


def normalize_angle_deg(angle_deg: float) -> float:
    """Map any angle into the range (-180, 180]."""
    shifted = math.fmod(angle_deg + 180.0, 360.0)
    if shifted <= 0:
        shifted += 360.0
    return shifted - 180.0


@dataclass(frozen=True)
class DeviceRegion:
    device_id: str
    min_angle_deg: float
    max_angle_deg: float
    enabled: bool = True

    def contains(self, angle_deg: float) -> bool:
        """Inclusive range. min > max means the range wraps across ±180° (for example 170 to -170)."""
        if self.min_angle_deg <= self.max_angle_deg:
            return self.min_angle_deg <= angle_deg <= self.max_angle_deg
        return angle_deg >= self.min_angle_deg or angle_deg <= self.max_angle_deg


@dataclass(frozen=True)
class DeviceMatch:
    """The single matched device, or the spec 6.2 cancel reason when there is none."""

    device_id: str | None
    cancel_reason: str | None = None


def match_device_detail(angle_deg: float, regions: list[DeviceRegion]) -> DeviceMatch:
    """Boundaries are inclusive; disabled devices are never matched."""
    angle_deg = normalize_angle_deg(angle_deg)
    matches = [region.device_id for region in regions if region.enabled and region.contains(angle_deg)]
    if not matches:
        return DeviceMatch(None, TARGET_NOT_FOUND)
    if len(matches) > 1:
        return DeviceMatch(None, AMBIGUOUS_TARGET)
    return DeviceMatch(matches[0])


def match_device(angle_deg: float, regions: list[DeviceRegion]) -> str | None:
    return match_device_detail(angle_deg, regions).device_id


def match_pointing(
    vector: PointingVector,
    regions: list[DeviceRegion],
    width: int = DEFAULT_FRAME_WIDTH,
    height: int = DEFAULT_FRAME_HEIGHT,
) -> DeviceMatch:
    """Match a normalized pointing vector using the real frame size (spec 4.3) so the aspect ratio does not skew the angle."""
    if width <= 0 or height <= 0:
        raise ValueError("frame width and height must be positive")
    return match_device_detail(pointing_angle_deg(vector, width, height), regions)
