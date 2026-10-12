"""라즈베리파이 GPIO 릴레이로 조명·선풍기를 켜고 끈다."""

from cloudaiot.devices.base import Device


class GpioRelayDevice(Device):
    def __init__(self, name: str, pin: int):
        super().__init__(name)
        self.pin = pin
        # TODO: gpiozero.OutputDevice(pin) 초기화 (라즈베리파이에서만)

    def turn_on(self) -> None:
        # TODO: 릴레이 ON
        self.is_on = True

    def turn_off(self) -> None:
        # TODO: 릴레이 OFF
        self.is_on = False
