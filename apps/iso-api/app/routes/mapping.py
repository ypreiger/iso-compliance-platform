"""Supervisor mapping review."""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser, require_project_access
from app.db import audit, get_conn, rows_to_list
from app.iso.rag_search import search_iso_rag

router = APIRouter(prefix="/v1/projects/{project_id}/mapping", tags=["mapping"])


class MappingCreate(BaseModel):
    finding_id: str
    standard: str
    clause_id: str
    clause_title: str = ""
    relevance_pct: int = Field(ge=0, le=100, default=75)
    severity: str = "minor"


class MappingUpdate(BaseModel):
    relevance_pct: int | None = None
    severity: str | None = None


@router.get("")
def list_mappings(project_id: str, user: Annotated[CurrentUser, Depends(require_project_access)]):
    with get_conn() as conn:
        findings = conn.execute(
            "SELECT * FROM findings WHERE project_id = %s ORDER BY sort_order",
            (project_id,),
        ).fetchall()
        result = []
        for f in findings:
            maps = conn.execute(
                "SELECT * FROM finding_clause_mappings WHERE finding_id = %s",
                (f["id"],),
            ).fetchall()
            result.append({"finding": dict(f), "mappings": rows_to_list(maps)})
    return {"items": result}


@router.post("")
def add_mapping(
    project_id: str,
    body: MappingCreate,
    user: Annotated[CurrentUser, Depends(require_project_access)],
):
    user.require_role("supervisor", "admin")
    mid = str(uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO finding_clause_mappings
            (id, finding_id, standard, clause_id, clause_title, relevance_pct, severity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (finding_id, standard, clause_id) DO UPDATE
            SET relevance_pct = EXCLUDED.relevance_pct, severity = EXCLUDED.severity,
                clause_title = EXCLUDED.clause_title
            """,
            (
                mid, body.finding_id, body.standard, body.clause_id,
                body.clause_title, body.relevance_pct, body.severity,
            ),
        )
        conn.execute(
            "UPDATE projects SET status = 'mapping', updated_at = NOW() WHERE id = %s",
            (project_id,),
        )
        audit(conn, user.id, "mapping.add", "mapping", mid, after=body.model_dump())
        conn.commit()
    return {"id": mid}


@router.delete("/{mapping_id}")
def delete_mapping(
    project_id: str,
    mapping_id: str,
    user: Annotated[CurrentUser, Depends(require_project_access)],
):
    user.require_role("supervisor", "admin")
    with get_conn() as conn:
        conn.execute("DELETE FROM finding_clause_mappings WHERE id = %s", (mapping_id,))
        audit(conn, user.id, "mapping.delete", "mapping", mapping_id)
        conn.commit()
    return {"ok": True}


@router.post("/approve")
def approve_mapping(project_id: str, user: Annotated[CurrentUser, Depends(require_project_access)]):
    user.require_role("supervisor", "admin")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE projects SET mapping_approved = TRUE, status = 'approved', updated_at = NOW()
            WHERE id = %s
            """,
            (project_id,),
        )
        conn.execute(
            "UPDATE findings SET review_status = 'approved' WHERE project_id = %s",
            (project_id,),
        )
        audit(conn, user.id, "mapping.approved", "project", project_id)
        conn.commit()
    return {"ok": True, "mapping_approved": True}


@router.post("/run-auto")
def run_auto_mapping(project_id: str, user: Annotated[CurrentUser, Depends(require_project_access)]):
    """Stub: propose mappings from keyword match (LLM in phase 2)."""
    created = 0
    with get_conn() as conn:
        project = conn.execute(
            "SELECT standards FROM projects WHERE id = %s", (project_id,)
        ).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        standard = (project["standards"] or ["ISO9001"])[0]
        findings = conn.execute(
            "SELECT id, finding_text FROM findings WHERE project_id = %s", (project_id,)
        ).fetchall()
        for f in findings:
            hits = search_iso_rag(
                conn,
                standard=standard,
                language="en",
                query=f["finding_text"],
                limit=1,
            )
            if not hits:
                continue
            hit = hits[0]
            mid = str(uuid4())
            conn.execute(
                """
                INSERT INTO finding_clause_mappings
                (id, finding_id, standard, clause_id, clause_title, relevance_pct, severity)
                VALUES (%s, %s, %s, %s, %s, %s, 'minor')
                ON CONFLICT DO NOTHING
                """,
                (
                    mid,
                    f["id"],
                    standard,
                    hit["clause_id"],
                    hit["title"],
                    min(95, 50 + hit["score"] * 8),
                ),
            )
            created += 1
        conn.execute(
            "UPDATE projects SET status = 'mapping', updated_at = NOW() WHERE id = %s",
            (project_id,),
        )
        conn.commit()
    return {"proposed": created}
