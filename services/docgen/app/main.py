"""Document generation service (Excel/DOCX stub)."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ISO DocGen", version="0.1.0")


class GenerateRequest(BaseModel):
    project_id: str
    project_name: str
    format: str
    template_type: str = "excel"
    locale: str = "he"


@app.get("/health")
def health():
    return {"status": "ok", "service": "docgen"}


@app.post("/generate")
def generate(req: GenerateRequest):
    return {
        "status": "generated",
        "project_id": req.project_id,
        "format": req.format,
        "locale": req.locale,
        "artifact": f"/artifacts/{req.project_id}.{req.format}",
        "note": "Hebrew RTL DOCX/XLSX generation — wire python-docx/openpyxl in phase 2",
    }
