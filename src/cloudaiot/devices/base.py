"""제어 대상 기기 인터페이스."""

from abc import ABC, abstractmethod


class Device(ABC):
    def __init__(self, name: str):
        self.name = name
        self.is_on = False

    @abstractmethod
    def turn_on(self) -> None: ...

    @abstractmethod
    def turn_off(self) -> None: ...


class MockDevice(Device):
    """하드웨어 없이 테스트할 때 쓰는 가짜 기기."""

    def turn_on(self) -> None:
        self.is_on = True
        print(f"[mock] {self.name} ON")

    def turn_off(self) -> None:
        self.is_on = False
        print(f"[mock] {self.name} OFF")
