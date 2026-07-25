"""Translate ISO clause text via configured LLM gateway (EN↔HE)."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_LANG_NAME = {"en": "English", "he": "Hebrew"}

# Keep each LLM call small enough that JSON body output fits max_tokens.
_BODY_CHUNK_CHARS = 2800
_MIN_TARGET_RATIO = 0.45  # HE/EN length ratio floor for accepting a translation


def _parse_json_object(content: str) -> dict[str, Any]:
    """Parse a JSON object from the model. Refuse truncated / salvaged bodies."""
    match = re.search(r"\{[\s\S]*\}", content or "")
    if not match:
        raise ValueError("LLM did not return JSON")
    raw = match.group()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Do not salvage truncated JSON — that silently drops clause body text.
        raise ValueError(f"LLM returned truncated/invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("LLM JSON was not an object")
    return data


def _split_body_chunks(body: str, *, max_chars: int = _BODY_CHUNK_CHARS) -> list[str]:
    text = (body or "").strip()
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = re.split(r"\n\s*\n", text)
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if buf and len(buf) + len(para) + 2 > max_chars:
            chunks.append(buf)
            buf = para
        elif not buf:
            if len(para) <= max_chars:
                buf = para
            else:
                # Hard-split very long paragraphs on sentence boundaries.
                parts = re.split(r"(?<=[.!?])\s+", para)
                for part in parts:
                    if buf and len(buf) + len(part) + 1 > max_chars:
                        chunks.append(buf)
                        buf = part
                    else:
                        buf = f"{buf} {part}".strip() if buf else part
        else:
            buf = f"{buf}\n\n{para}"
    if buf:
        chunks.append(buf)
    return chunks or [text]


def _max_tokens_for(text: str) -> int:
    # Hebrew often similar length; leave headroom for JSON + title.
    estimate = int(len(text) * 1.2) + 256
    # ~4 chars/token rough; clamp to gateway-friendly range.
    tokens = max(1024, min(8192, math.ceil(estimate / 3)))
    return tokens


def _translation_too_short(source: str, target: str) -> bool:
    src = re.sub(r"\s+", "", source or "")
    dst = re.sub(r"\s+", "", target or "")
    if len(src) < 40:
        return False  # short clauses — don't over-reject
    if not dst:
        return True
    return len(dst) < len(src) * _MIN_TARGET_RATIO


async def _llm_json_translate(
    *,
    prompt: str,
    max_tokens: int,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_gateway_url or not settings.llm_api_key:
        raise RuntimeError("LLM gateway not configured for translation")

    payload = {
        "model": settings.llm_model_mapping,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "reasoning_effort": "low",
        "response_format": {"type": "json_object"},
    }
    url = f"{settings.llm_gateway_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=180, verify=False) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                choice = resp.json()["choices"][0]
                finish = choice.get("finish_reason") or choice.get("finishReason")
                message = choice["message"]
                content = (
                    message.get("content")
                    or message.get("reasoning_content")
                    or message.get("reasoning")
                    or ""
                )
            if finish == "length":
                raise ValueError("LLM hit max_tokens mid-translation (finish_reason=length)")
            return _parse_json_object(str(content))
        except Exception as exc:
            last_exc = exc
            log.warning("translate LLM attempt %d failed: %s", attempt + 1, exc)
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Translation failed: {last_exc}")


async def translate_clause_text(
    title: str,
    body: str,
    *,
    source_language: str,
    target_language: str,
) -> tuple[str, str]:
    if source_language not in ("en", "he") or target_language not in ("en", "he"):
        raise ValueError("source_language and target_language must be en or he")
    if source_language == target_language:
        return title, body

    src_name = _LANG_NAME[source_language]
    tgt_name = _LANG_NAME[target_language]
    body_src = body or ""

    # Translate title alone (short).
    title_prompt = (
        f"Translate this ISO clause title from {src_name} to {tgt_name}. "
        'Return JSON only: {"title":"..."}. Preserve meaning; no commentary.\n\n'
        f"Title: {title}"
    )
    title_data = await _llm_json_translate(prompt=title_prompt, max_tokens=256)
    title_out = str(title_data.get("title") or title).strip() or title

    chunks = _split_body_chunks(body_src)
    body_parts: list[str] = []
    for idx, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        prompt = (
            f"Translate the following ISO standard clause body from {src_name} to {tgt_name}. "
            f"This is part {idx + 1} of {len(chunks)} of one clause. "
            'Return JSON only: {"body":"..."}. '
            "Translate ALL text completely — do not summarize or omit sentences. "
            "Preserve shall/should modality, cross-references (see 4.2.5), and regulatory tone. "
            "Do not add commentary.\n\n"
            f"Body:\n{chunk}"
        )
        data = await _llm_json_translate(
            prompt=prompt,
            max_tokens=_max_tokens_for(chunk),
        )
        part = str(data.get("body") or "").strip()
        if not part:
            raise ValueError(f"Empty translation for body chunk {idx + 1}/{len(chunks)}")
        if _translation_too_short(chunk, part):
            raise ValueError(
                f"Translated body chunk {idx + 1} too short "
                f"({len(part)} chars vs source {len(chunk)}) — likely truncated"
            )
        body_parts.append(part)

    body_out = "\n\n".join(body_parts).strip() if body_parts else ""
    if body_src.strip() and not body_out:
        raise ValueError("Translation produced empty body")
    if _translation_too_short(body_src, body_out):
        raise ValueError(
            f"Translated body too short ({len(body_out)} vs source {len(body_src)})"
        )
    return title_out, body_out


async def translate_clause(title_en: str, body_en: str) -> tuple[str, str]:
    return await translate_clause_text(
        title_en, body_en, source_language="en", target_language="he"
    )


async def translate_clause_rows(
    rows: list[dict[str, Any]],
    *,
    source_language: str,
    target_language: str,
    concurrency: int = 4,
) -> tuple[list[tuple[str, str, str, int]], list[str]]:
    """Translate many clauses concurrently. Returns (translated, errors)."""
    from app.iso.parser import _sort_key, normalize_hebrew_body

    sem = asyncio.Semaphore(max(1, concurrency))
    translated: list[tuple[str, str, str, int]] = []
    errors: list[str] = []
    lock = asyncio.Lock()

    async def one(row: dict[str, Any]) -> None:
        cid = str(row["clause_id"])
        title = row.get("title") or ""
        body = row.get("body") or ""
        if source_language == "he":
            body = normalize_hebrew_body(body)
        try:
            async with sem:
                title_out, body_out = await translate_clause_text(
                    title,
                    body,
                    source_language=source_language,
                    target_language=target_language,
                )
            if target_language == "he":
                body_out = normalize_hebrew_body(body_out)
            item = (cid, title_out, body_out, _sort_key(cid))
            async with lock:
                translated.append(item)
        except Exception as exc:
            async with lock:
                errors.append(f"{cid}: {exc}")

    await asyncio.gather(*(one(r) for r in rows))
    translated.sort(key=lambda t: (t[3], t[0]))
    return translated, errors
