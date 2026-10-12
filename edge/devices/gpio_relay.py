"""라즈베리파이 GPIO 릴레이로 조명·선풍기를 켜고 끈다."""

from edge.devices.base import Device


class GpioRelayDevice(Device):
    def __init__(self, name: str, pin: int):
        super().__init__(name)
        self.pin = pin
        raise NotImplementedError("GPIO 릴레이 제어는 아직 구현되지 않았습니다. --mock을 사용하세요.")

    def turn_on(self) -> None:
        # TODO: 릴레이 ON
        self.is_on = True

    def turn_off(self) -> None:
        # TODO: 릴레이 OFF
        self.is_on = False
