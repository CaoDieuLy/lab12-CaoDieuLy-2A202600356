"""Production-ready FastAPI agent for Day 12 final lab."""
from __future__ import annotations

import json
import logging
import signal
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget
from app.rate_limiter import check_rate_limit
from utils.mock_llm import ask as llm_ask


logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(message)s")
logger = logging.getLogger("agent")

START_TIME = time.time()
IS_READY = False
IS_SHUTTING_DOWN = False
REQUEST_COUNT = 0
ERROR_COUNT = 0

_memory_history: dict[str, list[str]] = defaultdict(list)


def _get_redis_client() -> redis.Redis | None:
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def _log(event: str, **payload: object) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **payload,
    }
    logger.info(json.dumps(record, ensure_ascii=True))


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def load_history(user_id: str) -> list[str]:
    client = _get_redis_client()
    if client:
        return client.lrange(_history_key(user_id), 0, -1)
    return _memory_history[user_id]


def append_history(user_id: str, line: str) -> None:
    client = _get_redis_client()
    if client:
        key = _history_key(user_id)
        client.rpush(key, line)
        client.ltrim(key, -20, -1)
        client.expire(key, 60 * 60 * 24 * 7)
        return
    _memory_history[user_id].append(line)
    _memory_history[user_id] = _memory_history[user_id][-20:]


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    timestamp: str
    history_items: int


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global IS_READY
    _log("startup", app=settings.app_name, env=settings.environment, version=settings.app_version)
    IS_READY = True
    yield
    IS_READY = False
    _log("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global REQUEST_COUNT, ERROR_COUNT
    REQUEST_COUNT += 1
    started = time.time()
    try:
        response: Response = await call_next(request)
    except Exception:
        ERROR_COUNT += 1
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    elapsed_ms = round((time.time() - started) * 1000, 2)
    _log("request", method=request.method, path=request.url.path, status=response.status_code, ms=elapsed_ms)
    return response


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics",
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "requests": REQUEST_COUNT,
        "errors": ERROR_COUNT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    if IS_SHUTTING_DOWN:
        raise HTTPException(status_code=503, detail="Shutting down")
    if not IS_READY:
        raise HTTPException(status_code=503, detail="Not ready")
    if not _get_redis_client():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.post("/ask", response_model=AskResponse)
def ask_agent(body: AskRequest, _api_key: str = Depends(verify_api_key)):
    if IS_SHUTTING_DOWN:
        raise HTTPException(status_code=503, detail="Service is shutting down")

    check_rate_limit(body.user_id)

    estimated_cost = max(len(body.question) / 10000.0, 0.0005)
    check_budget(body.user_id, estimated_cost)

    history = load_history(body.user_id)
    prompt = body.question
    if history:
        context = "\n".join(history[-6:])
        prompt = f"Conversation context:\n{context}\n\nUser: {body.question}"

    answer = llm_ask(prompt)
    append_history(body.user_id, f"user: {body.question}")
    append_history(body.user_id, f"assistant: {answer}")

    _log("agent_call", user_id=body.user_id, history_items=len(history), question_length=len(body.question))

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        history_items=len(load_history(body.user_id)),
    )


@app.get("/metrics")
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "requests": REQUEST_COUNT,
        "errors": ERROR_COUNT,
        "environment": settings.environment,
    }


def _handle_sigterm(signum, _frame):
    global IS_SHUTTING_DOWN
    IS_SHUTTING_DOWN = True
    _log("signal", signal=signum, text="SIGTERM received")


signal.signal(signal.SIGTERM, _handle_sigterm)


if __name__ == "__main__":
    _log("boot", host=settings.host, port=settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
