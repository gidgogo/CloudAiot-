from pi_led_agent.led_controller import LedController


class FakeLed:
    def __init__(self) -> None:
        self.is_lit = False
        self.closed = False

    def on(self) -> None:
        self.is_lit = True

    def off(self) -> None:
        self.is_lit = False

    def close(self) -> None:
        self.closed = True


def test_led_controller_controls_and_closes_gpio_device():
    raw = FakeLed()
    controller = LedController(raw)
    controller.set(True)
    assert controller.is_on
    controller.set(False)
    assert not controller.is_on
    controller.close()
    assert raw.closed
