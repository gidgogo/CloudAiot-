"""Match a normalized pointing direction to registered device angle regions."""
from __future__ import annotations

from dataclasses import dataclass

from server.intent.cancel_reasons import AMBIGUOUS_TARGET, TARGET_NOT_FOUND


@dataclass(frozen=True)
class DeviceRegion:
    device_id: str
    min_angle_deg: float
    max_angle_deg: float
    enabled: bool = True


@dataclass(frozen=True)
class DeviceMatch:
    """The single matched device, or the spec 6.2 cancel reason when there is none."""

    device_id: str | None
    cancel_reason: str | None = None


def match_device_detail(angle_deg: float, regions: list[DeviceRegion]) -> DeviceMatch:
    """Boundaries are inclusive; disabled devices are never matched."""
    matches = [
        region.device_id
        for region in regions
        if region.enabled and region.min_angle_deg <= angle_deg <= region.max_angle_deg
    ]
    if not matches:
        return DeviceMatch(None, TARGET_NOT_FOUND)
    if len(matches) > 1:
        return DeviceMatch(None, AMBIGUOUS_TARGET)
    return DeviceMatch(matches[0])


def match_device(angle_deg: float, regions: list[DeviceRegion]) -> str | None:
    return match_device_detail(angle_deg, regions).device_id
