"""Rule thresholds shared by the intent modules."""
from dataclasses import dataclass
@dataclass(frozen=True)
class IntentParameters:
    selection_timeout_ms: int = 3000
    min_stable_frames: int = 6
    min_hold_ms: int = 500
    max_angle_delta_deg: float = 15.0
