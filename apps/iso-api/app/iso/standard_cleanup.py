"""Remove ISO standard data (clauses, RAG, corpus records)."""
from __future__ import annotations

from typing import Any

from app.iso.rag_index import COLLECTION_ID, purge_standard_language


def purge_standard_rag(conn: Any, *, standard: str, language: str | None = None) -> int:
    if language:
        conn.execute(
            """
            DELETE FROM rag_documents
            WHERE collection_id = %s
              AND metadata->>'standard' = %s
              AND metadata->>'language' = %s
            """,
            (COLLECTION_ID, standard, language),
        )
    else:
        conn.execute(
            """
            DELETE FROM rag_documents
            WHERE collection_id = %s AND metadata->>'standard' = %s
            """,
            (COLLECTION_ID, standard),
        )
    return 1


def delete_iso_standard(
    conn: Any,
    *,
    standard: str,
    languages: list[str] | None = None,
    admin_id: str | None = None,
) -> dict:
    std = standard.upper().replace(" ", "")
    langs = languages or ["en", "he"]
    deleted_clauses = 0
    for lang in langs:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM iso_clause_text WHERE standard = %s AND language = %s",
            (std, lang),
        ).fetchone()
        deleted_clauses += int(row["c"]) if row else 0
        conn.execute(
            "DELETE FROM iso_clause_text WHERE standard = %s AND language = %s",
            (std, lang),
        )
        purge_standard_language(conn, standard=std, language=lang)

    if languages is None:
        purge_standard_rag(conn, standard=std, language=None)
    else:
        for lang in langs:
            purge_standard_rag(conn, standard=std, language=lang)

    conn.execute(
        """
        DELETE FROM corpus_documents
        WHERE doc_type = 'iso_standard' AND %s = ANY(standards)
        """,
        (std,),
    )

    from app.db import audit

    audit(
        conn,
        admin_id,
        "corpus.iso.deleted",
        "standard",
        std,
        after={"languages": langs, "clauses_removed": deleted_clauses},
    )
    return {"standard": std, "languages": langs, "clauses_removed": deleted_clauses}
