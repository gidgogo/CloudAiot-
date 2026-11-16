"""영상 송출(edge.main --stream)을 켜고 끄는 스위치.

``command_handler.Switch`` 인터페이스(is_on, set)를 따르므로 MQTT 원격 명령(CommandHandler)으로도 켜고 끌 수 있다. ON이면 송출 프로세스를 자식 프로세스로 띄우고, OFF면 Ctrl+C(SIGINT)로 정리 종료한다.

송출 프로세스가 스스로 죽으면(카메라 오류, 설정 오류 등) 다시 띄우지 않고 ``crashed``로 표시한다.
같은 오류로 무한 재시작하는 것보다 LED로 알리고 사람이 다시 켜게 하는 편이 안전하다.
네트워크 끊김은 edge.main이 스스로 재접속하므로 여기서 다루지 않는다.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Sequence

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STOP_TIMEOUT_SEC = 8.0


def default_stream_command(*, mock: bool = False) -> list[str]:
    """제어 프로세스와 같은 파이썬(가상환경)으로 송출을 실행한다. mock이면 카메라 없이 테스트 패턴을 보낸다."""
    command = [sys.executable, "-m", "edge.main", "--stream"]
    if mock:
        command += ["--source", "synthetic"]
    return command


class ProcessSwitch:
    def __init__(
        self,
        name: str,
        command: Sequence[str],
        *,
        cwd: Path | str = REPO_ROOT,
        env: dict[str, str] | None = None,
        stop_timeout_sec: float = DEFAULT_STOP_TIMEOUT_SEC,
        popen: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.name = name
        self.command = list(command)
        self.cwd = str(cwd)
        self.env = env
        self.stop_timeout_sec = stop_timeout_sec
        self._popen = popen
        self._proc: Any = None
        self._crashed = False
        self._lock = threading.RLock()  # MQTT 스레드와 버튼(gpiozero) 스레드가 동시에 부를 수 있다

    @property
    def is_on(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    @property
    def crashed(self) -> bool:
        """켜 둔 송출이 스스로 종료됐는지. ``check_exit()``가 갱신하고, 다시 켜거나 끄면 지워진다."""
        with self._lock:
            return self._crashed

    def set(self, on: bool) -> None:
        with self._lock:
            if on:
                self._start()
            else:
                self._stop()

    def toggle(self) -> bool:
        """현재 상태를 뒤집고 바뀐 상태를 돌려준다 (버튼용)."""
        with self._lock:
            self.set(not self.is_on)
            return self.is_on

    def check_exit(self) -> bool:
        """켜져 있어야 할 프로세스가 끝났으면 crashed로 표시하고 True를 돌려준다. 주기적으로 호출한다."""
        with self._lock:
            if self._proc is None or self._proc.poll() is None:
                return False
            log.warning("[%s] stream process exited by itself (code %s)", self.name, self._proc.returncode)
            self._proc = None
            self._crashed = True
            return True

    def close(self) -> None:
        self.set(False)

    def _start(self) -> None:
        if self.is_on:
            return
        self._crashed = False
        env = None if self.env is None else {**os.environ, **self.env}
        log.info("[%s] starting stream: %s", self.name, " ".join(self.command))
        # stdout/stderr는 그대로 물려받아 systemd 저널(journalctl)에 함께 남는다
        self._proc = self._popen(self.command, cwd=self.cwd, env=env)

    def _stop(self) -> None:
        self._crashed = False
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        log.info("[%s] stopping stream", self.name)
        proc.send_signal(signal.SIGINT)  # edge.main은 Ctrl+C를 받으면 메트릭을 남기고 카메라를 닫는다
        try:
            proc.wait(timeout=self.stop_timeout_sec)
        except subprocess.TimeoutExpired:
            log.warning("[%s] stream did not stop in %.0fs; killing", self.name, self.stop_timeout_sec)
            proc.kill()
            proc.wait(timeout=self.stop_timeout_sec)
