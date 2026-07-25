"""Vector similarity search for ISO clauses using BGE-M3 embeddings."""
from __future__ import annotations

from typing import List, Dict, Any, Optional

from app.iso.embeddings import generate_embedding, is_zero_vector


def generate_query_embedding(query: str) -> List[float]:
    """Generate embedding for search query (instrumented)."""
    return generate_embedding(query, task="embed_query")


def search_similar_chunks(
    conn,
    query: str,
    limit: int = 10,
    standard: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for similar document chunks using vector similarity.

    ``standard`` is required so clause indexes never mix across ISO standards.
    """
    if not standard:
        raise ValueError("standard is required — vector search must be scoped to one ISO standard")

    from app.iso.rag_index import LEGACY_COLLECTION_ID, collection_id_for_standard, normalize_standard_id

    std = normalize_standard_id(standard)
    coll = collection_id_for_standard(std)

    query_embedding = generate_query_embedding(query)
    if is_zero_vector(query_embedding):
        return []

    filters = [
        "(collection_id = %s OR (collection_id = %s AND metadata->>'standard' = %s))",
        "metadata->>'standard' = %s",
        "embedding IS NOT NULL",
    ]
    filter_params: list = [coll, LEGACY_COLLECTION_ID, std, std]

    if language:
        filters.append("metadata->>'language' = %s")
        filter_params.append(language)

    where_clause = "WHERE " + " AND ".join(filters)

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

    params = [query_embedding, *filter_params, query_embedding, limit]
    try:
        cursor = conn.execute(sql, params)
    except Exception as exc:
        print(f"vector search unavailable: {exc}")
        return []

    results = []
    for row in cursor.fetchall():
        if isinstance(row, dict):
            results.append({
                "id": row["id"],
                "collection_id": row["collection_id"],
                "source_path": row["source_path"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "metadata": row["metadata"],
                "similarity": float(row["similarity"]),
            })
        else:
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
