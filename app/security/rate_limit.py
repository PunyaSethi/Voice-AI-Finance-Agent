from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.config import get_settings


@dataclass
class _RateBucket:
    timestamps: deque[float]


_buckets: dict[str, _RateBucket] = defaultdict(lambda: _RateBucket(deque()))
_lock = Lock()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client and client.host else "unknown"


def rate_limit_request(request: Request) -> None:
    settings = get_settings()
    if settings.rate_limit_per_minute <= 0:
        return

    key = f"{_client_key(request)}:{request.url.path}"
    now = monotonic()
    window = 60.0

    with _lock:
        for bucket_key, bucket in list(_buckets.items()):
            while bucket.timestamps and now - bucket.timestamps[0] > window:
                bucket.timestamps.popleft()
            if not bucket.timestamps:
                _buckets.pop(bucket_key, None)

        bucket = _buckets[key]
        while bucket.timestamps and now - bucket.timestamps[0] > window:
            bucket.timestamps.popleft()

        if len(bucket.timestamps) >= settings.rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

        bucket.timestamps.append(now)
