"""Cancel reasons from the common interface spec v1.0, section 6.2.

shared/types.py has no CancelReason enum yet, so the intent module keeps the spec strings here.
"""

TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
GESTURE_TIMEOUT = "GESTURE_TIMEOUT"
INVALID_GESTURE = "INVALID_GESTURE"
DIRECTION_CHANGED = "DIRECTION_CHANGED"

CANCEL_REASONS = frozenset({
    TARGET_NOT_FOUND,
    AMBIGUOUS_TARGET,
    GESTURE_TIMEOUT,
    INVALID_GESTURE,
    DIRECTION_CHANGED,
})
