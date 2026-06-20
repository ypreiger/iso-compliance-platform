"""Instructions / prompt admin."""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import CurrentUser, require_admin
from app.db import audit, get_conn, rows_to_list

router = APIRouter(prefix="/admin/instructions", tags=["instructions"])

STAGES = [
    "context_summarize", "finding_normalize", "iso_map_and_score",
    "clause_coverage", "corrective_action_draft", "ofi_instruction_draft", "report_narrative",
]


class PromptSave(BaseModel):
    stage: str
    body: str
    locale: str = "en"


@router.get("")
def list_instructions(admin: Annotated[CurrentUser, Depends(require_admin)]):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT stage, locale, MAX(version) AS version
            FROM prompt_templates WHERE is_published = TRUE
            GROUP BY stage, locale ORDER BY stage
            """
        ).fetchall()
        published = conn.execute(
            """
            SELECT id, stage, locale, version, body, is_published, created_at
            FROM prompt_templates WHERE is_published = TRUE ORDER BY stage, version DESC
            """
        ).fetchall()
    return {"stages": STAGES, "published": rows_to_list(published), "summary": rows_to_list(rows)}


@router.get("/{stage}")
def get_stage(stage: str, admin: Annotated[CurrentUser, Depends(require_admin)], locale: str = "en"):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM prompt_templates
            WHERE stage = %s AND locale = %s AND is_published = TRUE
            ORDER BY version DESC LIMIT 1
            """,
            (stage, locale),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Stage not found")
    return dict(row)


@router.post("")
def publish_instruction(body: PromptSave, admin: Annotated[CurrentUser, Depends(require_admin)]):
    if body.stage not in STAGES:
        raise HTTPException(status_code=400, detail="Invalid stage")
    pid = str(uuid4())
    with get_conn() as conn:
        ver = conn.execute(
            """
            SELECT COALESCE(MAX(version), 0) + 1 AS v FROM prompt_templates
            WHERE stage = %s AND locale = %s
            """,
            (body.stage, body.locale),
        ).fetchone()
        version = int(ver["v"])
        conn.execute(
            "UPDATE prompt_templates SET is_published = FALSE WHERE stage = %s AND locale = %s",
            (body.stage, body.locale),
        )
        conn.execute(
            """
            INSERT INTO prompt_templates (id, stage, locale, version, body, is_published, published_by)
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
            """,
            (pid, body.stage, body.locale, version, body.body, admin.id),
        )
        audit(conn, admin.id, "prompt.publish", "prompt", pid, after={"stage": body.stage, "version": version})
        conn.commit()
    return {"id": pid, "version": version}
