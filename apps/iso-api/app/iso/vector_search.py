"""Vector similarity search for ISO clauses using BGE-M3 embeddings."""
from __future__ import annotations

import os
from typing import List, Dict, Any, Optional
import httpx


def get_embedding_url() -> str:
    """Get BGE-M3 embedding endpoint URL."""
    return os.getenv(
        "LLM_EMBED_URL",
        os.getenv("LLM_GATEWAY_URL", "").replace("/v1", "")  # Fallback
    )


def generate_query_embedding(query: str) -> List[float]:
    """Generate embedding for search query."""
    url = get_embedding_url()
    if not url or url == "https://REPLACE-maas-or-gateway":
        # Return zero vector if not configured
        return [0.0] * 1024

    endpoint = f"{url}/v1/embeddings"

    try:
        response = httpx.post(
            endpoint,
            json={"input": query},
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating query embedding: {e}")
        return [0.0] * 1024


def search_similar_chunks(
    conn,
    query: str,
    limit: int = 10,
    standard: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for similar document chunks using vector similarity.

    Args:
        conn: Database connection
        query: Search query text
        limit: Number of results to return
        standard: Filter by ISO standard (e.g., "ISO9001")
        language: Filter by language (e.g., "en", "he")

    Returns:
        List of matching chunks with similarity scores
    """
    # Generate query embedding
    query_embedding = generate_query_embedding(query)

    # Build WHERE clause for filters
    filters = []
    params = [query_embedding, limit]

    if standard:
        filters.append("metadata->>'standard' = %s")
        params.insert(-1, standard.upper())

    if language:
        filters.append("metadata->>'language' = %s")
        params.insert(-1, language)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    # Search using cosine similarity
    sql = f"""
        SELECT
            id,
            collection_id,
            source_path,
            chunk_index,
            content,
            metadata,
            1 - (embedding <=> %s::vector) as similarity
        FROM rag_documents
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    # Execute search
    cursor = conn.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            "id": row[0],
            "collection_id": row[1],
            "source_path": row[2],
            "chunk_index": row[3],
            "content": row[4],
            "metadata": row[5],
            "similarity": float(row[6]),
        })

    return results
