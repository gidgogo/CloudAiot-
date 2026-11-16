"""송출 기기의 물리 버튼과 상태 LED.

    버튼 짧게 누름 → 송출 시작/정지 토글
    LED 켜짐       → 송출 중
    LED 꺼짐       → 정지
    LED 빠른 깜빡임 → 송출 프로세스가 스스로 종료됨(카메라·설정 오류). 버튼을 다시 누르면 재시작

원격 제어(MQTT)를 켠 경우, 버튼으로 바뀐 상태를 state Topic에도 발행해 서버·웹이 같은 상태를 보게 하고
원격 명령으로 바뀐 상태도 같은 LED에 반영한다.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Protocol

from edge.stream_control.switch import ProcessSwitch

log = logging.getLogger(__name__)

BLINK_ON_SEC = BLINK_OFF_SEC = 0.15
BUTTON_BOUNCE_SEC = 0.05
PRESS_COOLDOWN_SEC = 1.0  # 한 번 처리한 뒤 이 시간 안의 입력은 같은 누름(접점 떨림)으로 본다


class Indicator(Protocol):
    def on(self) -> None: ...
    def off(self) -> None: ...
    def blink(self, on_time: float, off_time: float) -> None: ...
    def close(self) -> None: ...


class LogIndicator:
    """LED 핀이 없거나 --mock일 때 상태 변화를 로그로만 남긴다."""

    def __init__(self, name: str) -> None:
        self.name = name

    def on(self) -> None:
        log.info("[%s] LED on", self.name)

    def off(self) -> None:
        log.info("[%s] LED off", self.name)

    def blink(self, on_time: float, off_time: float) -> None:
        log.info("[%s] LED blinking", self.name)

    def close(self) -> None:
        pass


class StreamPanel:
    """스위치 상태를 LED에 반영하고, 버튼·원격 어느 쪽으로 바뀌든 state를 한 번만 발행한다."""

    def __init__(
        self,
        switch: ProcessSwitch,
        led: Indicator,
        publish_state: Callable[[], None],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.switch = switch
        self.led = led
        self._publish_state = publish_state
        self._clock = clock
        self._press_lock = threading.Lock()
        self._last_press_done = float("-inf")
        self._lock = threading.Lock()
        self._shown: tuple[bool, bool] | None = None  # (is_on, crashed) 마지막으로 LED에 반영한 값
        self.sync(publish=False)

    def press(self) -> None:
        """버튼 콜백 (gpiozero 스레드).

        송출을 멈추는 데 1초 가까이 걸리는 동안 버튼 접점 떨림(bounce)이 쌓였다가 연달아 들어오면
        ON/OFF가 여러 번 뒤집힌다. 처리 중에 들어온 입력과, 처리 직후 PRESS_COOLDOWN_SEC 안에
        들어온 입력은 같은 누름으로 보고 버린다.
        """
        if not self._press_lock.acquire(blocking=False):
            return
        try:
            if self._clock() - self._last_press_done < PRESS_COOLDOWN_SEC:
                return
            on = self.switch.toggle()
            log.info("[%s] button -> stream %s", self.switch.name, "ON" if on else "OFF")
            self.sync(publish=True)
        finally:
            self._last_press_done = self._clock()
            self._press_lock.release()

    def after_command(self) -> None:
        """MQTT 명령 처리 직후. state는 CommandHandler 쪽에서 이미 발행했으므로 LED만 맞춘다."""
        self.sync(publish=False)

    def poll(self) -> None:
        """주기적으로 호출. 송출 프로세스가 스스로 죽었는지 확인한다."""
        crashed_now = self.switch.check_exit()
        self.sync(publish=crashed_now)

    def sync(self, *, publish: bool) -> None:
        with self._lock:
            current = (self.switch.is_on, self.switch.crashed)
            changed = current != self._shown
            if changed:
                self._shown = current
                is_on, crashed = current
                if is_on:
                    self.led.on()
                elif crashed:
                    self.led.blink(BLINK_ON_SEC, BLINK_OFF_SEC)
                else:
                    self.led.off()
        if publish and changed:
            self._publish_state()

    def close(self) -> None:
        self.led.off()
        self.led.close()


class GpioButton:
    """풀업 입력 버튼. 버튼 한쪽은 GPIO 핀, 다른 쪽은 GND에 연결한다(외부 저항 불필요)."""

    def __init__(self, pin: int, on_press: Callable[[], None]) -> None:
        from gpiozero import Button  # Pi가 아닌 환경에서 import 오류를 피하려고 지연 import

        self._button = Button(pin, pull_up=True, bounce_time=BUTTON_BOUNCE_SEC)
        self._button.when_pressed = on_press

    def close(self) -> None:
        self._button.close()


def gpio_led(pin: int) -> Indicator:
    from gpiozero import LED

    return LED(pin)
