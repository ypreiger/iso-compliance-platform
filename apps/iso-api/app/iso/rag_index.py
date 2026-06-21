"""Index ISO uploads into rag_documents with version replacement."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.iso.parser import ParsedClause

COLLECTION_ID = "iso-standards"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


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
    """Remove all RAG chunks for this standard+language before re-import."""
    conn.execute(
        """
        DELETE FROM rag_documents
        WHERE collection_id = %s
          AND metadata->>'standard' = %s
          AND metadata->>'language' = %s
        """,
        (COLLECTION_ID, standard, language),
    )


def purge_clause_chunks(
    conn: Any,
    *,
    standard: str,
    language: str,
    clause_ids: list[str],
) -> None:
    for clause_id in clause_ids:
        conn.execute(
            """
            DELETE FROM rag_documents
            WHERE collection_id = %s
              AND metadata->>'standard' = %s
              AND metadata->>'language' = %s
              AND metadata->>'clause_id' = %s
            """,
            (COLLECTION_ID, standard, language, clause_id),
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
) -> int:
    if replace_all:
        purge_standard_language(conn, standard=standard, language=language)
    elif clauses:
        purge_clause_chunks(
            conn,
            standard=standard,
            language=language,
            clause_ids=[c.clause_id for c in clauses],
        )
    inserted = 0
    source_path = f"uploads/{corpus_id}/{source_name}"
    for clause in clauses:
        full_text = f"{clause.clause_id} {clause.title}\n\n{clause.body}"
        for idx, piece in enumerate(_chunk(full_text)):
            meta = {
                "kind": "standards",
                "standard": standard,
                "language": language,
                "edition": edition,
                "clause_id": clause.clause_id,
                "title": clause.title,
                "corpus_id": corpus_id,
                "sha256": content_sha256,
                "source": "upload",
            }
            conn.execute(
                """
                INSERT INTO rag_documents (collection_id, source_path, chunk_index, content, metadata)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (collection_id, source_path, chunk_index) DO UPDATE
                SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
                """,
                (
                    COLLECTION_ID,
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
