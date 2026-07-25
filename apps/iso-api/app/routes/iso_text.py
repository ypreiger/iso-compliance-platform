"""ISO clause text — bilingual viewer API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.deps import CurrentUser, get_current_user
from app.db import get_conn, rows_to_list
from app.iso.parser import _sort_key, normalize_hebrew_body

router = APIRouter(prefix="/v1/iso", tags=["iso-text"])

DEFAULT_STANDARDS = ["ISO9001", "ISO14001", "ISO45001", "ISO13485"]


def _norm_standard(standard: str) -> str:
    return standard.upper().replace(" ", "")


def _row_to_clause(row: dict, language: str, *, fallback: bool = False) -> dict:
    cid = row["clause_id"]
    parts = [p for p in cid.split(".") if p]
    body = row["body"] or ""
    if language == "he":
        body = normalize_hebrew_body(body)
    return {
        "id": row.get("id"),
        "clause_id": cid,
        "title": row["title"],
        "language": language,
        "text": body,
        "standard": row["standard"],
        "direction": "rtl" if language == "he" else "ltr",
        "fallback": fallback,
        "source": row.get("source", "seed"),
        "edition": row.get("edition", ""),
        "parent_clause_id": row.get("parent_clause_id")
        or (".".join(parts[:-1]) if len(parts) > 1 else ""),
        "depth": row.get("depth") or len(parts),
        "corpus_id": row.get("corpus_id") or "",
    }


def _load_language_map(conn, std: str, language: str) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT id, standard, clause_id, title, body, sort_order, edition, source,
               parent_clause_id, depth, corpus_id
        FROM iso_clause_text
        WHERE standard = %s AND language = %s
        ORDER BY sort_order, clause_id
        """,
        (std, language),
    ).fetchall()
    return {r["clause_id"]: dict(r) for r in rows_to_list(rows)}


def _build_clause_list(
    std: str,
    language: str,
    primary: dict[str, dict],
    secondary: dict[str, dict],
) -> list[dict]:
    """Build viewer list from uploaded rows for the requested language.

    Cross-language fallback is only used when the requested language has no
    uploaded rows at all. Mixing HE into EN (or vice versa) for empty bodies
    looks like data corruption in the UI.
    """
    if primary:
        clause_ids = sorted(primary.keys(), key=lambda cid: (_sort_key(cid), cid))
        allow_fallback = False
    else:
        clause_ids = sorted(secondary.keys(), key=lambda cid: (_sort_key(cid), cid))
        allow_fallback = True

    clauses: list[dict] = []
    for clause_id in clause_ids:
        row = primary.get(clause_id)
        if row and row.get("body", "").strip():
            clauses.append(_row_to_clause(row, language, fallback=False))
            continue
        if allow_fallback:
            alt = secondary.get(clause_id)
            if alt and alt.get("body", "").strip():
                clauses.append(_row_to_clause(alt, language, fallback=True))
                continue
        if row:
            clauses.append(_row_to_clause(row, language, fallback=False))
    return clauses


def _filter_clause_list(clauses: list[dict], q: str) -> list[dict]:
    if not q:
        return clauses
    needle = q.lower()
    return [
        c
        for c in clauses
        if needle in c["clause_id"].lower()
        or needle in c["title"].lower()
        or needle in c["text"].lower()
    ]


@router.get("/standards")
def list_standards(user: Annotated[CurrentUser, Depends(get_current_user)]):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT standard FROM iso_clause_text ORDER BY standard"
        ).fetchall()
    standards = [r["standard"] for r in rows_to_list(rows)]
    return {"standards": standards or DEFAULT_STANDARDS}


@router.get("/clauses")
def search_clauses(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    standard: str = Query(..., description="ISO9001, ISO14001, etc."),
    language: str = Query("en", pattern="^(en|he)$"),
    q: str = Query("", description="Search keyword or clause id"),
):
    std = _norm_standard(standard)
    with get_conn() as conn:
        en_map = _load_language_map(conn, std, "en")
        he_map = _load_language_map(conn, std, "he")

    if language == "en":
        clauses = _build_clause_list(std, "en", en_map, he_map)
    else:
        clauses = _build_clause_list(std, "he", he_map, en_map)

    clauses = _filter_clause_list(clauses, q)
    return {"standard": std, "language": language, "clauses": clauses}


@router.get("/clauses/{clause_id}")
def get_clause(
    clause_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    standard: str = Query(...),
    language: str = Query("en", pattern="^(en|he)$"),
):
    std = _norm_standard(standard)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, standard, clause_id, title, body, edition, source,
                   parent_clause_id, depth, corpus_id
            FROM iso_clause_text
            WHERE standard = %s AND clause_id = %s AND language = %s
            """,
            (std, clause_id, language),
        ).fetchone()
        fallback = False
        if (not row or not row["body"].strip()) and language == "he":
            row = conn.execute(
                """
                SELECT id, standard, clause_id, title, body, edition, source,
                       parent_clause_id, depth, corpus_id
                FROM iso_clause_text
                WHERE standard = %s AND clause_id = %s AND language = 'en'
                """,
                (std, clause_id),
            ).fetchone()
            fallback = bool(row)
        elif (not row or not row["body"].strip()) and language == "en":
            row = conn.execute(
                """
                SELECT id, standard, clause_id, title, body, edition, source,
                       parent_clause_id, depth, corpus_id
                FROM iso_clause_text
                WHERE standard = %s AND clause_id = %s AND language = 'he'
                """,
                (std, clause_id),
            ).fetchone()
            fallback = bool(row)

    if not row:
        return {
            "clause_id": clause_id,
            "standard": std,
            "language": language,
            "text": "",
            "title": "",
            "direction": "rtl" if language == "he" else "ltr",
            "fallback": False,
        }
    clause = _row_to_clause(dict(row), language, fallback=fallback)
    return {
        "clause_id": clause["clause_id"],
        "standard": clause["standard"],
        "language": clause["language"],
        "title": clause["title"],
        "text": clause["text"],
        "direction": clause["direction"],
        "fallback": clause["fallback"],
        "edition": clause.get("edition", ""),
    }


@router.get("/clauses/{clause_id}/bilingual")
def get_clause_bilingual(
    clause_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    standard: str = Query(...),
):
    std = _norm_standard(standard)
    result: dict[str, dict] = {}
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT language, title, body, source
            FROM iso_clause_text
            WHERE standard = %s AND clause_id = %s AND language IN ('en', 'he')
            """,
            (std, clause_id),
        ).fetchall()
        en_row = conn.execute(
            """
            SELECT title, body FROM iso_clause_text
            WHERE standard = %s AND clause_id = %s AND language = 'en'
            """,
            (std, clause_id),
        ).fetchone()
    for row in rows_to_list(rows):
        lang = row["language"]
        result[lang] = {
            "title": row["title"],
            "text": row["body"],
            "direction": "rtl" if lang == "he" else "ltr",
            "source": row.get("source", "seed"),
        }
    if "he" not in result and en_row:
        result["he"] = {
            "title": en_row["title"],
            "text": en_row["body"],
            "direction": "rtl",
            "source": "en_fallback",
            "fallback": True,
        }
    return {"clause_id": clause_id, "standard": std, "locales": result}
