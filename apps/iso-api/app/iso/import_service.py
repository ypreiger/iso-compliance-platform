"""Import uploaded ISO files into iso_clause_text and RAG."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.iso.parser import BilingualUpload, dedupe_clauses, parse_bilingual_json, parse_upload, is_bilingual_json
from app.iso.rag_index import file_sha256, index_clauses, purge_standard_language


def clear_standard_language(conn: Any, *, std: str, language: str) -> None:
    """Remove all clause rows and RAG chunks for a standard+language."""
    conn.execute(
        "DELETE FROM iso_clause_text WHERE standard = %s AND language = %s",
        (std, language),
    )
    purge_standard_language(conn, standard=std, language=language)


def _clause_meta(clause_id: str) -> tuple[str, int]:
    parts = [p for p in clause_id.split(".") if p]
    parent = ".".join(parts[:-1]) if len(parts) > 1 else ""
    return parent, len(parts)


def _upsert_clause(
    conn: Any,
    *,
    std: str,
    language: str,
    edition: str,
    clause,
    corpus_id: str = "",
) -> None:
    parent, depth = _clause_meta(clause.clause_id)
    conn.execute(
        """
        INSERT INTO iso_clause_text
          (standard, clause_id, title, language, body, sort_order, edition, source,
           parent_clause_id, depth, corpus_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'upload', %s, %s, %s)
        ON CONFLICT (standard, clause_id, language) DO UPDATE SET
            title = EXCLUDED.title,
            body = EXCLUDED.body,
            sort_order = EXCLUDED.sort_order,
            edition = EXCLUDED.edition,
            source = EXCLUDED.source,
            parent_clause_id = EXCLUDED.parent_clause_id,
            depth = EXCLUDED.depth,
            corpus_id = EXCLUDED.corpus_id
        """,
        (
            std, clause.clause_id, clause.title, language, clause.body,
            clause.sort_order, edition, parent, depth, corpus_id,
        ),
    )


def _import_language_clauses(
    conn: Any,
    *,
    std: str,
    language: str,
    edition: str,
    clauses: list,
    corpus_id: str,
    filename: str,
    sha: str,
    replace_previous: bool,
) -> int:
    clauses, _warnings = dedupe_clauses(clauses)
    if not clauses:
        return 0

    if replace_previous:
        clear_standard_language(conn, std=std, language=language)
        for clause in clauses:
            parent, depth = _clause_meta(clause.clause_id)
            conn.execute(
                """
                INSERT INTO iso_clause_text
                  (standard, clause_id, title, language, body, sort_order, edition, source,
                   parent_clause_id, depth, corpus_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'upload', %s, %s, %s)
                """,
                (
                    std, clause.clause_id, clause.title, language, clause.body,
                    clause.sort_order, edition, parent, depth, corpus_id,
                ),
            )
    else:
        for clause in clauses:
            _upsert_clause(
                conn,
                std=std,
                language=language,
                edition=edition,
                clause=clause,
                corpus_id=corpus_id,
            )

    return index_clauses(
        conn,
        standard=std,
        language=language,
        edition=edition,
        corpus_id=corpus_id,
        source_name=filename,
        clauses=clauses,
        content_sha256=sha,
        replace_all=replace_previous,
    )


def import_iso_upload(
    conn: Any,
    *,
    content: bytes,
    filename: str,
    standard: str,
    language: str,
    edition: str,
    admin_id: str | None,
    replace_previous: bool = True,
    auto_translate_he: bool = False,
) -> dict:
    sha = file_sha256(content)
    corpus_id = str(uuid4())
    warnings: list[str] = []

    if language == "both" or (filename.lower().endswith(".json") and is_bilingual_json(content)):
        text = content.decode("utf-8", errors="replace")
        bundle: BilingualUpload = parse_bilingual_json(text, default_standard=standard)
        std = bundle.standard
        en_clauses, en_warn = dedupe_clauses(bundle.en)
        he_clauses, he_warn = dedupe_clauses(bundle.he)
        warnings.extend(en_warn)
        warnings.extend(he_warn)
        total_clauses = len(en_clauses) + len(he_clauses)
        if total_clauses == 0:
            raise ValueError("No clauses parsed from bilingual upload")

        conn.execute(
            """
            INSERT INTO corpus_documents (id, doc_type, name, standards, language, edition, status, metadata)
            VALUES (%s, 'iso_standard', %s, %s, %s, %s, 'ready', %s::jsonb)
            """,
            (
                corpus_id,
                filename,
                [std],
                "both",
                edition,
                json.dumps({
                    "sha256": sha,
                    "clause_count_en": len(en_clauses),
                    "clause_count_he": len(he_clauses),
                    "source": "upload",
                    "bilingual": True,
                    "replace_previous": replace_previous,
                }),
            ),
        )

        rag_en = 0
        rag_he = 0
        if en_clauses:
            rag_en = _import_language_clauses(
                conn, std=std, language="en", edition=edition, clauses=en_clauses,
                corpus_id=corpus_id, filename=filename, sha=sha, replace_previous=replace_previous,
            )
        if he_clauses:
            rag_he = _import_language_clauses(
                conn, std=std, language="he", edition=edition, clauses=he_clauses,
                corpus_id=corpus_id, filename=filename, sha=sha, replace_previous=replace_previous,
            )

        from app.db import audit

        audit(
            conn,
            admin_id,
            "corpus.iso.uploaded",
            "corpus_document",
            corpus_id,
            after={
                "standard": std,
                "language": "both",
                "edition": edition,
                "clauses_en": len(en_clauses),
                "clauses_he": len(he_clauses),
                "replace_previous": replace_previous,
            },
        )
        return {
            "corpus_id": corpus_id,
            "standard": std,
            "language": "both",
            "edition": edition,
            "clauses_imported": len(en_clauses) + len(he_clauses),
            "clauses_en": len(en_clauses),
            "clauses_he": len(he_clauses),
            "rag_chunks": rag_en + rag_he,
            "replace_previous": replace_previous,
            "warnings": warnings,
            "auto_translate_he": auto_translate_he,
        }

    std, clauses = parse_upload(
        content,
        filename=filename,
        standard=standard,
        language=language,
    )
    clauses, parse_warnings = dedupe_clauses(clauses)
    warnings.extend(parse_warnings)
    if not clauses:
        raise ValueError("No clauses parsed from upload")

    conn.execute(
        """
        INSERT INTO corpus_documents (id, doc_type, name, standards, language, edition, status, metadata)
        VALUES (%s, 'iso_standard', %s, %s, %s, %s, 'ready', %s::jsonb)
        """,
        (
            corpus_id,
            filename,
            [std],
            language,
            edition,
            json.dumps({
                "sha256": sha,
                "clause_count": len(clauses),
                "source": "upload",
                "replace_previous": replace_previous,
            }),
        ),
    )

    chunk_count = _import_language_clauses(
        conn,
        std=std,
        language=language,
        edition=edition,
        clauses=clauses,
        corpus_id=corpus_id,
        filename=filename,
        sha=sha,
        replace_previous=replace_previous,
    )

    from app.db import audit

    audit(
        conn,
        admin_id,
        "corpus.iso.uploaded",
        "corpus_document",
        corpus_id,
        after={
            "standard": std,
            "language": language,
            "edition": edition,
            "clauses": len(clauses),
            "replace_previous": replace_previous,
        },
    )

    return {
        "corpus_id": corpus_id,
        "standard": std,
        "language": language,
        "edition": edition,
        "clauses_imported": len(clauses),
        "rag_chunks": chunk_count,
        "replace_previous": replace_previous,
        "warnings": warnings,
        "auto_translate_he": auto_translate_he,
    }


def import_translated_clauses(
    conn: Any,
    *,
    standard: str,
    edition: str,
    clauses: list[tuple[str, str, str, int]],
    target_language: str,
    admin_id: str | None,
    corpus_id: str = "",
    replace_all: bool = True,
) -> int:
    """Write translated clauses into target language.

    When replace_all=True (default full-standard translate), clears all existing
    target-language clauses + RAG first. When False, upserts only the provided
    clause IDs (partial translate).
    """
    if replace_all:
        clear_standard_language(conn, std=standard, language=target_language)
    count = 0
    for clause_id, title, body, sort_order in clauses:
        parent, depth = _clause_meta(clause_id)
        if replace_all:
            conn.execute(
                """
                INSERT INTO iso_clause_text
                  (standard, clause_id, title, language, body, sort_order, edition, source,
                   parent_clause_id, depth, corpus_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'translated', %s, %s, %s)
                """,
                (
                    standard,
                    clause_id,
                    title,
                    target_language,
                    body,
                    sort_order,
                    edition,
                    parent,
                    depth,
                    corpus_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO iso_clause_text
                  (standard, clause_id, title, language, body, sort_order, edition, source,
                   parent_clause_id, depth, corpus_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'translated', %s, %s, %s)
                ON CONFLICT (standard, clause_id, language) DO UPDATE SET
                    title = EXCLUDED.title,
                    body = EXCLUDED.body,
                    sort_order = EXCLUDED.sort_order,
                    edition = EXCLUDED.edition,
                    source = EXCLUDED.source,
                    parent_clause_id = EXCLUDED.parent_clause_id,
                    depth = EXCLUDED.depth,
                    corpus_id = EXCLUDED.corpus_id
                """,
                (
                    standard,
                    clause_id,
                    title,
                    target_language,
                    body,
                    sort_order,
                    edition,
                    parent,
                    depth,
                    corpus_id,
                ),
            )
        count += 1
    from app.db import audit

    audit(
        conn,
        admin_id,
        "corpus.iso.translated",
        "standard",
        standard,
        after={
            "clauses": count,
            "target_language": target_language,
            "corpus_id": corpus_id,
            "replace_all": replace_all,
        },
    )
    return count
