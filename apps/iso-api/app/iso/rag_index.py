"""Index ISO uploads into rag_documents with version replacement.

Each ISO standard is indexed into its own collection
(``iso-standards-ISO9001``, ``iso-standards-ISO13485``, …) so clause
titles/chunks never mix across standards. Legacy rows in the shared
``iso-standards`` collection remain readable until re-ingest.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.iso.parser import ParsedClause

LEGACY_COLLECTION_ID = "iso-standards"
# Back-compat alias used by older imports/callers.
COLLECTION_ID = LEGACY_COLLECTION_ID
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


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
    inserted = 0
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
            conn.execute(
                """
                INSERT INTO rag_documents (collection_id, source_path, chunk_index, content, metadata)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (collection_id, source_path, chunk_index) DO UPDATE
                SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
                """,
                (
                    coll,
                    f"{source_path}#{clause.clause_id}",
                    idx,
                    piece,
                    json.dumps(meta),
                ),
            )
            inserted += 1
    return inserted


def file_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
