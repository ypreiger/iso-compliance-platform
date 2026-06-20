"""ISO clause text — bilingual viewer API."""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.deps import CurrentUser, get_current_user
from app.db import get_conn, rows_to_list

router = APIRouter(prefix="/v1/iso", tags=["iso-text"])

STANDARDS = ["ISO9001", "ISO14001", "ISO45001", "ISO13485"]


@router.get("/standards")
def list_standards(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return {"standards": STANDARDS}


@router.get("/clauses")
def search_clauses(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    standard: str = Query(..., description="ISO9001, ISO14001, etc."),
    language: str = Query("en", pattern="^(en|he)$"),
    q: str = Query("", description="Search keyword or clause id"),
):
    with get_conn() as conn:
        sql = """
            SELECT id, content, metadata, source_path
            FROM rag_documents
            WHERE collection_id IN ('iso-clauses', 'iso-standards')
              AND metadata->>'standard' = %s
              AND metadata->>'language' = %s
        """
        params: list = [standard.upper().replace(" ", ""), language]
        if q:
            sql += " AND (metadata->>'clause_id' ILIKE %s OR content ILIKE %s OR metadata->>'title' ILIKE %s)"
            like = f"%{q}%"
            params.extend([like, like, like])
        sql += " ORDER BY metadata->>'clause_id', chunk_index LIMIT 200"
        rows = conn.execute(sql, params).fetchall()
    clauses = []
    for row in rows:
        meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
        clauses.append({
            "id": row["id"],
            "clause_id": meta.get("clause_id", ""),
            "title": meta.get("title", ""),
            "language": meta.get("language", language),
            "text": row["content"],
            "standard": meta.get("standard", standard),
            "direction": "rtl" if language == "he" else "ltr",
        })
    return {"standard": standard, "language": language, "clauses": clauses}


@router.get("/clauses/{clause_id}")
def get_clause(
    clause_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    standard: str = Query(...),
    language: str = Query("en", pattern="^(en|he)$"),
):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT content, metadata FROM rag_documents
            WHERE metadata->>'standard' = %s
              AND metadata->>'clause_id' = %s
              AND metadata->>'language' = %s
            ORDER BY chunk_index
            LIMIT 1
            """,
            (standard.upper().replace(" ", ""), clause_id, language),
        ).fetchone()
    if not row:
        return {"clause_id": clause_id, "standard": standard, "language": language, "text": "", "title": ""}
    meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
    return {
        "clause_id": clause_id,
        "standard": standard,
        "language": language,
        "title": meta.get("title", ""),
        "text": row["content"],
        "direction": "rtl" if language == "he" else "ltr",
    }


@router.get("/clauses/{clause_id}/bilingual")
def get_clause_bilingual(
    clause_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    standard: str = Query(...),
):
    result = {}
    for lang in ("en", "he"):
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT content, metadata FROM rag_documents
                WHERE metadata->>'standard' = %s
                  AND metadata->>'clause_id' = %s
                  AND metadata->>'language' = %s
                LIMIT 1
                """,
                (standard.upper().replace(" ", ""), clause_id, lang),
            ).fetchone()
        if row:
            meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
            result[lang] = {
                "title": meta.get("title", ""),
                "text": row["content"],
                "direction": "rtl" if lang == "he" else "ltr",
            }
    return {"clause_id": clause_id, "standard": standard, "locales": result}
