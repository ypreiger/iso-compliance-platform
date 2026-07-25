#!/usr/bin/env python3
"""Ops repair: restore ISO9001 EN from DOCX structure; clean HE junk + rollup."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.db import get_conn
from app.iso.clause_parse import (
    ensure_parent_clauses,
    parse_document_bytes,
    promote_nested_clauses,
    roll_up_empty_parents,
)
from app.iso.import_service import _import_language_clauses
from app.iso.parser import ParsedClause, dedupe_clauses
from app.iso.pipeline import (
    _bad_title,
    _normalize_clause_bodies,
    _repair_known_titles,
)


def clean_clauses(clauses: list[ParsedClause], language: str) -> list[ParsedClause]:
    clauses, _ = dedupe_clauses(clauses)
    clauses = ensure_parent_clauses(promote_nested_clauses(clauses))
    clauses = _repair_known_titles(clauses, language=language, standard="ISO9001")
    clauses = _normalize_clause_bodies(clauses, language=language)
    kept: list[ParsedClause] = []
    for c in clauses:
        cid = c.clause_id
        title = (c.title or "").strip()
        if title.startswith("##"):
            continue
        if "ISO 10002" in title or "Correspondence" in title or "התאמה בין" in title:
            continue
        if cid.startswith("0."):
            rest = cid.split(".", 1)[1]
            if rest.isdigit() and int(rest) >= 5:
                continue
        # EN LLM sometimes nests Support/Operation under 4.x
        if language == "en" and (
            cid.startswith("4.5")
            or cid.startswith("4.4.3")
            or cid.startswith("4.4.4")
            or cid.startswith("4.4.5")
        ):
            continue
        if _bad_title(title, cid) and not (c.body or "").strip():
            continue
        kept.append(c)
    kept = roll_up_empty_parents(kept)
    return _repair_known_titles(kept, language=language, standard="ISO9001")


def import_lang(path: str, language: str) -> None:
    content = Path(path).read_bytes()
    filename = Path(path).name
    clauses = clean_clauses(parse_document_bytes(content, filename=filename), language)
    print(f"{language}: parsed/cleaned {len(clauses)} clauses")
    for cid in ["0", "1", "4", "4.1", "5", "6", "7", "7.1", "8", "9", "10"]:
        c = next((x for x in clauses if x.clause_id == cid), None)
        if c:
            print(f"  {cid}: {c.title[:50]!r} blen={len(c.body)}")
        else:
            print(f"  {cid}: MISSING")
    corpus_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO corpus_documents
              (id, doc_type, name, standards, language, edition, status, metadata)
            VALUES (%s, 'iso_standard', %s, %s, %s, %s, 'ready', %s::jsonb)
            """,
            (
                corpus_id,
                filename,
                ["ISO9001"],
                language,
                "2015",
                json.dumps(
                    {
                        "parse_method": "structure+repair",
                        "clauses_imported": len(clauses),
                        "source": "ops-repair",
                        "replace_previous": True,
                    }
                ),
            ),
        )
        n = _import_language_clauses(
            conn,
            std="ISO9001",
            language=language,
            edition="2015",
            clauses=clauses,
            corpus_id=corpus_id,
            filename=filename,
            sha="ops-repair",
            replace_previous=True,
        )
        conn.commit()
    print(f"{language}: imported rag_chunks={n} corpus_id={corpus_id}")


def repair_he_in_place() -> None:
    with get_conn() as conn:
        deleted = conn.execute(
            """
            DELETE FROM iso_clause_text
            WHERE standard='ISO9001' AND language='he'
              AND (
                title LIKE '##%'
                OR title ILIKE '%ISO 10002%'
                OR title ILIKE '%גיליון התיקון%'
                OR clause_id ~ '^0\\.([5-9]|[1-9][0-9])$'
                OR clause_id = '1.2'
                OR (clause_id LIKE '10.2.%' AND title LIKE '%ISO%')
                OR title ~ '^[.][0-9]'
              )
            RETURNING clause_id, title
            """
        ).fetchall()
        print("HE deleted junk:", [(r["clause_id"], r["title"][:40]) for r in deleted])
        rows = conn.execute(
            """
            SELECT clause_id, title, body, sort_order
            FROM iso_clause_text
            WHERE standard='ISO9001' AND language='he'
            ORDER BY sort_order, clause_id
            """
        ).fetchall()
        clauses = [
            ParsedClause(r["clause_id"], r["title"], r["body"] or "", int(r["sort_order"]))
            for r in rows
        ]
        clauses = _repair_known_titles(clauses, language="he", standard="ISO9001")
        clauses = roll_up_empty_parents(clauses)
        clauses = _normalize_clause_bodies(clauses, language="he")
        for c in clauses:
            conn.execute(
                """
                UPDATE iso_clause_text
                SET title=%s, body=%s, sort_order=%s
                WHERE standard='ISO9001' AND language='he' AND clause_id=%s
                """,
                (c.title, c.body, c.sort_order, c.clause_id),
            )
        conn.commit()
        print(f"HE repaired in place: {len(clauses)} clauses")
        for cid in ["0", "1", "4", "5.1", "6", "7", "7.1", "8", "9", "10"]:
            c = next((x for x in clauses if x.clause_id == cid), None)
            print(f"  {cid}: {(c.title if c else None)!r} blen={len(c.body) if c else None}")


if __name__ == "__main__":
    import_lang("/tmp/ISO9001-EN.docx", "en")
    repair_he_in_place()
