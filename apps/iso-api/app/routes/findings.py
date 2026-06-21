"""Findings ingest."""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import CurrentUser, require_project_access
from app.db import audit, get_conn, rows_to_list

router = APIRouter(prefix="/v1/projects/{project_id}/findings", tags=["findings"])


class FindingCreate(BaseModel):
    finding_text: str
    source_type: str = "manual"


class FindingsBulk(BaseModel):
    findings: list[str]


@router.get("")
def list_findings(project_id: str, user: Annotated[CurrentUser, Depends(require_project_access)]):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, finding_text, source_type, sort_order, review_status, created_at
            FROM findings WHERE project_id = %s ORDER BY sort_order, created_at
            """,
            (project_id,),
        ).fetchall()
    return {"findings": rows_to_list(rows)}


@router.post("")
def add_finding(
    project_id: str,
    body: FindingCreate,
    user: Annotated[CurrentUser, Depends(require_project_access)],
):
    fid = str(uuid4())
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id = %s", (project_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Project not found")
        conn.execute(
            """
            INSERT INTO findings (id, project_id, finding_text, source_type)
            VALUES (%s, %s, %s, %s)
            """,
            (fid, project_id, body.finding_text.strip(), body.source_type),
        )
        conn.execute(
            "UPDATE projects SET status = 'findings', updated_at = NOW() WHERE id = %s",
            (project_id,),
        )
        audit(conn, user.id, "finding.created", "finding", fid, after=body.model_dump())
        conn.commit()
    return {"id": fid, **body.model_dump()}


@router.post("/bulk")
def bulk_findings(
    project_id: str,
    body: FindingsBulk,
    user: Annotated[CurrentUser, Depends(require_project_access)],
):
    created = []
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id = %s", (project_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Project not found")
        for i, text in enumerate(body.findings):
            if not text.strip():
                continue
            fid = str(uuid4())
            conn.execute(
                """
                INSERT INTO findings (id, project_id, finding_text, source_type, sort_order)
                VALUES (%s, %s, %s, 'paste', %s)
                """,
                (fid, project_id, text.strip(), i),
            )
            created.append(fid)
        conn.execute(
            "UPDATE projects SET status = 'findings', updated_at = NOW() WHERE id = %s",
            (project_id,),
        )
        conn.commit()
    return {"created": len(created), "ids": created}
