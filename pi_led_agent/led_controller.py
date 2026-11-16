"""GPIO abstraction for one low-voltage LED on Raspberry Pi."""
from __future__ import annotations

from typing import Protocol


class LedDevice(Protocol):
    @property
    def is_lit(self) -> bool: ...

    def on(self) -> None: ...

    def off(self) -> None: ...

    def close(self) -> None: ...


class LedController:
    def __init__(self, device: LedDevice) -> None:
        self._device = device

    @classmethod
    def from_gpio(cls, pin: int, *, active_low: bool) -> "LedController":
        try:
            from gpiozero import LED
        except ImportError as exc:  # pragma: no cover - depends on deployment environment
            raise RuntimeError("gpiozero is required on Raspberry Pi; install the pi-led-agent dependency") from exc
        return cls(LED(pin, active_high=not active_low, initial_value=False))

    @property
    def is_on(self) -> bool:
        return bool(self._device.is_lit)

    def set(self, on: bool) -> None:
        if on:
            self._device.on()
        else:
            self._device.off()

    def close(self) -> None:
        self._device.close()
