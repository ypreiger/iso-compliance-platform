"""Thin async LLM client — OpenAI-compatible chat completions.

Works with:
  - OpenAI API (api.openai.com)
  - OpenShift AI / vLLM (any OpenAI-compatible endpoint)
  - Ollama  (/v1/chat/completions)
  - LiteLLM proxy
  - Azure OpenAI

Usage:
    result = await llm_call(
        task="parse",
        messages=[{"role": "user", "content": "..."}],
        temperature=0,
        response_format="json",
    )
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from app.config import get_model_config

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


async def llm_call(
    task: str,
    messages: list[dict],
    *,
    temperature: float = 0,
    response_format: str = "json",  # "json" | "text"
    retries: int = 3,
    timeout: float = 180.0,
    max_tokens: int = 4096,
    reasoning_effort: str = "low",
) -> str:
    """Call the LLM for a given task; return the content string."""
    cfg = get_model_config()[task]
    url = f"{cfg['url']}/chat/completions"
    key = cfg["key"]
    model = cfg["model"]

    if not key:
        raise LLMError(f"No API key configured for task '{task}'. Set {task.upper()}_MODEL_KEY or OPENAI_API_KEY.")

    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # gpt-oss / reasoning models: low effort cuts wall time dramatically
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    # json_object mode is supported by OpenAI and most vLLM builds
    if response_format == "json":
        payload["response_format"] = {"type": "json_object"}

    from app.model_metrics import track_model_call, usage_from_response

    last_exc: Exception | None = None
    for attempt in range(retries):
        with track_model_call(task=task, model=model) as mctx:
            try:
                # Disable SSL verification for internal cluster HTTPS (self-signed certs)
                async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                    resp = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json=payload,
                    )
                    if resp.status_code == 429:
                        mctx["status"] = "rate_limited"
                        wait = 5 * (attempt + 1)
                        log.warning("LLM rate-limited (task=%s); retry in %ds", task, wait)
                        time.sleep(wait)
                        continue
                    if resp.status_code >= 400:
                        mctx["status"] = "error"
                        body = resp.text[:400]
                        raise LLMError(f"LLM API {resp.status_code} (task={task}): {body}")
                    data = resp.json()
                    prompt_t, completion_t, total_t = usage_from_response(data)
                    mctx["prompt_tokens"] = prompt_t
                    mctx["completion_tokens"] = completion_t
                    mctx["total_tokens"] = total_t
                    mctx["model"] = data.get("model") or model
                    # Handle both standard and reasoning model responses (gpt-oss may
                    # return content=null when max_tokens is consumed by reasoning).
                    message = data["choices"][0]["message"]
                    content = (
                        message.get("content")
                        or message.get("reasoning_content")
                        or message.get("reasoning")
                        or ""
                    )
                    if not str(content).strip():
                        mctx["status"] = "empty"
                        raise LLMError(
                            f"LLM returned empty content (task={task}, "
                            f"finish={data['choices'][0].get('finish_reason')})"
                        )
                    return content
            except LLMError:
                if mctx.get("status") == "ok":
                    mctx["status"] = "error"
                raise
            except (httpx.HTTPError, KeyError) as exc:
                mctx["status"] = "error"
                last_exc = exc
                log.warning("LLM attempt %d/%d failed (task=%s): %s", attempt + 1, retries, task, exc)
                time.sleep(2 ** attempt)

    raise LLMError(f"LLM call failed after {retries} attempts (task={task}): {last_exc}")


def parse_json_response(raw: str) -> list | dict:
    """Parse LLM response; handle both bare JSON and markdown-wrapped JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # gpt-oss often truncates long Hebrew JSON; salvage a clauses array if present.
        start = raw.find("[")
        if start < 0:
            start = raw.find("{")
        if start >= 0:
            snippet = raw[start:]
            # Close truncated structures conservatively.
            if snippet.lstrip().startswith("["):
                snippet = snippet + "]"
            else:
                # Truncated object/array under {"clauses":[...
                if '"clauses"' in snippet and "[" in snippet:
                    snippet = snippet.rstrip().rstrip(",") + "]}"
                else:
                    snippet = snippet.rstrip().rstrip(",") + "}"
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass
        raise
