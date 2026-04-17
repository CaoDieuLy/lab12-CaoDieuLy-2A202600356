"""Rate limiting using Redis sliding window with local fallback."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

import redis
from fastapi import HTTPException

from app.config import settings

_local_windows: dict[str, deque[float]] = defaultdict(deque)


def _redis_client() -> redis.Redis | None:
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _check_local(user_id: str) -> None:
    now = time.time()
    window = _local_windows[user_id]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)


def _check_redis(user_id: str, client: redis.Redis) -> None:
    now = time.time()
    key = f"rate:{user_id}"
    pipeline = client.pipeline()
    pipeline.zremrangebyscore(key, 0, now - 60)
    pipeline.zadd(key, {f"{now}:{uuid.uuid4()}": now})
    pipeline.zcard(key)
    pipeline.expire(key, 120)
    _, _, count, _ = pipeline.execute()
    if int(count) > settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def check_rate_limit(user_id: str) -> None:
    client = _redis_client()
    if client:
        _check_redis(user_id, client)
        return
    _check_local(user_id)
