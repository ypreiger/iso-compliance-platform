"""Translate ISO clause text via configured LLM gateway."""
from __future__ import annotations

import json
import re

import httpx

from app.config import get_settings


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

    settings = get_settings()
    if not settings.llm_gateway_url or not settings.llm_api_key:
        raise RuntimeError("LLM gateway not configured for translation")

    lang_name = {"en": "English", "he": "Hebrew"}
    prompt = (
        f"Translate the following ISO standard clause from {lang_name[source_language]} "
        f"to {lang_name[target_language]}. "
        'Return JSON only: {"title": "...", "body": "..."}. '
        "Preserve clause meaning and regulatory tone.\n\n"
        f"Title: {title}\n\nBody:\n{body}"
    )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.llm_gateway_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model_mapping,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        raise ValueError("LLM did not return JSON")
    data = json.loads(match.group())
    return str(data.get("title", title)), str(data.get("body", body))


async def translate_clause(title_en: str, body_en: str) -> tuple[str, str]:
    return await translate_clause_text(title_en, body_en, source_language="en", target_language="he")
