"""Export triggers (docgen integration)."""
from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import CurrentUser, require_project_access
from app.db import get_conn

router = APIRouter(prefix="/v1/projects/{project_id}/exports", tags=["exports"])

DOCGEN_URL = __import__("os").getenv("DOCGEN_URL", "http://iso-docgen:8080")


class ExportRequest(BaseModel):
    format: str
    template_type: str = "excel"
    locale: str = "he"


@router.post("")
async def create_export(
    project_id: str,
    body: ExportRequest,
    user: Annotated[CurrentUser, Depends(require_project_access)],
):
    with get_conn() as conn:
        project = conn.execute(
            "SELECT mapping_approved, name FROM projects WHERE id = %s", (project_id,)
        ).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project["mapping_approved"]:
        raise HTTPException(status_code=400, detail="Mapping must be approved before export")
    payload = {
        "project_id": project_id,
        "project_name": project["name"],
        "format": body.format,
        "template_type": body.template_type,
        "locale": body.locale,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{DOCGEN_URL}/generate", json=payload)
            if resp.status_code == 200:
                return resp.json()
    except httpx.RequestError:
        pass
    return {
        "status": "queued",
        "format": body.format,
        "message": "Export stub — docgen service will produce artifact when deployed",
        "download_url": f"/v1/projects/{project_id}/exports/latest",
    }


@router.get("/latest")
def latest_export(project_id: str, user: Annotated[CurrentUser, Depends(require_project_access)]):
    return {
        "project_id": project_id,
        "artifact": None,
        "note": "No artifact yet — deploy docgen-service for Hebrew DOCX/XLSX output",
    }
