"""Corpus file storage — list, download, delete original uploaded files."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth.deps import CurrentUser, get_current_user, require_admin
from app.db import get_conn, rows_to_list

router = APIRouter(prefix="/admin/corpus/files", tags=["documents"])


@router.get("")
def list_files(admin: Annotated[CurrentUser, Depends(require_admin)]):
    """List all stored original files (without binary data)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT cf.id, cf.corpus_id, cf.filename, cf.content_type,
                   cf.size_bytes, cf.created_at,
                   cd.standards, cd.language, cd.edition,
                   cd.metadata->>'parse_method' AS parse_method,
                   cd.metadata->>'clauses_imported' AS clauses_imported,
                   cd.metadata->'validation' AS validation
            FROM corpus_files cf
            JOIN corpus_documents cd ON cd.id = cf.corpus_id
            ORDER BY cf.created_at DESC
            """
        ).fetchall()
    result = []
    for r in rows_to_list(rows):
        result.append({
            "id": r["id"],
            "corpus_id": r["corpus_id"],
            "filename": r["filename"],
            "content_type": r["content_type"],
            "size_bytes": r["size_bytes"],
            "created_at": str(r["created_at"]),
            "standards": r.get("standards") or [],
            "language": r.get("language", ""),
            "edition": r.get("edition", ""),
            "parse_method": r.get("parse_method") or "unknown",
            "clauses_imported": r.get("clauses_imported"),
            "validation": r.get("validation"),
        })
    return {"files": result}


@router.get("/{file_id}")
def download_file(
    file_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Download an original uploaded file by its file_id."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT filename, content_type, file_data FROM corpus_files WHERE id = %s",
            (file_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    # file_data may come back as bytes (psycopg) or memoryview
    data = bytes(row["file_data"])
    return Response(
        content=data,
        media_type=row["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{row["filename"]}"',
            "Content-Length": str(len(data)),
        },
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """Delete a stored file (does NOT delete the indexed clauses)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM corpus_files WHERE id = %s", (file_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        conn.execute("DELETE FROM corpus_files WHERE id = %s", (file_id,))
        conn.commit()
    return {"ok": True, "deleted": file_id}


@router.get("/validate/{corpus_id}")
def get_validation(
    corpus_id: str,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """Return the stored validation report for a corpus document."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT metadata FROM corpus_documents WHERE id = %s", (corpus_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Corpus document not found")
    meta = row["metadata"] or {}
    return {"corpus_id": corpus_id, "validation": meta.get("validation")}
