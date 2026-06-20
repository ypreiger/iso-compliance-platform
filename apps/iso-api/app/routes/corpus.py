"""Corpus admin — ISO, samples, templates."""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import CurrentUser, require_admin
from app.db import get_conn, rows_to_list

router = APIRouter(prefix="/admin/corpus", tags=["corpus"])


class CorpusCreate(BaseModel):
    doc_type: str
    name: str
    standards: list[str] = []
    language: str = "en"
    edition: str = ""


@router.get("/{doc_type}")
def list_corpus(doc_type: str, admin: Annotated[CurrentUser, Depends(require_admin)]):
    if doc_type not in ("iso", "samples", "templates"):
        raise HTTPException(status_code=400, detail="Invalid doc_type")
    type_map = {"iso": "iso_standard", "samples": "sample_report", "templates": "template"}
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, standards, language, edition, status, created_at
            FROM corpus_documents WHERE doc_type = %s ORDER BY created_at DESC
            """,
            (type_map[doc_type],),
        ).fetchall()
        rag_count = conn.execute(
            "SELECT COUNT(*) AS c FROM rag_documents WHERE collection_id = %s",
            (f"iso-{doc_type}" if doc_type != "iso" else "iso-standards",),
        ).fetchone()
    return {
        "documents": rows_to_list(rows),
        "indexed_chunks": int(rag_count["c"]) if rag_count else 0,
    }


@router.post("/{doc_type}")
def register_corpus(
    doc_type: str,
    body: CorpusCreate,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    type_map = {"iso": "iso_standard", "samples": "sample_report", "templates": "template"}
    if doc_type not in type_map:
        raise HTTPException(status_code=400, detail="Invalid doc_type")
    cid = str(uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO corpus_documents (id, doc_type, name, standards, language, edition, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'ready')
            """,
            (cid, type_map[doc_type], body.name, body.standards, body.language, body.edition),
        )
        conn.commit()
    return {"id": cid, "status": "ready"}


@router.get("/summary/all")
def corpus_summary(admin: Annotated[CurrentUser, Depends(require_admin)]):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT doc_type, COUNT(*) AS count FROM corpus_documents GROUP BY doc_type
            """
        ).fetchall()
        chunks = conn.execute("SELECT COUNT(*) AS c FROM rag_documents").fetchone()
    return {"by_type": rows_to_list(rows), "total_chunks": int(chunks["c"]) if chunks else 0}
