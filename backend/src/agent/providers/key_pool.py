"""Primary and fallback API key rotation.

A quota or auth failure on one key retires it for a cool-down period and the
call retries on the next. Exhausting the pool is a 503 with a retry hint, not a
500: the request was well-formed and will likely succeed later.

State is per-process, which is correct for a single instance and wrong for
several. That limitation is recorded in the README rather than papered over;
Redis would be the fix.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

DEFAULT_COOLDOWN_SECONDS = 300.0


@dataclass
class _KeyState:
    value: str
    cooling_until: float = 0.0
    failure_count: int = field(default=0)

    def is_available(self, now: float) -> bool:
        return now >= self.cooling_until


class NoKeysAvailableError(RuntimeError):
    pass


class GeminiKeyPool:
    def __init__(
        self,
        keys: list[str],
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        if not keys:
            raise ValueError("A key pool requires at least one key.")
        self._keys = [_KeyState(value=key) for key in keys]
        self._cooldown_seconds = cooldown_seconds

    @property
    def size(self) -> int:
        return len(self._keys)

    def available_keys(self, now: float | None = None) -> list[str]:
        moment = now if now is not None else time.monotonic()
        return [key.value for key in self._keys if key.is_available(moment)]

    def acquire(self, exclude: set[str] | None = None) -> str:
        """Return the highest-priority key that is neither cooling nor excluded.

        `exclude` carries the keys already tried within this one request, so a
        retry never lands on the key that just failed.
        """
        excluded = exclude or set()
        now = time.monotonic()

        for key in self._keys:
            if key.value not in excluded and key.is_available(now):
                return key.value

        raise NoKeysAvailableError("Every configured API key is cooling down or exhausted.")

    def report_failure(self, key_value: str) -> None:
        for key in self._keys:
            if key.value == key_value:
                key.failure_count += 1
                key.cooling_until = time.monotonic() + self._cooldown_seconds
                return

    def report_success(self, key_value: str) -> None:
        for key in self._keys:
            if key.value == key_value:
                key.failure_count = 0
                key.cooling_until = 0.0
                return
