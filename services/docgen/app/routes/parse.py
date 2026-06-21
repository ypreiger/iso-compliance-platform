"""Parse endpoint — accepts any document file, returns structured JSON."""
from __future__ import annotations

import base64
import logging
import re
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
    raw_text = _preprocess_extracted_text(raw_text)

    log.info("Extracted %d chars from %s", len(raw_text), filename)

    # ── LLM structuring ───────────────────────────────────────────────────
    if req.task == "iso_clauses":
        from app.agents.extractor import extract_clauses
        regex_clauses = _regex_extract_clauses(raw_text)
        try:
            llm_clauses, model_used = await extract_clauses(
                raw_text, standard=req.standard, language=req.language
            )
            clauses, method = _choose_best_clause_set(
                llm_clauses=llm_clauses,
                regex_clauses=regex_clauses,
                language=req.language,
            )
            if method != "llm":
                warnings.append(
                    "LLM parse dropped too much content; used regex parse for fidelity."
                )
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
    r"^(?:#{1,4}\s*)?(\d{1,2}(?:\.\d{1,2}){0,4})(?:\s*[\.\)]?\s*)(\S(?:.*\S)?)\s*$"
)
_JUNK = _re.compile(
    r"(©\s*ISO|All rights reserved|Licensed to|Downloaded|^\s*\d{1,3}\s*$)", _re.I
)
_TOC_LINE = _re.compile(r"\.{2,}\s*\d+\s*$")
_CLAUSE_ID_ONLY = _re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,4}$")


def _preprocess_extracted_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", text)
    lines = [ln.strip() for ln in text.split("\n")]
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            line
            and _CLAUSE_ID_ONLY.fullmatch(line)
            and i + 1 < len(lines)
            and lines[i + 1]
            and not _CLAUSE_LINE.match(lines[i + 1])
        ):
            merged.append(f"{line} {lines[i + 1]}")
            i += 2
            continue
        if line:  # Only append non-empty lines
            merged.append(line)
        i += 1
    return "\n".join(merged)


def _normalize_clause_id(raw: str) -> str:
    parts = [p for p in raw.split(".") if p.isdigit()]
    if not parts:
        return ""
    return ".".join(str(int(p)) for p in parts)


def _clause_sort_key(clause_id: str) -> tuple[int, ...]:
    return tuple(int(p) for p in clause_id.split(".") if p.isdigit())


def _total_body_chars(clauses: list[dict]) -> int:
    return sum(len(str(c.get("body", "")).strip()) for c in clauses)


def _choose_best_clause_set(
    *,
    llm_clauses: list[dict],
    regex_clauses: list[dict],
    language: str,
) -> tuple[list[dict], str]:
    """Pick parser output with better fidelity.

    Hebrew is evaluated more strictly because the LLM often drops content.
    """
    llm_count = len(llm_clauses)
    regex_count = len(regex_clauses)
    llm_chars = _total_body_chars(llm_clauses)
    regex_chars = _total_body_chars(regex_clauses)

    if llm_count == 0:
        return regex_clauses, "regex"
    if regex_count == 0:
        return llm_clauses, "llm"

    min_ratio = 0.90 if language.lower().startswith("he") else 0.75
    llm_count_ok = llm_count >= max(1, int(regex_count * min_ratio))
    llm_chars_ok = llm_chars >= int(regex_chars * min_ratio)

    if llm_count_ok and llm_chars_ok:
        return llm_clauses, "llm"
    return regex_clauses, "regex"


def _regex_extract_clauses(text: str) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    current_id: str | None = None
    body_lines: list[str] = []

    def flush():
        nonlocal current_id, body_lines
        if not current_id:
            return
        body = "\n\n".join(body_lines).strip()
        if body:
            prev = str(merged[current_id].get("body", "")).strip()
            merged[current_id]["body"] = f"{prev}\n\n{body}".strip() if prev else body
        current_id = None
        body_lines = []

    for line in text.split("\n"):
        line = line.strip()
        if not line or _JUNK.search(line) or _TOC_LINE.search(line):
            continue
        m = _CLAUSE_LINE.match(line)
        if m:
            flush()
            cid = _normalize_clause_id(m.group(1))
            if not cid:
                continue
            top = int(cid.split(".")[0])
            if 1 <= top <= 10:
                if cid not in merged:
                    merged[cid] = {"clause_id": cid, "title": m.group(2).strip(), "body": ""}
                    order.append(cid)
                elif not merged[cid]["title"]:
                    merged[cid]["title"] = m.group(2).strip()
                current_id = cid
        elif current_id:
            body_lines.append(line)
    flush()
    return [merged[cid] for cid in sorted(order, key=_clause_sort_key)]
