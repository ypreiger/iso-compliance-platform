"""Model-as-a-Service configuration for the doc-agent.

Each task maps to an independently configurable LLM endpoint.
This allows choosing the best (or cheapest) model per task and
switching between OpenAI, OpenShift AI (vLLM), Ollama, or any
OpenAI-compatible endpoint without code changes.

Env vars follow the pattern:
    {TASK}_MODEL_URL   — base URL  (default: OPENAI_API_BASE or openai.com)
    {TASK}_MODEL_NAME  — model id  (default per task)
    {TASK}_MODEL_KEY   — API key   (falls back to OPENAI_API_KEY / LLM_API_KEY)

Tasks: PARSE, EXTRACT, TRANSLATE, GENERATE
"""
from __future__ import annotations

import os
from functools import lru_cache


_OPENAI_DEFAULT = "https://api.openai.com/v1"


def _read_token_file() -> str:
    path = os.getenv("MAAS_BEARER_TOKEN_FILE", "").strip()
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _url(task: str) -> str:
    return (
        os.getenv(f"{task}_MODEL_URL")
        or os.getenv("LLM_GATEWAY_URL")
        or os.getenv("OPENAI_API_BASE")
        or _OPENAI_DEFAULT
    ).rstrip("/")


def _key(task: str) -> str:
    return (
        os.getenv(f"{task}_MODEL_KEY")
        or os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or _read_token_file()
        or ""
    )


def _model(task: str, default: str) -> str:
    return os.getenv(f"{task}_MODEL_NAME") or os.getenv("LLM_MODEL_MAPPING") or default


@lru_cache(maxsize=1)
def get_model_config() -> dict[str, dict[str, str]]:
    """Return resolved model configuration for every task."""
    return {
        # Structured document parsing (PDF/DOC/DOCX → clauses or findings)
        "parse": {
            "url": _url("PARSE"),
            "key": _key("PARSE"),
            "model": _model("PARSE", "gpt-4o"),
        },
        # ISO clause extraction from pre-parsed text
        "extract": {
            "url": _url("EXTRACT"),
            "key": _key("EXTRACT"),
            "model": _model("EXTRACT", "gpt-4o"),
        },
        # EN ↔ HE translation
        "translate": {
            "url": _url("TRANSLATE"),
            "key": _key("TRANSLATE"),
            "model": _model("TRANSLATE", "gpt-4o"),
        },
        # Narrative generation for reports (cheaper model is fine)
        "generate": {
            "url": _url("GENERATE"),
            "key": _key("GENERATE"),
            "model": _model("GENERATE", "gpt-4o-mini"),
        },
    }
