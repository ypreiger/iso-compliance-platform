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
    raw_text: str | None = None         # original extracted text for retrieval fidelity
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
    raw_text_for_parse = _preprocess_extracted_text(raw_text)

    log.info("Extracted %d chars from %s", len(raw_text), filename)

    # ── LLM structuring ───────────────────────────────────────────────────
    if req.task == "iso_clauses":
        from app.agents.extractor import extract_clauses
        regex_clauses = _promote_nested_clauses(_regex_extract_clauses(raw_text_for_parse))
        model_used = "regex"
        method = "regex"
        clauses = regex_clauses

        # Fast path: hierarchical regex already recovered rich level-3 coverage.
        if _structure_quality_ok(regex_clauses, language=req.language):
            warnings.append(
                f"Used hierarchical regex parse ({len(regex_clauses)} clauses); skipped LLM."
            )
        else:
            try:
                llm_clauses, model_used = await extract_clauses(
                    raw_text_for_parse, standard=req.standard, language=req.language
                )
                llm_clauses = _promote_nested_clauses(llm_clauses)
                # Hebrew PDF regex titles are often garbage; merge LLM+regex so we
                # keep LLM titles/bodies where good and fill gaps from regex.
                if req.language.lower().startswith("he"):
                    clauses = _merge_clause_sets(llm_clauses, regex_clauses)
                    method = "hybrid"
                    warnings.append(
                        f"Merged LLM ({len(llm_clauses)}) + regex ({len(regex_clauses)}) for Hebrew."
                    )
                else:
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
                clauses = regex_clauses
                model_used = "regex"
                method = "regex"

        clauses = _annotate_clause_metadata(clauses)

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
        raw_text=raw_text,
        raw_text_length=len(raw_text),
    )


# ── regex fallback ─────────────────────────────────────────────────────────

import re as _re
_CLAUSE_LINE = _re.compile(
    r"^(?:#{1,4}\s*)?\.?(\d{1,2}(?:\.\d{1,2}){0,4})(?:\s*[\.\)]?\s*)(\S(?:.*\S)?)\s*$"
)
_JUNK = _re.compile(
    r"(©\s*ISO|All rights reserved|Licensed to|Downloaded|^\s*\d{1,3}\s*$)", _re.I
)
_TOC_LINE = _re.compile(r"\.{2,}\s*\d+\s*$")
_CLAUSE_ID_ONLY = _re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,4}$")


def _strip_correspondence_annexes(text: str) -> str:
    """Drop ISO correspondence/comparison annexes that mix two clause schemes."""
    patterns = (
        r"(?im)^Annex\s+[A-Z]\s*\n?\s*\(informative\)\s*\n\s*"
        r"(?:Correspondence between ISO|Comparison of content between ISO)",
        r"(?im)^Correspondence between ISO\s+\d+",
        r"(?im)^Comparison of content between ISO\s+\d+",
        r"(?im)^Table\s+B\.\d+\s+[—\-–].*Correspondence between ISO",
    )
    cut = None
    for pat in patterns:
        m = re.search(pat, text)
        if m and (cut is None or m.start() < cut):
            cut = m.start()
    return text[:cut].rstrip() if cut is not None else text


def _strip_toc_artifact_lines(text: str) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if re.search(r"\.{5,}|…{3,}", s):
            continue
        if re.match(r"^Annex\s+[A-Z]\s*\(informative\).+\d+\s*$", s, re.I):
            continue
        out.append(line)
    return "\n".join(out)


def _preprocess_extracted_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _strip_correspondence_annexes(text)
    text = _strip_toc_artifact_lines(text)
    text = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", text)
    # Hebrew/RTL extractors often emit leading dots: ".5.1.1" → "5.1.1"
    text = re.sub(r"(?m)^\.+(\d{1,2}(?:\.\d{1,2}){0,4})(?=\s|$)", r"\1", text)
    text = re.sub(r"(?im)^(Introduction|מבוא)\s*$", r"0 \1", text)
    lines = [ln.strip().lstrip(".") for ln in text.split("\n")]
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


def _level3_count(clauses: list[dict]) -> int:
    return sum(1 for c in clauses if str(c.get("clause_id", "")).count(".") >= 2)


def _bad_title(title: str, clause_id: str = "") -> bool:
    t = str(title or "").strip()
    if not t or t.startswith("Clause "):
        return True
    if t in {"סעיף", "וסעיף", "א -", "( א -", "א-", "חשיבה", "– ה", "ה", "-", "–"}:
        return True
    if re.search(r"https?://|www\.iso\.org", t, re.I):
        return True
    if re.match(r"^[a-z]", t):
        return True
    he = re.findall(r"[\u0590-\u05FF]+", t)
    if he and sum(len(x) for x in he) < 3:
        return True
    return False


def _structure_quality_ok(clauses: list[dict], *, language: str) -> bool:
    """True when regex/structure parse is rich enough to skip the slow LLM pass."""
    if len(clauses) < 40:
        return False
    if _level3_count(clauses) < 12:
        return False
    # Hebrew PDFs often look numerous but empty — require body mass too.
    min_chars = 8_000 if language.lower().startswith("he") else 4_000
    if _total_body_chars(clauses) < min_chars:
        return False
    bad = sum(1 for c in clauses if _bad_title(c.get("title", ""), str(c.get("clause_id", ""))))
    max_bad = 0.15 if language.lower().startswith("he") else 0.25
    if bad / max(1, len(clauses)) > max_bad:
        return False
    has_intro = any(
        str(c.get("clause_id", "")) == "0" or str(c.get("clause_id", "")).startswith("0.")
        for c in clauses
    )
    if not has_intro:
        return False
    # Hebrew tokenized PDFs invent headings; require LLM unless titles look real.
    if language.lower().startswith("he"):
        return False
    return True


def _parent_id(clause_id: str) -> str:
    parts = clause_id.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else ""


def _annotate_clause_metadata(clauses: list[dict]) -> list[dict]:
    out: list[dict] = []
    for c in clauses:
        cid = str(c.get("clause_id", "")).strip()
        item = dict(c)
        item["clause_id"] = cid
        item["depth"] = cid.count(".") + 1 if cid else 0
        item["parent_clause_id"] = _parent_id(cid)
        out.append(item)
    return out


def _promote_nested_clauses(clauses: list[dict]) -> list[dict]:
    """Split child headings accidentally left inside a parent body (e.g. 5.1.1 in 5.1)."""
    if not clauses:
        return clauses
    merged: dict[str, dict] = {}
    order: list[str] = []

    def upsert(cid: str, title: str, body: str) -> None:
        if cid not in merged:
            merged[cid] = {"clause_id": cid, "title": title, "body": body}
            order.append(cid)
            return
        if not merged[cid]["title"] and title:
            merged[cid]["title"] = title
        if body and body not in merged[cid]["body"]:
            prev = merged[cid]["body"]
            merged[cid]["body"] = f"{prev}\n\n{body}".strip() if prev else body

    for clause in clauses:
        cid = _normalize_clause_id(str(clause.get("clause_id", "")))
        if not cid:
            continue
        title = str(clause.get("title", "")).strip()
        body = str(clause.get("body", "")).strip()
        upsert(cid, title, "")

        current_id = cid
        body_lines: list[str] = []
        for line in body.split("\n"):
            stripped = line.strip()
            m = _CLAUSE_LINE.match(stripped) if stripped else None
            if m:
                nested_id = _normalize_clause_id(m.group(1))
                # Only promote true descendants of the current clause.
                if nested_id and (
                    nested_id.startswith(cid + ".") or nested_id.count(".") > cid.count(".")
                ):
                    if body_lines:
                        upsert(current_id, merged[current_id]["title"], "\n".join(body_lines).strip())
                        body_lines = []
                    upsert(nested_id, m.group(2).strip(), "")
                    current_id = nested_id
                    continue
            if stripped:
                body_lines.append(stripped)
        if body_lines:
            upsert(current_id, merged[current_id]["title"], "\n".join(body_lines).strip())

    return [merged[cid] for cid in sorted(order, key=_clause_sort_key)]


def _clause_quality(clause: dict) -> tuple[int, int, int]:
    title = str(clause.get("title", ""))
    body = str(clause.get("body", ""))
    cid = str(clause.get("clause_id", ""))
    title_ok = 0 if _bad_title(title, cid) else 1
    return title_ok, len(body.strip()), len(title.strip())


def _merge_clause_sets(*sets: list[dict]) -> list[dict]:
    """Union clause sets, keeping the better title/body per clause_id."""
    best: dict[str, dict] = {}
    for clauses in sets:
        for clause in clauses or []:
            cid = _normalize_clause_id(str(clause.get("clause_id", "")))
            if not cid:
                continue
            item = {
                "clause_id": cid,
                "title": str(clause.get("title", "")).strip(),
                "body": str(clause.get("body", "")).strip(),
            }
            prev = best.get(cid)
            if prev is None or _clause_quality(item) > _clause_quality(prev):
                # Preserve non-empty fields from the other side when winning on one axis.
                if prev:
                    if not item["title"] and prev["title"]:
                        item["title"] = prev["title"]
                    if not item["body"] and prev["body"]:
                        item["body"] = prev["body"]
                    elif item["body"] and prev["body"] and len(prev["body"]) > len(item["body"]) * 1.3:
                        if _bad_title(item["title"], cid) and not _bad_title(prev["title"], cid):
                            item["body"] = prev["body"]
                best[cid] = item
    return [best[cid] for cid in sorted(best.keys(), key=_clause_sort_key)]


def _choose_best_clause_set(
    *,
    llm_clauses: list[dict],
    regex_clauses: list[dict],
    language: str,
) -> tuple[list[dict], str]:
    """Pick parser output with better fidelity.

    Prefer the set with more level-3 clauses when body coverage is comparable.
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
        # Prefer more granular level-3 coverage when both are viable.
        if _level3_count(llm_clauses) + 3 < _level3_count(regex_clauses):
            return regex_clauses, "regex"
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
            if 0 <= top <= 10:
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
