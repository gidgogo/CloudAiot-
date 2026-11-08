"""사용자 계정과 비밀번호를 검증한다.

비밀번호는 bcrypt 해시로만 저장한다. bcrypt는 72바이트까지만 사용하므로
더 긴 비밀번호는 잘리지 않도록 거부한다.
"""

from __future__ import annotations

import threading
import time
from functools import lru_cache

import bcrypt

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72
BCRYPT_ROUNDS = 12  # 테스트에서만 낮춘다.


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"비밀번호는 {MAX_PASSWORD_BYTES}바이트 이하여야 합니다.")


def hash_password(password: str) -> str:
    validate_password(password)
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)
    ).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
    except ValueError:
        return False


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(BCRYPT_ROUNDS)).decode(
        "ascii"
    )


def burn_verification_time(password: str) -> None:
    """없는 계정도 같은 시간이 걸리게 해 계정 존재 여부가 드러나지 않게 한다."""
    verify_password(password, _dummy_hash())


class LoginRateLimiter:
    """같은 계정·주소에서 연속 실패하면 일정 시간 로그인을 막는다(메모리 저장)."""

    def __init__(self, max_attempts: int = 5, lock_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        """기간이 지난 실패 기록을 버린다. 남은 기록이 없으면 키를 지워 메모리가 늘지 않게 한다."""
        attempts = [
            t for t in self._failures.get(key, ()) if now - t < self.lock_seconds
        ]
        if attempts:
            self._failures[key] = attempts
        else:
            self._failures.pop(key, None)
        return attempts

    def is_locked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._failures[key] = [*self._recent(key, now), now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
