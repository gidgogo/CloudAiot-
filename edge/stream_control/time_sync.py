"""NTP 동기화 여부 확인 (공통 인터페이스 11.7).

Raspberry Pi OS는 systemd-timesyncd로 시간을 맞춘다. ``timedatectl``이 동기화됐다고 답할 때만 True다.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time

log = logging.getLogger(__name__)

CACHE_SEC = 30.0  # 명령마다 프로세스를 띄우지 않도록 결과를 잠시 재사용한다


class NtpSyncChecker:
    def __init__(self, cache_sec: float = CACHE_SEC) -> None:
        self._cache_sec = cache_sec
        self._checked_at = float("-inf")
        self._synced = False
        self._warned = False

    def __call__(self) -> bool:
        now = time.monotonic()
        if now - self._checked_at < self._cache_sec:
            return self._synced
        self._checked_at = now
        self._synced = self._query()
        return self._synced

    def _query(self) -> bool:
        if shutil.which("timedatectl") is None:
            if not self._warned:
                log.warning("timedatectl not found; treating clock as NOT synchronized")
                self._warned = True
            return False
        try:
            out = subprocess.run(
                ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                capture_output=True, text=True, timeout=2, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return out.stdout.strip() == "yes"
