"""Index ISO uploads into rag_documents with version replacement.

Each ISO standard is indexed into its own collection
(``iso-standards-ISO9001``, ``iso-standards-ISO13485``, …) so clause
titles/chunks never mix across standards. Legacy rows in the shared
``iso-standards`` collection remain readable until re-ingest.

When PostgreSQL + BGE-M3 are available, chunk embeddings are written so
semantic RAG (multilingual EN/HE) can use vector search.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.iso.parser import ParsedClause

log = logging.getLogger(__name__)

LEGACY_COLLECTION_ID = "iso-standards"
# Back-compat alias used by older imports/callers.
COLLECTION_ID = LEGACY_COLLECTION_ID
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
EMBED_BATCH = 16


def normalize_standard_id(standard: str) -> str:
    return (standard or "").upper().replace(" ", "").replace("-", "")


def collection_id_for_standard(standard: str) -> str:
    """Per-standard RAG collection — never share one index across standards."""
    return f"iso-standards-{normalize_standard_id(standard)}"


def _chunk(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + CHUNK_SIZE])
        start += max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    return chunks


def purge_standard_language(
    conn: Any,
    *,
    standard: str,
    language: str,
) -> None:
    """Remove all RAG chunks for this standard+language before re-import.

    Deletes both the per-standard collection and any legacy shared-collection
    rows tagged with the same metadata.standard.
    """
    std = normalize_standard_id(standard)
    coll = collection_id_for_standard(std)
    conn.execute(
        """
        DELETE FROM rag_documents
        WHERE collection_id = %s
          AND metadata->>'language' = %s
        """,
        (coll, language),
    )
    conn.execute(
        """
        DELETE FROM rag_documents
        WHERE collection_id = %s
          AND metadata->>'standard' = %s
          AND metadata->>'language' = %s
        """,
        (LEGACY_COLLECTION_ID, std, language),
    )


def purge_clause_chunks(
    conn: Any,
    *,
    standard: str,
    language: str,
    clause_ids: list[str],
) -> None:
    std = normalize_standard_id(standard)
    coll = collection_id_for_standard(std)
    for clause_id in clause_ids:
        conn.execute(
            """
            DELETE FROM rag_documents
            WHERE collection_id = %s
              AND metadata->>'language' = %s
              AND metadata->>'clause_id' = %s
            """,
            (coll, language, clause_id),
        )
        conn.execute(
            """
            DELETE FROM rag_documents
            WHERE collection_id = %s
              AND metadata->>'standard' = %s
              AND metadata->>'language' = %s
              AND metadata->>'clause_id' = %s
            """,
            (LEGACY_COLLECTION_ID, std, language, clause_id),
        )


def _insert_chunk(
    conn: Any,
    *,
    coll: str,
    source_path: str,
    idx: int,
    piece: str,
    meta: dict,
    embedding: list[float] | None,
) -> None:
    if embedding is not None:
        conn.execute(
            """
            INSERT INTO rag_documents
                (collection_id, source_path, chunk_index, content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)
            ON CONFLICT (collection_id, source_path, chunk_index) DO UPDATE
            SET content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata
            """,
            (coll, source_path, idx, piece, embedding, json.dumps(meta)),
        )
    else:
        conn.execute(
            """
            INSERT INTO rag_documents (collection_id, source_path, chunk_index, content, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (collection_id, source_path, chunk_index) DO UPDATE
            SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
            """,
            (coll, source_path, idx, piece, json.dumps(meta)),
        )


def index_clauses(
    conn: Any,
    *,
    standard: str,
    language: str,
    edition: str,
    corpus_id: str,
    source_name: str,
    clauses: list[ParsedClause],
    content_sha256: str,
    replace_all: bool = True,
    source: str = "upload",
) -> int:
    from app.iso.embeddings import (
        embeddings_enabled,
        generate_embeddings,
        is_zero_vector,
    )

    std = normalize_standard_id(standard)
    coll = collection_id_for_standard(std)
    if replace_all:
        purge_standard_language(conn, standard=std, language=language)
    elif clauses:
        purge_clause_chunks(
            conn,
            standard=std,
            language=language,
            clause_ids=[c.clause_id for c in clauses],
        )

    pending: list[tuple[str, int, str, dict]] = []
    source_path = f"uploads/{corpus_id}/{source_name}"
    for clause in clauses:
        full_text = f"{clause.clause_id} {clause.title}\n\n{clause.body}"
        for idx, piece in enumerate(_chunk(full_text)):
            parts = [p for p in clause.clause_id.split(".") if p]
            meta = {
                "kind": "standards",
                "standard": std,
                "language": language,
                "edition": edition,
                "clause_id": clause.clause_id,
                "title": clause.title,
                "parent_clause_id": ".".join(parts[:-1]) if len(parts) > 1 else "",
                "depth": len(parts),
                "corpus_id": corpus_id,
                "sha256": content_sha256,
                "source": source,
            }
            pending.append((f"{source_path}#{clause.clause_id}", idx, piece, meta))

    do_embed = embeddings_enabled()
    if do_embed:
        log.info(
            "Indexing %d RAG chunks with BGE-M3 embeddings (standard=%s lang=%s)",
            len(pending),
            std,
            language,
        )
    else:
        log.info(
            "Indexing %d RAG chunks without embeddings (standard=%s lang=%s)",
            len(pending),
            std,
            language,
        )

    inserted = 0
    for i in range(0, len(pending), EMBED_BATCH):
        batch = pending[i : i + EMBED_BATCH]
        texts = [piece for _, _, piece, _ in batch]
        vectors: list[list[float] | None] = [None] * len(batch)
        if do_embed:
            raw = generate_embeddings(texts, task="embed_index")
            vectors = [None if is_zero_vector(v) else v for v in raw]

        for (path, idx, piece, meta), emb in zip(batch, vectors):
            _insert_chunk(
                conn,
                coll=coll,
                source_path=path,
                idx=idx,
                piece=piece,
                meta=meta,
                embedding=emb,
            )
            inserted += 1
    return inserted


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
