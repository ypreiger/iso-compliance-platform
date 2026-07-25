"""Keyword search over indexed ISO RAG chunks."""
from __future__ import annotations

import re
from typing import Any

from app.iso.rag_index import LEGACY_COLLECTION_ID, collection_id_for_standard, normalize_standard_id


def _query_terms(text: str, *, max_terms: int = 6) -> list[str]:
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was", "be", "to", "of", "in",
        "on", "at", "by", "or", "an", "as", "is", "it", "its", "not", "may", "can", "has", "have",
        "shall", "will", "were", "been", "being", "organization", "management", "system",
    }
    terms: list[str] = []
    for word in re.findall(r"[A-Za-z\u0590-\u05FF]{4,}", text.lower()):
        if word in stop:
            continue
        if word not in terms:
            terms.append(word)
        if len(terms) >= max_terms:
            break
    return terms


def search_iso_rag(
    conn: Any,
    *,
    standard: str,
    language: str,
    query: str,
    limit: int = 1,
) -> list[dict]:
    """Return best-matching RAG chunks for a standard+language.

    Always scoped to one standard — never mixes clause indexes across standards.
    """
    terms = _query_terms(query)
    if not terms:
        return []

    std = normalize_standard_id(standard)
    coll = collection_id_for_standard(std)

    score_parts = ["CASE"]
    params: list[Any] = []
    for term in terms:
        score_parts.append(" WHEN LOWER(content) LIKE %s THEN 1")
        params.append(f"%{term}%")
    score_parts.append(" ELSE 0 END")
    score_sql = "".join(score_parts)
    # Per-standard collection first; also accept legacy shared rows for this standard only.
    params.extend([coll, LEGACY_COLLECTION_ID, std, std, language, limit])

    rows = conn.execute(
        f"""
        SELECT metadata, content,
               ({score_sql}) AS score
        FROM rag_documents
        WHERE (
                collection_id = %s
             OR (collection_id = %s AND metadata->>'standard' = %s)
              )
          AND metadata->>'standard' = %s
          AND metadata->>'language' = %s
          AND metadata->>'clause_id' IS NOT NULL
        ORDER BY score DESC, length(content) DESC, id
        LIMIT %s
        """,
        params,
    ).fetchall()

    results: list[dict] = []
    for row in rows:
        if int(row["score"]) <= 0:
            continue
        meta = row["metadata"]
        if isinstance(meta, str):
            import json

            meta = json.loads(meta)
        results.append(
            {
                "clause_id": meta.get("clause_id", ""),
                "title": meta.get("title", ""),
                "content": row["content"],
                "score": int(row["score"]),
            }
        )
    return results
