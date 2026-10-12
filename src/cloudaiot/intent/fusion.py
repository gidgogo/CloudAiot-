"""의도 판단: 시선과 손동작을 함께 보고 명령을 결정한다.

둘 중 하나라도 인식되지 않으면 아무 동작도 하지 않는다.
"""

import time
from typing import Dict, Optional, Tuple

from cloudaiot.types import Action, GazeResult, GestureResult, Intent


class IntentFusion:
    def __init__(
        self,
        mapping: Dict[str, str],
        fusion_window_sec: float = 1.5,
        cooldown_sec: float = 2.0,
        min_confidence: float = 0.7,
    ):
        self.mapping = {name: Action(value) for name, value in mapping.items()}
        self.fusion_window_sec = fusion_window_sec
        self.cooldown_sec = cooldown_sec
        self.min_confidence = min_confidence
        self._last: Optional[Tuple[Intent, float]] = None

    def decide(self, gaze: GazeResult, gesture: GestureResult) -> Optional[Intent]:
        now = time.time()
        if gesture.name is None or gesture.name not in self.mapping:
            return None
        # FR-03/FR-05: 도움 요청도 시선과 손동작이 함께 확인되어야 한다.
        if gaze.target is None:
            return None
        if not (
            self.min_confidence <= gaze.confidence <= 1.0
            and self.min_confidence <= gesture.confidence <= 1.0
        ):
            return None
        # 서로 가까운 시각에 얻은 입력이어도 오래된 결과를 재실행하지 않는다.
        if not (
            0 <= now - gaze.timestamp <= self.fusion_window_sec
            and 0 <= now - gesture.timestamp <= self.fusion_window_sec
        ):
            return None

        action = self.mapping[gesture.name]
        intent = Intent(target=gaze.target, action=action)
        cooldown_now = time.monotonic()
        if self._last is not None:
            last, at = self._last
            if (last.target, last.action) == (intent.target, intent.action) and cooldown_now - at < self.cooldown_sec:
                return None
        self._last = (intent, cooldown_now)
        return intent
