"""Parse endpoint — accepts any document file, returns structured JSON."""
from __future__ import annotations

import base64
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/parse", tags=["parse"])
log = logging.getLogger(__name__)


class ParseRequest(BaseModel):
    filename: str
    content_b64: str = Field(..., description="Base64-encoded file bytes")
    standard: str = "ISO9001"
    language: str = "en"
    task: Literal["iso_clauses", "findings", "general"] = "iso_clauses"


class ParseResponse(BaseModel):
    filename: str
    source_type: str
    task: str
    model_used: str
    parse_method: str          # "llm" | "structured" | "regex"
    clauses: list[dict] | None = None   # iso_clauses task
    sheets: list[dict] | None = None    # findings/general task for Excel
    raw_text_length: int = 0
    warnings: list[str] = []


@router.post("", response_model=ParseResponse)
async def parse_document(req: ParseRequest) -> ParseResponse:
    """Parse a document and return structured ISO clauses or findings."""
    try:
        data = base64.b64decode(req.content_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 content: {exc}") from exc

    filename = req.filename.strip()
    lower = filename.lower()
    warnings: list[str] = []

    # ── Excel — always structured, no LLM needed ─────────────────────────
    if lower.endswith((".xlsx", ".xls")):
        from app.agents.parser import extract_excel
        try:
            result = extract_excel(data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Excel parse failed: {exc}") from exc
        return ParseResponse(
            filename=filename,
            source_type="xlsx",
            task=req.task,
            model_used="none",
            parse_method="structured",
            sheets=result["sheets"],
        )

    # ── PDF / DOC / DOCX — extract text then LLM ─────────────────────────
    if not any(lower.endswith(ext) for ext in (".pdf", ".doc", ".docx")):
        raise HTTPException(
            status_code=400,
            detail="Supported formats: .pdf, .doc, .docx, .xlsx. Received: " + filename,
        )

    from app.agents.parser import extract_text
    try:
        raw_text = extract_text(data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {exc}") from exc

    log.info("Extracted %d chars from %s", len(raw_text), filename)

    # ── LLM structuring ───────────────────────────────────────────────────
    if req.task == "iso_clauses":
        from app.agents.extractor import extract_clauses
        from app.config import get_model_config
        try:
            clauses, model_used = await extract_clauses(
                raw_text, standard=req.standard, language=req.language
            )
            method = "llm"
        except Exception as exc:
            log.warning("LLM extraction failed (%s); falling back to regex", exc)
            warnings.append(f"LLM failed ({exc}); used regex fallback")
            clauses = _regex_extract_clauses(raw_text)
            model_used = "regex"
            method = "regex"

        if not clauses:
            raise HTTPException(
                status_code=422,
                detail="No ISO clauses found. Verify the document contains structured text with clause headings like '4.1'.",
            )
        return ParseResponse(
            filename=filename,
            source_type=lower.split(".")[-1],
            task=req.task,
            model_used=model_used,
            parse_method=method,
            clauses=clauses,
            raw_text_length=len(raw_text),
            warnings=warnings,
        )

    # ── general / findings — return raw text segmented ────────────────────
    # For findings, caller can post-process; or we parse Excel for findings
    sheets = [{"name": "text", "rows": [{"line": ln} for ln in raw_text.split("\n") if ln.strip()]}]
    return ParseResponse(
        filename=filename,
        source_type=lower.split(".")[-1],
        task=req.task,
        model_used="none",
        parse_method="text",
        sheets=sheets,
        raw_text_length=len(raw_text),
    )


# ── regex fallback ─────────────────────────────────────────────────────────

import re as _re
_CLAUSE_LINE = _re.compile(
    r"^(?:#{1,4}\s*)?(\d{1,2}(?:\.\d{1,2}){0,4})\s+(.+?)\s*$"
)
_JUNK = _re.compile(
    r"(©\s*ISO|All rights reserved|Licensed to|Downloaded|^\s*\d{1,3}\s*$)", _re.I
)


def _regex_extract_clauses(text: str) -> list[dict]:
    clauses: list[dict] = []
    current: dict | None = None
    body_lines: list[str] = []

    def flush():
        nonlocal current, body_lines
        if current:
            current["body"] = "\n\n".join(body_lines).strip()
            clauses.append(current)
        current = None
        body_lines = []

    for line in text.split("\n"):
        line = line.strip()
        if not line or _JUNK.search(line):
            continue
        m = _CLAUSE_LINE.match(line)
        if m:
            flush()
            cid_raw = m.group(1)
            parts = [p for p in cid_raw.split(".") if p.isdigit()]
            cid = ".".join(str(int(p)) for p in parts)
            top = int(cid.split(".")[0])
            if 1 <= top <= 10:
                current = {"clause_id": cid, "title": m.group(2).strip(), "body": ""}
        elif current:
            body_lines.append(line)
    flush()
    return clauses
