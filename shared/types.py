"""모듈 간에 주고받는 데이터 형식."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class Action(str, Enum):
    ON = "on"
    OFF = "off"
    CALL_CAREGIVER = "call_caregiver"


@dataclass
class GazeResult:
    """시선이 향한 기기. 아무것도 보지 않으면 target=None."""
    target: Optional[str]
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class GestureResult:
    """인식된 손동작 이름(예: 'open_palm'). 없으면 name=None."""
    name: Optional[str]
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class Intent:
    """시선 + 손동작을 결합해 판단한 사용자 의도."""
    target: Optional[str]  # 보호자 호출이면 None 가능
    action: Action
    timestamp: float = field(default_factory=time.time)
