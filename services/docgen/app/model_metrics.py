"""Prometheus metrics for docgen model calls."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS = Counter(
    "iso_app_model_requests_total",
    "Application model invocations (chat or embeddings)",
    ["service", "task", "model", "status", "user"],
)
TOKENS = Counter(
    "iso_app_model_tokens_total",
    "Tokens reported by model responses (prompt/completion/total)",
    ["service", "task", "model", "token_type", "user"],
)
LATENCY = Histogram(
    "iso_app_model_latency_seconds",
    "Model call latency",
    ["service", "task", "model", "user"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

SERVICE = "iso-docgen"


def metrics_user() -> str:
    return (os.getenv("ISO_APP_METRICS_USER") or "iso-api").strip() or "iso-api"


def usage_from_response(data: dict | None) -> tuple[int, int, int]:
    if not isinstance(data, dict):
        return 0, 0, 0
    usage = data.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion) or 0)
    return prompt, completion, total


@contextmanager
def track_model_call(*, task: str, model: str) -> Iterator[dict]:
    user = metrics_user()
    ctx: dict = {
        "status": "ok",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model": model,
        "user": user,
    }
    started = time.perf_counter()
    try:
        yield ctx
    except Exception:
        if ctx.get("status") == "ok":
            ctx["status"] = "error"
        raise
    finally:
        model_l = str(ctx.get("model") or model or "unknown")
        task_l = task or "unknown"
        status_l = str(ctx.get("status") or "ok")
        user_l = str(ctx.get("user") or user)
        REQUESTS.labels(
            service=SERVICE, task=task_l, model=model_l, status=status_l, user=user_l
        ).inc()
        LATENCY.labels(
            service=SERVICE, task=task_l, model=model_l, user=user_l
        ).observe(max(0.0, time.perf_counter() - started))
        prompt = int(ctx.get("prompt_tokens") or 0)
        completion = int(ctx.get("completion_tokens") or 0)
        total = int(ctx.get("total_tokens") or 0)
        if prompt:
            TOKENS.labels(
                service=SERVICE,
                task=task_l,
                model=model_l,
                token_type="prompt",
                user=user_l,
            ).inc(prompt)
        if completion:
            TOKENS.labels(
                service=SERVICE,
                task=task_l,
                model=model_l,
                token_type="completion",
                user=user_l,
            ).inc(completion)
        if total or prompt or completion:
            TOKENS.labels(
                service=SERVICE,
                task=task_l,
                model=model_l,
                token_type="total",
                user=user_l,
            ).inc(total or (prompt + completion))


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
