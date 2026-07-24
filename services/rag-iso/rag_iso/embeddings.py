"""Generate embeddings using BGE-M3 for RAG documents."""
from __future__ import annotations

import os
from typing import List
import httpx


def get_embedding_url() -> str:
    """Get BGE-M3 embedding endpoint URL."""
    return os.getenv(
        "LLM_EMBED_URL",
        "https://bge-m3-llm.apps.ocp.7hrxw.sandbox880.opentlc.com"
    )


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using BGE-M3.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    url = get_embedding_url()
    endpoint = f"{url}/v1/embeddings"

    try:
        response = httpx.post(
            endpoint,
            json={"input": texts},
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()

        # Extract embeddings from OpenAI-compatible response
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    except Exception as e:
        print(f"Error generating embeddings: {e}")
        # Return zero vectors as fallback
        return [[0.0] * 1024 for _ in texts]  # BGE-M3 outputs 1024-dim vectors


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text string to embed

    Returns:
        Embedding vector (list of floats)
    """
    embeddings = generate_embeddings([text])
    return embeddings[0] if embeddings else [0.0] * 1024
