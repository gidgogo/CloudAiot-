"""릴레이 출력. 실제 GPIO(gpiozero)와 하드웨어 없는 Mock을 같은 인터페이스로 제공한다."""
from __future__ import annotations

import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Relay(Protocol):
    @property
    def is_on(self) -> bool: ...
    def set(self, on: bool) -> None: ...
    def close(self) -> None: ...


class MockRelay:
    """노트북 개발·테스트용. 상태만 메모리에 기록한다."""

    def __init__(self, name: str, initial_on: bool = False) -> None:
        self.name = name
        self._on = initial_on

    @property
    def is_on(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        self._on = on
        log.info("[mock relay] %s %s", self.name, "ON" if on else "OFF")

    def close(self) -> None:
        pass


class GpioRelay:
    """gpiozero OutputDevice로 릴레이 핀 하나를 제어한다. 라즈베리파이에서만 동작한다."""

    def __init__(self, name: str, pin: int, *, active_high: bool = False, initial_on: bool = False) -> None:
        from gpiozero import OutputDevice  # Pi가 아닌 환경에서 import 오류를 피하려고 지연 import

        self.name = name
        self._device = OutputDevice(pin, active_high=active_high, initial_value=initial_on)

    @property
    def is_on(self) -> bool:
        return bool(self._device.value)

    def set(self, on: bool) -> None:
        if on:
            self._device.on()
        else:
            self._device.off()

    def close(self) -> None:
        self._device.close()


def build_relays(devices_cfg: dict[str, dict[str, Any]], *, mock: bool = False) -> dict[str, Relay]:
    relays: dict[str, Relay] = {}
    for device_id, spec in devices_cfg.items():
        initial_on = str(spec.get("initial_state", "OFF")).upper() == "ON"
        if mock:
            relays[device_id] = MockRelay(device_id, initial_on)
        elif spec.get("type", "gpio_relay") == "gpio_relay":
            relays[device_id] = GpioRelay(
                device_id, int(spec["pin"]), active_high=bool(spec.get("active_high", False)), initial_on=initial_on
            )
        else:
            raise ValueError(f"unknown device type for {device_id}: {spec.get('type')!r}")
    return relays
