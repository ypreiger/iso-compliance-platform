"""RAG search over indexed ISO chunks — vector (BGE-M3) with keyword fallback."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.iso.rag_index import LEGACY_COLLECTION_ID, collection_id_for_standard, normalize_standard_id

log = logging.getLogger(__name__)


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


def _meta(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _keyword_search(
    conn: Any,
    *,
    standard: str,
    language: str,
    query: str,
    limit: int,
) -> list[dict]:
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
        meta = _meta(row["metadata"])
        results.append(
            {
                "clause_id": meta.get("clause_id", ""),
                "title": meta.get("title", ""),
                "content": row["content"],
                "score": int(row["score"]),
                "method": "keyword",
            }
        )
    return results


def _vector_search(
    conn: Any,
    *,
    standard: str,
    language: str,
    query: str,
    limit: int,
) -> list[dict]:
    from app.db import USE_SQLITE
    from app.iso.embeddings import embeddings_configured
    from app.iso.vector_search import search_similar_chunks

    if USE_SQLITE or not embeddings_configured():
        return []

    chunks = search_similar_chunks(
        conn,
        query,
        limit=limit,
        standard=standard,
        language=language,
    )
    results: list[dict] = []
    for ch in chunks:
        sim = float(ch.get("similarity") or 0.0)
        if sim < 0.25:
            continue
        meta = _meta(ch.get("metadata"))
        results.append(
            {
                "clause_id": meta.get("clause_id", ""),
                "title": meta.get("title", ""),
                "content": ch.get("content", ""),
                # Scale similarity into the same rough units mapping.py expects.
                "score": max(1, int(round(sim * 10))),
                "similarity": sim,
                "method": "vector",
            }
        )
    return results


def search_iso_rag(
    conn: Any,
    *,
    standard: str,
    language: str,
    query: str,
    limit: int = 1,
) -> list[dict]:
    """Return best-matching RAG chunks for a standard+language.

    Prefers BGE-M3 vector similarity when embeddings exist; falls back to
    keyword scoring so dry-run / unembedded corpora still work.
    Always scoped to one standard — never mixes clause indexes across standards.
    """
    try:
        vector_hits = _vector_search(
            conn,
            standard=standard,
            language=language,
            query=query,
            limit=limit,
        )
        if vector_hits:
            return vector_hits
    except Exception as exc:
        log.warning("vector RAG search failed; falling back to keyword: %s", exc)

    return _keyword_search(
        conn,
        standard=standard,
        language=language,
        query=query,
        limit=limit,
    )
