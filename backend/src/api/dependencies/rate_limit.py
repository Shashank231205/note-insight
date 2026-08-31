"""Per-user rate limiting on the analysis endpoint.

The scarce resource here is free-tier Gemini quota, so the limit sits on the
one endpoint that spends it. A token bucket rather than a fixed window: it
allows a short burst (a clinician analysing three notes back to back) without
permitting sustained abuse.

State is per-process. Correct for one Render instance, wrong for several; the
README records that, and Redis is the fix.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import Depends, Request

from src.api.dependencies.settings import get_request_settings
from src.core.config import Settings
from src.core.errors import RateLimitedError
from src.models.user import AuthenticatedUser

LIMITER_STATE_KEY = "analysis_rate_limiter"


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    def __init__(self, capacity: int, refill_per_hour: int) -> None:
        self._capacity = float(capacity)
        self._refill_per_second = refill_per_hour / 3600.0
        self._buckets: dict[str, _Bucket] = {}

    def check(self, key: str, now: float | None = None) -> None:
        moment = now if now is not None else time.monotonic()
        bucket = self._buckets.get(key)

        if bucket is None:
            self._buckets[key] = _Bucket(tokens=self._capacity - 1.0, updated_at=moment)
            return

        elapsed = max(0.0, moment - bucket.updated_at)
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
        bucket.updated_at = moment

        if bucket.tokens < 1.0:
            missing = 1.0 - bucket.tokens
            retry_after = int(missing / self._refill_per_second) + 1
            raise RateLimitedError(retry_after_seconds=retry_after)

        bucket.tokens -= 1.0


def get_rate_limiter(
    request: Request,
    settings: Settings = Depends(get_request_settings),
) -> TokenBucketRateLimiter:
    existing = getattr(request.app.state, LIMITER_STATE_KEY, None)
    if isinstance(existing, TokenBucketRateLimiter):
        return existing

    limiter = TokenBucketRateLimiter(
        capacity=settings.analysis_rate_limit_burst,
        refill_per_hour=settings.analysis_rate_limit_per_hour,
    )
    setattr(request.app.state, LIMITER_STATE_KEY, limiter)
    return limiter


def enforce_analysis_rate_limit(
    caller: AuthenticatedUser,
    limiter: TokenBucketRateLimiter,
) -> None:
    limiter.check(caller.uid)
