"""BGE-M3 embedding client used for RAG index + query (instrumented)."""
from __future__ import annotations

import os
from typing import List

import httpx

from app.observability.model_metrics import track_model_call, usage_from_response


def get_embedding_url() -> str:
    return (
        os.getenv("LLM_EMBED_URL")
        or os.getenv("LLM_GATEWAY_URL", "").replace("/v1", "")
        or ""
    ).rstrip("/")


def get_embed_model() -> str:
    return os.getenv("LLM_MODEL_EMBED", "bge-m3")


def _read_maas_token() -> str:
    path = os.getenv("MAAS_BEARER_TOKEN_FILE", "").strip()
    if not path:
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _embedding_headers() -> dict[str, str]:
    # In-cluster BGE needs no auth; MaaS path needs projected SA token.
    key = (
        _read_maas_token()
        or os.getenv("MAAS_API_KEY", "").strip()
        or os.getenv("EMBED_API_KEY", "").strip()
    )
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def embeddings_configured() -> bool:
    """True when an embed endpoint is available (not SQLite dry-run)."""
    if os.getenv("USE_SQLITE", "0") == "1":
        return False
    url = get_embedding_url()
    return bool(url) and url != "https://REPLACE-maas-or-gateway"


def embeddings_enabled() -> bool:
    """Whether to write embeddings during RAG index (upload/translate)."""
    if not embeddings_configured():
        return False
    if os.getenv("RAG_EMBED_ON_INDEX", "1").strip().lower() in ("0", "false", "no"):
        return False
    return True


def generate_embeddings(texts: List[str], *, task: str = "embed") -> List[List[float]]:
    """Embed texts via BGE-M3. Returns zero-vectors on failure (same length)."""
    if not texts:
        return []

    url = get_embedding_url()
    model = get_embed_model()
    dim = 1024
    zeros = [[0.0] * dim for _ in texts]
    if not url or url == "https://REPLACE-maas-or-gateway":
        return zeros

    endpoint = f"{url}/v1/embeddings"
    with track_model_call(task=task, model=model) as ctx:
        try:
            response = httpx.post(
                endpoint,
                headers=_embedding_headers(),
                json={"input": texts, "model": model},
                timeout=120.0,
            )
            if response.status_code == 429:
                ctx["status"] = "rate_limited"
                return zeros
            response.raise_for_status()
            data = response.json()
            prompt, completion, total = usage_from_response(data)
            ctx["prompt_tokens"] = prompt
            ctx["completion_tokens"] = completion
            ctx["total_tokens"] = total or sum(max(1, len(t.split())) for t in texts)
            ctx["model"] = data.get("model") or model
            vectors = [item["embedding"] for item in data["data"]]
            if len(vectors) != len(texts):
                ctx["status"] = "error"
                return zeros
            return vectors
        except Exception:
            ctx["status"] = "error"
            return zeros


def generate_embedding(text: str, *, task: str = "embed_query") -> List[float]:
    vectors = generate_embeddings([text], task=task)
    return vectors[0] if vectors else [0.0] * 1024


def is_zero_vector(vec: List[float] | None) -> bool:
    if not vec:
        return True
    return all(abs(x) < 1e-12 for x in vec[:8])
