"""Rule thresholds shared by the intent modules.

The common interface spec does not fix these values; they are working defaults until the team agrees on them.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentParameters:
    selection_timeout_ms: int = 3000  # how long a pointed device stays selected without a thumb gesture
    min_stable_frames: int = 6  # a gesture must be seen in at least this many consecutive frames
    min_hold_ms: int = 500  # and held for at least this long before it can select or confirm
    max_angle_delta_deg: float = 15.0  # moving further than this from the selected angle is DIRECTION_CHANGED
    help_cooldown_ms: int = 5000  # minimum time between two confirmed HELP intents
