"""Prometheus metrics for every application model call (chat + embeddings)."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Labels: model = served model id, task = parse|translate|embed|extract|...,
# status = ok|error|empty|rate_limited
REQUESTS = Counter(
    "iso_app_model_requests_total",
    "Application model invocations (chat or embeddings)",
    ["service", "task", "model", "status"],
)
TOKENS = Counter(
    "iso_app_model_tokens_total",
    "Tokens reported by model responses (prompt/completion/total)",
    ["service", "task", "model", "token_type"],
)
LATENCY = Histogram(
    "iso_app_model_latency_seconds",
    "Model call latency",
    ["service", "task", "model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

SERVICE = "iso-api"


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
) -> None:
    model_l = (model or "unknown").strip() or "unknown"
    task_l = (task or "unknown").strip() or "unknown"
    status_l = (status or "unknown").strip() or "unknown"
    REQUESTS.labels(service=service, task=task_l, model=model_l, status=status_l).inc()
    LATENCY.labels(service=service, task=task_l, model=model_l).observe(max(0.0, latency_s))
    if prompt_tokens:
        TOKENS.labels(
            service=service, task=task_l, model=model_l, token_type="prompt"
        ).inc(prompt_tokens)
    if completion_tokens:
        TOKENS.labels(
            service=service, task=task_l, model=model_l, token_type="completion"
        ).inc(completion_tokens)
    if total_tokens:
        TOKENS.labels(
            service=service, task=task_l, model=model_l, token_type="total"
        ).inc(total_tokens)
    elif prompt_tokens or completion_tokens:
        TOKENS.labels(
            service=service, task=task_l, model=model_l, token_type="total"
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
) -> Iterator[dict]:
    """Context manager that records metrics when the block exits.

    Caller may set ``ctx["status"]``, ``ctx["prompt_tokens"]``, etc.
    """
    ctx: dict = {
        "status": "ok",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model": model,
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
        )


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
