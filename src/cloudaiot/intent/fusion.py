"""의도 판단: 시선과 손동작을 함께 보고 명령을 결정한다.

둘 중 하나라도 인식되지 않으면 아무 동작도 하지 않는다.
"""

import time
from typing import Dict, Optional, Tuple

from cloudaiot.types import Action, GazeResult, GestureResult, Intent


class IntentFusion:
    def __init__(self, mapping: Dict[str, str], fusion_window_sec: float = 1.5, cooldown_sec: float = 2.0):
        self.mapping = {name: Action(value) for name, value in mapping.items()}
        self.fusion_window_sec = fusion_window_sec
        self.cooldown_sec = cooldown_sec
        self._last: Optional[Tuple[Intent, float]] = None

    def decide(self, gaze: GazeResult, gesture: GestureResult) -> Optional[Intent]:
        if gesture.name is None or gesture.name not in self.mapping:
            return None
        action = self.mapping[gesture.name]

        # 보호자 호출 외의 명령은 시선 대상이 반드시 있어야 한다
        if action is not Action.CALL_CAREGIVER and gaze.target is None:
            return None
        if abs(gaze.timestamp - gesture.timestamp) > self.fusion_window_sec and gaze.target is not None:
            return None

        intent = Intent(target=gaze.target, action=action)
        now = time.time()
        if self._last is not None:
            last, at = self._last
            if (last.target, last.action) == (intent.target, intent.action) and now - at < self.cooldown_sec:
                return None
        self._last = (intent, now)
        return intent
