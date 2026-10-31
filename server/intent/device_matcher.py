"""Match a normalized pointing direction to registered device angle regions."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class DeviceRegion:
    device_id: str
    min_angle_deg: float
    max_angle_deg: float
def match_device(angle_deg: float, regions: list[DeviceRegion]) -> str | None:
    matches = [region.device_id for region in regions if region.min_angle_deg <= angle_deg <= region.max_angle_deg]
    return matches[0] if len(matches) == 1 else None
