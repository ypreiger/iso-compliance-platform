"""ISO clause extraction agent.

Receives raw text (already extracted from PDF/DOC/DOCX) and uses an LLM
to return a structured list of ISO clauses: [{clause_id, title, body}].

Segments large texts so no single call exceeds ≈ 12 000 chars.
Merges partial clauses that span segment boundaries.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

from app.llm import LLMError, llm_call, parse_json_response

log = logging.getLogger(__name__)

# Bound concurrent segment calls; gpt-oss is slow if fully serial.
_SEGMENT_CONCURRENCY = max(1, int(os.getenv("EXTRACT_SEGMENT_CONCURRENCY", "3")))

MAX_SEGMENT_CHARS = 6_000
OVERLAP_CHARS = 250

_TOP_SECTION = re.compile(r"^(\d{1,2})\s+[A-Z\u0590-\u05FF]", re.MULTILINE)
_CLAUSE_ID_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,4}$")

SYSTEM_PROMPT = """\
You are an ISO standards document expert.
Extract every clause heading and its body from the text, including Introduction.
Skip: table of contents, bibliography, copyright notices, page numbers,
and informative correspondence/comparison annexes between ISO standards.

Return ONLY a JSON object:
{"clauses": [
  {"clause_id": "0", "title": "<verbatim from document>", "body": "…"},
  {"clause_id": "0.1", "title": "<verbatim from document>", "body": "…"},
  {"clause_id": "4", "title": "<verbatim from document>", "body": "…"},
  {"clause_id": "4.1", "title": "<verbatim from document>", "body": "…"},
  {"clause_id": "4.1.1", "title": "<verbatim from document>", "body": "…"}
]}

Rules:
- clause_id uses ISO numbering: "0.1", "4", "4.1", "4.1.1", "5.1.2" (up to 5 levels).
- Introduction is 0 / 0.1 / 0.2 / 0.3 using the document's own title.
- CRITICAL: every level-3 / level-4 heading MUST be its own object.
  Never merge 5.1.1 into 5.1. Store 5.1.1 and 5.1.2 separately.
- Parent clauses (e.g. 5.1) only contain text before the first child heading.
- title is VERBATIM heading text from THIS standard only — never invent HLS titles
  and never copy titles from a different ISO standard or correspondence table.
- body is the verbatim clause text until the next heading; keep \\n\\n paragraph breaks.
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


def _merge_item(merged: dict[str, dict], order: list[str], item: dict) -> None:
    cid = _normalize_id(str(item.get("clause_id", "")))
    if not cid or not _CLAUSE_ID_RE.match(cid):
        return
    top = int(cid.split(".")[0])
    if top < 0 or top > 10:
        return
    title = str(item.get("title", "")).strip()
    body = str(item.get("body", "")).strip()
    if cid not in merged:
        merged[cid] = {"clause_id": cid, "title": title, "body": body}
        order.append(cid)
        return
    if not merged[cid]["title"] and title:
        merged[cid]["title"] = title
    if body and body not in merged[cid]["body"]:
        sep = "\n\n" if merged[cid]["body"] else ""
        merged[cid]["body"] = merged[cid]["body"] + sep + body


async def extract_clauses(
    text: str,
    *,
    standard: str,
    language: str,
) -> tuple[list[dict], str]:
    """Return (clauses_list, model_used). clauses_list items: {clause_id, title, body}."""
    segments = _segment(text)
    log.info(
        "extract_clauses: %s/%s %d chars %d segments concurrency=%d",
        standard, language, len(text), len(segments), _SEGMENT_CONCURRENCY,
    )

    sem = asyncio.Semaphore(_SEGMENT_CONCURRENCY)

    async def _one(idx: int, seg: str) -> list[dict]:
        async with sem:
            log.info("  segment %d/%d (%d chars)", idx + 1, len(segments), len(seg))
            msgs = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Standard: {standard}  Language: {language}\n"
                    f"Extract clauses for {standard} only. Titles must be exact indexes "
                    f"from this standard — never titles from another ISO standard.\n\n"
                    f"Extract ISO clauses from this text. "
                    f"Keep every N.N.N heading as its own clause:\n\n{seg}"
                )},
            ]
            raw = await llm_call(
                "extract",
                msgs,
                temperature=0,
                response_format="json",
                max_tokens=4096,
                reasoning_effort="low",
            )
            return _iter_clause_items(parse_json_response(raw))

    results = await asyncio.gather(
        *[_one(i, seg) for i, seg in enumerate(segments)],
        return_exceptions=True,
    )

    merged: dict[str, dict] = {}
    order: list[str] = []
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            log.warning("segment %d failed: %s", idx + 1, res)
            continue
        for item in res:
            _merge_item(merged, order, item)

    if not merged:
        raise LLMError("extract_clauses produced 0 clauses from all segments")

    from app.config import get_model_config
    model_used = get_model_config()["extract"]["model"]

    result = [merged[cid] for cid in sorted(order, key=_clause_sort_key)]
    log.info("extract_clauses done: %d clauses, model=%s", len(result), model_used)
    return result, model_used
