"""Projects and context questionnaire."""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser, require_project_access
from app.db import audit, get_conn, rows_to_list

router = APIRouter(prefix="/v1/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    standards: list[str] = Field(default_factory=lambda: ["ISO9001"])
    edition: str = "2015"


class ContextUpdate(BaseModel):
    context: dict = Field(default_factory=dict)


@router.get("")
def list_projects(user: Annotated[CurrentUser, Depends(require_project_access)]):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, standards, edition, status, mapping_approved, created_at, updated_at
            FROM projects ORDER BY updated_at DESC
            """
        ).fetchall()
    return {"projects": rows_to_list(rows)}


@router.post("")
def create_project(body: ProjectCreate, user: Annotated[CurrentUser, Depends(require_project_access)]):
    pid = str(uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, name, standards, edition, owner_id, status)
            VALUES (%s, %s, %s, %s, %s, 'draft')
            """,
            (pid, body.name, body.standards, body.edition, user.id),
        )
        audit(conn, user.id, "project.created", "project", pid, after=body.model_dump())
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = %s", (pid,)).fetchone()
    return dict(row)


@router.get("/{project_id}")
def get_project(project_id: str, user: Annotated[CurrentUser, Depends(require_project_access)]):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(row)


@router.put("/{project_id}/context")
def update_context(
    project_id: str,
    body: ContextUpdate,
    user: Annotated[CurrentUser, Depends(require_project_access)],
):
    with get_conn() as conn:
        row = conn.execute("SELECT context FROM projects WHERE id = %s", (project_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        conn.execute(
            "UPDATE projects SET context = %s::jsonb, updated_at = NOW(), status = 'context' WHERE id = %s",
            (body.context, project_id),
        )
        audit(conn, user.id, "project.context", "project", project_id, after=body.context)
        conn.commit()
    return {"ok": True, "context": body.context}
