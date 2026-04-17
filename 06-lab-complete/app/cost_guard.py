"""Monthly budget guard per user."""
from __future__ import annotations

from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings

_memory_budget: dict[str, float] = {}


def _redis_client() -> redis.Redis | None:
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _budget_key(user_id: str) -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"budget:{user_id}:{month}"


def _check_local(user_id: str, estimated_cost: float) -> None:
    key = _budget_key(user_id)
    current = _memory_budget.get(key, 0.0)
    if current + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Monthly budget exceeded")
    _memory_budget[key] = current + estimated_cost


def _check_redis(user_id: str, estimated_cost: float, client: redis.Redis) -> None:
    key = _budget_key(user_id)
    current = float(client.get(key) or 0.0)
    if current + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Monthly budget exceeded")
    client.incrbyfloat(key, estimated_cost)
    client.expire(key, 60 * 60 * 24 * 40)


def check_budget(user_id: str, estimated_cost: float) -> None:
    client = _redis_client()
    if client:
        _check_redis(user_id, estimated_cost, client)
        return
    _check_local(user_id, estimated_cost)
