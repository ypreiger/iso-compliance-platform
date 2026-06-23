"""ISO clause extraction agent.

Receives raw text (already extracted from PDF/DOC/DOCX) and uses an LLM
to return a structured list of ISO clauses: [{clause_id, title, body}].

Segments large texts so no single call exceeds ≈ 12 000 chars.
Merges partial clauses that span segment boundaries.
"""
from __future__ import annotations

import logging
import re

from app.llm import LLMError, llm_call, parse_json_response

log = logging.getLogger(__name__)

MAX_SEGMENT_CHARS = 12_000
OVERLAP_CHARS = 400

_TOP_SECTION = re.compile(r"^(\d{1,2})\s+[A-Z\u0590-\u05FF]", re.MULTILINE)
_CLAUSE_ID_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,4}$")

SYSTEM_PROMPT = """\
You are an ISO standards document expert.
Extract every normative clause from the text. Skip: table of contents, foreword, \
bibliography, copyright notices, page numbers, annex headers.

Return ONLY a JSON array — no markdown, no extra text:
[
  {"clause_id": "4",   "title": "Context of the organization", "body": "Full body text…"},
  {"clause_id": "4.1", "title": "Understanding the organization", "body": "…"},
  …
]

Rules:
- clause_id uses ISO numbering: "4", "4.1", "4.1.1" etc.
- title is the heading text only, no clause_id prefix.
- body contains ALL text belonging to that clause verbatim; keep \\n\\n paragraph breaks.
- If a clause body is empty in the source, set body to "".
"""


def _segment(text: str) -> list[str]:
    if len(text) <= MAX_SEGMENT_CHARS:
        return [text]
    # Split at top-level sections
    hits = list(_TOP_SECTION.finditer(text))
    if len(hits) >= 2:
        parts: list[str] = []
        for i, m in enumerate(hits):
            start = m.start()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            chunk = text[start:end]
            if len(chunk) > MAX_SEGMENT_CHARS:
                parts.extend(_window(chunk))
            else:
                parts.append(chunk)
        pre = text[: hits[0].start()].strip()
        if pre:
            parts.insert(0, pre)
        return parts
    return _window(text)


def _window(text: str) -> list[str]:
    out: list[str] = []
    start = 0
    while start < len(text):
        out.append(text[start : start + MAX_SEGMENT_CHARS])
        start += MAX_SEGMENT_CHARS - OVERLAP_CHARS
    return out


def _normalize_id(raw: str) -> str:
    parts = [p for p in raw.strip().split(".") if p.isdigit()]
    if not parts:
        return ""
    return ".".join(str(int(p)) for p in parts)


def _clause_sort_key(clause_id: str) -> tuple[int, ...]:
    return tuple(int(p) for p in clause_id.split(".") if p.isdigit())


def _iter_clause_items(payload: object) -> list[dict]:
    """Normalize heterogeneous LLM JSON into a list of clause dicts."""
    if isinstance(payload, list):
        out: list[dict] = []
        for item in payload:
            out.extend(_iter_clause_items(item))
        return out
    if isinstance(payload, dict):
        preferred = payload.get("clauses")
        if isinstance(preferred, (list, dict)):
            return _iter_clause_items(preferred)
        if all(k in payload for k in ("clause_id", "title", "body")):
            return [payload]
        out: list[dict] = []
        for value in payload.values():
            if isinstance(value, (list, dict)):
                out.extend(_iter_clause_items(value))
        return out
    return []


async def extract_clauses(
    text: str,
    *,
    standard: str,
    language: str,
) -> tuple[list[dict], str]:
    """Return (clauses_list, model_used). clauses_list items: {clause_id, title, body}."""
    segments = _segment(text)
    log.info("extract_clauses: %s/%s %d chars %d segments", standard, language, len(text), len(segments))

    merged: dict[str, dict] = {}
    order: list[str] = []

    for idx, seg in enumerate(segments):
        log.info("  segment %d/%d (%d chars)", idx + 1, len(segments), len(seg))
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Standard: {standard}  Language: {language}\n\n"
                f"Extract ISO clauses from this text:\n\n{seg}"
            )},
        ]
        raw = await llm_call("extract", msgs, temperature=0, response_format="json")
        items = _iter_clause_items(parse_json_response(raw))
        for item in items:
            cid = _normalize_id(str(item.get("clause_id", "")))
            if not cid or not _CLAUSE_ID_RE.match(cid):
                continue
            top = int(cid.split(".")[0])
            if top < 1 or top > 10:
                continue
            title = str(item.get("title", "")).strip()
            body = str(item.get("body", "")).strip()
            if cid not in merged:
                merged[cid] = {"clause_id": cid, "title": title, "body": body}
                order.append(cid)
            else:
                if not merged[cid]["title"] and title:
                    merged[cid]["title"] = title
                if body and body not in merged[cid]["body"]:
                    sep = "\n\n" if merged[cid]["body"] else ""
                    merged[cid]["body"] = merged[cid]["body"] + sep + body

    from app.config import get_model_config
    model_used = get_model_config()["extract"]["model"]

    result = [merged[cid] for cid in sorted(order, key=_clause_sort_key)]
    log.info("extract_clauses done: %d clauses, model=%s", len(result), model_used)
    return result, model_used
