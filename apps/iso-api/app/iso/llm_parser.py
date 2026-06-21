"""LLM-powered ISO clause extraction agent.

Architecture:
  raw text (from PDF/DOC/DOCX)
      │
      ▼
  pre_segment()   ← split by top-level headings so each call is < 12 k tokens
      │
      ▼
  _llm_parse_segment()   ← GPT-4o single call per segment
      │
      ▼
  merge + dedupe          ← bodies for duplicate clause_ids are joined
      │
      ▼
  list[ParsedClause]

Falls back to regex-only parse if LLM is unavailable or returns bad JSON.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from app.iso.parser import ParsedClause, _sort_key, normalize_clause_id

log = logging.getLogger(__name__)

# Approximate token count: 1 token ≈ 4 chars.
# GPT-4o supports 128k context; we keep segments to ≤ 12 000 chars so the
# full prompt + large JSON response fits within typical 16k-output limits.
MAX_SEGMENT_CHARS = 12_000
SEGMENT_OVERLAP_CHARS = 400

SYSTEM_PROMPT = """You are an expert ISO standards document parser.
Your job is to extract every clause from the provided ISO standard text.

Rules:
- clause_id: ISO numbering like "4", "4.1", "4.1.1". Never include sub-section headings in clause_id.
- title: the clause heading text only (no clause_id prefix, no trailing period).
- body: ALL body text that belongs to this clause, verbatim, up to the next clause heading.
  Preserve paragraph breaks with \\n\\n. Do not truncate.
- Skip: table of contents, foreword, copyright notices, page numbers, bibliography.
- If you cannot determine a clause boundary, include the text in the parent clause body.

Return ONLY a JSON array, no markdown, no extra text:
[
  {"clause_id": "4", "title": "Context of the organization", "body": "..."},
  {"clause_id": "4.1", "title": "Understanding the organization and its context", "body": "..."},
  ...
]"""


def _openai_url() -> str:
    from app.config import get_settings

    s = get_settings()
    if s.llm_gateway_url:
        return f"{s.llm_gateway_url.rstrip('/')}/chat/completions"
    return "https://api.openai.com/v1/chat/completions"


def _api_key() -> str:
    from app.config import get_settings

    s = get_settings()
    return s.llm_api_key


def _llm_model() -> str:
    from app.config import get_settings

    s = get_settings()
    # prefer a capable model; fall back to gpt-4-turbo for compatibility
    model = s.llm_model_mapping or "gpt-4o"
    return model


# ── top-level section detection ────────────────────────────────────────────

_TOP_SECTION = re.compile(r"^(\d{1,2})\s+[A-Z\u0590-\u05FF]", re.MULTILINE)


def pre_segment(text: str) -> list[str]:
    """Split text at top-level ISO sections (4, 5, 6 …) to keep LLM calls small."""
    if len(text) <= MAX_SEGMENT_CHARS:
        return [text]

    # Find positions of top-level headings
    matches = list(_TOP_SECTION.finditer(text))
    if len(matches) < 2:
        # Can't detect sections; just window
        return _window_split(text)

    segments: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[start:end]
        if len(seg) > MAX_SEGMENT_CHARS:
            # Section is huge (e.g. Annex) — window it
            segments.extend(_window_split(seg))
        else:
            segments.append(seg)

    # Include text before the first detected section (foreword, TOC — usually skipped by LLM)
    preamble = text[: matches[0].start()].strip()
    if preamble and len(preamble) > 200:
        segments.insert(0, preamble)

    return segments


def _window_split(text: str) -> list[str]:
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + MAX_SEGMENT_CHARS, len(text))
        windows.append(text[start:end])
        start += MAX_SEGMENT_CHARS - SEGMENT_OVERLAP_CHARS
    return windows


# ── single-segment LLM call ────────────────────────────────────────────────

def _llm_parse_segment(
    segment: str,
    *,
    standard: str,
    language: str,
    retries: int = 3,
) -> list[dict[str, str]]:
    """Call the LLM for one text segment; return raw dicts."""
    key = _api_key()
    if not key:
        raise RuntimeError("No LLM API key configured (OPENAI_API_KEY / LLM_API_KEY)")

    user_prompt = (
        f"Standard: {standard}  Language: {language}\n\n"
        f"Extract all ISO clauses from the following text:\n\n{segment}"
    )

    payload = {
        "model": _llm_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=180) as client:
                resp = client.post(
                    _openai_url(),
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
                if resp.status_code == 429:
                    wait = 5 * (attempt + 1)
                    log.warning("LLM rate-limited; sleeping %ds", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
                # The model may wrap array in {"clauses": [...]} due to json_object mode
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
                # Try common wrapper keys
                for key_name in ("clauses", "data", "result", "items"):
                    if key_name in parsed and isinstance(parsed[key_name], list):
                        return parsed[key_name]
                # Return values if it's a dict of clause_id→obj
                if parsed and all(isinstance(v, dict) for v in parsed.values()):
                    return list(parsed.values())
                log.warning("Unexpected LLM response shape: %s", str(parsed)[:200])
                return []
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
            last_exc = exc
            log.warning("LLM call attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"LLM parsing failed after {retries} attempts: {last_exc}")


# ── merge duplicate clause entries ─────────────────────────────────────────

def _merge_results(raw_items: list[dict[str, str]]) -> list[ParsedClause]:
    seen: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for item in raw_items:
        cid_raw = str(item.get("clause_id", "")).strip()
        if not cid_raw:
            continue
        cid = normalize_clause_id(cid_raw)
        if not re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,4}", cid):
            continue  # skip junk

        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()

        if cid not in seen:
            seen[cid] = {"title": title, "body": body}
            order.append(cid)
        else:
            # Merge: keep title if not set; append body if not duplicate
            if not seen[cid]["title"] and title:
                seen[cid]["title"] = title
            if body and body not in seen[cid]["body"]:
                seen[cid]["body"] = (
                    f"{seen[cid]['body']}\n\n{body}".strip()
                    if seen[cid]["body"]
                    else body
                )

    clauses: list[ParsedClause] = []
    for i, cid in enumerate(order):
        entry = seen[cid]
        sort = _sort_key(cid)
        clauses.append(ParsedClause(cid, entry["title"], entry["body"], sort))

    # Re-sort by sort_order for clean output
    clauses.sort(key=lambda c: c.sort_order)
    return clauses


# ── public API ─────────────────────────────────────────────────────────────

def parse_text_with_llm(
    text: str,
    *,
    standard: str,
    language: str,
) -> list[ParsedClause]:
    """Parse ISO standard raw text using an LLM agent.

    Returns a list of ParsedClause objects in clause_id order.
    Raises RuntimeError if LLM is unavailable (caller should fall back).
    """
    segments = pre_segment(text)
    log.info(
        "LLM parse: %s/%s  %d chars  %d segments",
        standard,
        language,
        len(text),
        len(segments),
    )

    all_items: list[dict[str, str]] = []
    for idx, seg in enumerate(segments):
        log.info("  segment %d/%d (%d chars)", idx + 1, len(segments), len(seg))
        items = _llm_parse_segment(seg, standard=standard, language=language)
        all_items.extend(items)

    clauses = _merge_results(all_items)
    log.info("LLM parse done: %d clauses extracted", len(clauses))
    return clauses
