"""Generate endpoint — produce Excel, DOCX, or PDF compliance documents."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    format: Literal["excel", "docx", "pdf"]
    project_name: str = "Compliance Report"
    standard: str = "ISO9001"
    edition: str = "2015"
    locale: Literal["en", "he"] = "en"
    findings: list[dict] = []
    mappings: list[dict] = []
    coverage: list[dict] = []


_MIME = {
    "excel": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "pdf": ("application/pdf", "pdf"),
}


@router.post("")
def generate_document(req: GenerateRequest) -> Response:
    """Generate a compliance report in the requested format."""
    from app.agents.generator import (
        generate_excel_compliance_report,
        generate_docx_report,
        generate_pdf_report,
    )

    data = req.model_dump()
    try:
        if req.format == "excel":
            content = generate_excel_compliance_report(data)
        elif req.format == "docx":
            content = generate_docx_report(data)
        elif req.format == "pdf":
            content = generate_pdf_report(data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    mime, ext = _MIME[req.format]
    safe_name = req.project_name.replace(" ", "_")[:40]
    filename = f"{safe_name}_{req.standard}.{ext}"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
