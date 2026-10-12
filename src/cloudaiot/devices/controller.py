"""의도(Intent)를 받아 해당 기기를 제어한다."""

from typing import Dict

from cloudaiot.devices.base import Device, MockDevice
from cloudaiot.devices.gpio_relay import GpioRelayDevice
from cloudaiot.types import Action, Intent


def build_devices(config: Dict[str, dict], mock: bool = False) -> Dict[str, Device]:
    devices: Dict[str, Device] = {}
    for name, spec in config.items():
        if mock:
            devices[name] = MockDevice(name)
        elif spec.get("type") == "gpio_relay":
            devices[name] = GpioRelayDevice(name, spec["pin"])
        else:
            raise ValueError(f"알 수 없는 기기 종류: {spec.get('type')}")
    return devices


class DeviceController:
    def __init__(self, devices: Dict[str, Device]):
        self.devices = devices

    def execute(self, intent: Intent) -> bool:
        device = self.devices.get(intent.target)
        if device is None:
            return False
        if intent.action is Action.ON:
            device.turn_on()
        elif intent.action is Action.OFF:
            device.turn_off()
        else:
            return False
        return True
