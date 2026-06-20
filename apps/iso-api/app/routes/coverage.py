"""Clause coverage matrix."""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import CurrentUser, get_current_user
from app.db import get_conn, rows_to_list

router = APIRouter(prefix="/v1/projects/{project_id}/coverage", tags=["coverage"])


class CoverageSet(BaseModel):
    standard: str
    clause_id: str
    status: str
    reason: str = ""


@router.get("")
def get_coverage(project_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clause_coverage WHERE project_id = %s ORDER BY standard, clause_id",
            (project_id,),
        ).fetchall()
    return {"coverage": rows_to_list(rows)}


@router.put("")
def set_coverage(
    project_id: str,
    body: CoverageSet,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    user.require_role("supervisor", "admin")
    cid = str(uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO clause_coverage (id, project_id, standard, clause_id, status, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (project_id, standard, clause_id) DO UPDATE
            SET status = EXCLUDED.status, reason = EXCLUDED.reason
            """,
            (cid, project_id, body.standard, body.clause_id, body.status, body.reason),
        )
        conn.commit()
    return {"ok": True}
