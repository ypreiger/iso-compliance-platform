"""Prometheus metrics for every application model call (chat + embeddings)."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Labels aligned with MaaS authorized_hits so Grafana can merge panels:
#   user  — synthetic caller id (default iso-api) for User filter
#   model — served model id (bge-m3, gpt-oss-20b, …)
#   task  — parse|translate|embed_index|embed_query|extract|…
#   status — ok|error|empty|rate_limited
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

SERVICE = "iso-api"


def metrics_user() -> str:
    """User label for Grafana filters (matches MaaS authorized_hits.user)."""
    return (os.getenv("ISO_APP_METRICS_USER") or "iso-api").strip() or "iso-api"


def record_model_call(
    *,
    task: str,
    model: str,
    status: str,
    latency_s: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    service: str = SERVICE,
    user: str | None = None,
) -> None:
    model_l = (model or "unknown").strip() or "unknown"
    task_l = (task or "unknown").strip() or "unknown"
    status_l = (status or "unknown").strip() or "unknown"
    user_l = (user or metrics_user()).strip() or "iso-api"
    REQUESTS.labels(
        service=service, task=task_l, model=model_l, status=status_l, user=user_l
    ).inc()
    LATENCY.labels(
        service=service, task=task_l, model=model_l, user=user_l
    ).observe(max(0.0, latency_s))
    if prompt_tokens:
        TOKENS.labels(
            service=service,
            task=task_l,
            model=model_l,
            token_type="prompt",
            user=user_l,
        ).inc(prompt_tokens)
    if completion_tokens:
        TOKENS.labels(
            service=service,
            task=task_l,
            model=model_l,
            token_type="completion",
            user=user_l,
        ).inc(completion_tokens)
    if total_tokens:
        TOKENS.labels(
            service=service,
            task=task_l,
            model=model_l,
            token_type="total",
            user=user_l,
        ).inc(total_tokens)
    elif prompt_tokens or completion_tokens:
        TOKENS.labels(
            service=service,
            task=task_l,
            model=model_l,
            token_type="total",
            user=user_l,
        ).inc(prompt_tokens + completion_tokens)


def usage_from_response(data: dict | None) -> tuple[int, int, int]:
    if not isinstance(data, dict):
        return 0, 0, 0
    usage = data.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion) or 0)
    return prompt, completion, total


@contextmanager
def track_model_call(
    *,
    task: str,
    model: str,
    service: str = SERVICE,
    user: str | None = None,
) -> Iterator[dict]:
    """Context manager that records metrics when the block exits."""
    ctx: dict = {
        "status": "ok",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model": model,
        "user": user or metrics_user(),
    }
    started = time.perf_counter()
    try:
        yield ctx
    except Exception:
        if ctx.get("status") == "ok":
            ctx["status"] = "error"
        raise
    finally:
        record_model_call(
            task=task,
            model=str(ctx.get("model") or model),
            status=str(ctx.get("status") or "ok"),
            latency_s=time.perf_counter() - started,
            prompt_tokens=int(ctx.get("prompt_tokens") or 0),
            completion_tokens=int(ctx.get("completion_tokens") or 0),
            total_tokens=int(ctx.get("total_tokens") or 0),
            service=service,
            user=str(ctx.get("user") or metrics_user()),
        )


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
