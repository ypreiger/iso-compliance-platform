"""Parse ISO standard text into structured clauses."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

CLAUSE_HEAD = re.compile(
    r"^(?:#{1,4}\s*)?"
    r"(\d{1,2}(?:\.\d{1,2}){0,3})"
    r"\s+"
    r"(.+?)\s*$",
    re.MULTILINE,
)

JUNK_RE = re.compile(
    r"(©\s*ISO|All rights reserved|Licensed to|ANSI order|Downloaded \d|^\s*ISO\s*\d|\d\s+\d\s+\d\s+\d\s+\d)",
    re.IGNORECASE,
)


def normalize_clause_id(clause_id: str) -> str:
    parts = [p for p in clause_id.strip().split(".") if p]
    if not parts or not all(p.isdigit() for p in parts):
        return clause_id.strip()
    return ".".join(str(int(p)) for p in parts)


def _clean_body(body: str) -> str:
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    clean = [p for p in paragraphs if not JUNK_RE.search(p)]
    return "\n\n".join(clean)


def is_plausible_clause(clause_id: str, title: str, body: str) -> bool:
    normalized = normalize_clause_id(clause_id)
    if not re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,4}", normalized):
        return False
    top = int(normalized.split(".")[0])
    if top < 1 or top > 10:
        return False
    title = title.strip()
    if len(title) < 2:
        return False
    if not re.search(r"[A-Za-z\u0590-\u05FF]", title):
        return False
    if body != "placeholder" and JUNK_RE.search(title):
        return False
    if re.fullmatch(r"[\d\s\.\,\;]+", title):
        return False
    return True


def preprocess_extracted_text(raw: str) -> str:
    """Fix common PDF/DOCX spacing artifacts before clause detection."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", text)
    return text


@dataclass
class ParsedClause:
    clause_id: str
    title: str
    body: str
    sort_order: int


def dedupe_clauses(clauses: list[ParsedClause]) -> tuple[list[ParsedClause], list[str]]:
    """Collapse duplicate clause_id values within one upload (merge bodies)."""
    by_id: dict[str, ParsedClause] = {}
    warnings: list[str] = []
    for clause in clauses:
        if clause.clause_id in by_id:
            warnings.append(f"Duplicate clause {clause.clause_id} in file; merged content")
            prev = by_id[clause.clause_id]
            merged_body = prev.body
            if clause.body.strip():
                merged_body = (
                    f"{merged_body}\n\n{clause.body}".strip() if merged_body.strip() else clause.body
                )
            by_id[clause.clause_id] = ParsedClause(
                clause.clause_id,
                clause.title or prev.title,
                merged_body,
                min(prev.sort_order, clause.sort_order),
            )
        else:
            by_id[clause.clause_id] = clause
    ordered = sorted(by_id.values(), key=lambda c: (c.sort_order, c.clause_id))
    return ordered, warnings


@dataclass
class BilingualUpload:
    standard: str
    en: list[ParsedClause]
    he: list[ParsedClause]


def _sort_key(clause_id: str) -> int:
    """Hierarchical sort key that keeps 4 < 4.1 < 4.2 < 5.

    We encode up to 5 hierarchy levels with fixed-width base-100 digits:
      4      -> 4,00,00,00,00
      4.1    -> 4,01,00,00,00
      4.1.2  -> 4,01,02,00,00
    This preserves natural clause order while still fitting INT.
    """
    parts = [int(p) for p in clause_id.split(".") if p.isdigit()]
    if not parts:
        return 0
    depth = 5
    padded = [min(p, 99) for p in parts[:depth]] + [0] * max(0, depth - len(parts))
    key = 0
    for p in padded:
        key = key * 100 + p
    return key


def parse_json_payload(raw: str, *, default_standard: str) -> tuple[str, list[ParsedClause]]:
    data = json.loads(raw)
    if isinstance(data, dict) and "clauses" in data:
        standard = data.get("standard", default_standard).upper().replace(" ", "")
        items = data["clauses"]
    elif isinstance(data, list):
        standard = default_standard.upper().replace(" ", "")
        items = data
    else:
        raise ValueError("JSON must be an array of clauses or {standard, clauses}")

    clauses: list[ParsedClause] = []
    for item in items:
        if "en" in item or "he" in item:
            raise ValueError("Use language-specific upload files; seed format with en/he is not supported here")
        lang_block = item.get("title") or item.get("body")
        if isinstance(lang_block, dict):
            raise ValueError("Nested en/he blocks require separate uploads per language")
        clause_id = normalize_clause_id(str(item["clause_id"]))
        title = str(item.get("title", ""))
        body = str(item.get("body", item.get("text", "")))
        sort_order = int(item.get("sort_order", _sort_key(clause_id)))
        clauses.append(ParsedClause(clause_id, title, body.strip(), sort_order))
    return standard, clauses


def parse_bilingual_json(raw: str, *, default_standard: str) -> BilingualUpload:
    """Parse seed-style JSON with en/he blocks per clause."""
    data = json.loads(raw)
    if isinstance(data, dict) and "clauses" in data:
        standard = data.get("standard", default_standard).upper().replace(" ", "")
        items = data["clauses"]
    elif isinstance(data, list):
        standard = default_standard.upper().replace(" ", "")
        items = data
    else:
        raise ValueError("JSON must be an array of clauses or {standard, clauses}")

    en_clauses: list[ParsedClause] = []
    he_clauses: list[ParsedClause] = []
    for item in items:
        clause_id = normalize_clause_id(str(item["clause_id"]))
        sort_order = int(item.get("sort_order", _sort_key(clause_id)))
        if "en" in item and isinstance(item["en"], dict):
            en_clauses.append(
                ParsedClause(
                    clause_id,
                    str(item["en"].get("title", "")),
                    str(item["en"].get("body", "")).strip(),
                    sort_order,
                )
            )
        if "he" in item and isinstance(item["he"], dict):
            he_clauses.append(
                ParsedClause(
                    clause_id,
                    str(item["he"].get("title", "")),
                    str(item["he"].get("body", "")).strip(),
                    sort_order,
                )
            )
    if not en_clauses and not he_clauses:
        raise ValueError("Bilingual JSON requires en/he objects per clause")
    return BilingualUpload(standard=standard, en=en_clauses, he=he_clauses)


def is_bilingual_json(content: bytes) -> bool:
    try:
        data = json.loads(content.decode("utf-8"))
        items = data.get("clauses", data) if isinstance(data, dict) else data
        return bool(items) and isinstance(items[0], dict) and ("en" in items[0] or "he" in items[0])
    except (json.JSONDecodeError, UnicodeDecodeError, IndexError, TypeError):
        return False


def parse_text_payload(raw: str, *, default_standard: str) -> tuple[str, list[ParsedClause]]:
    """Parse ISO document text using hierarchical line assignment."""
    from app.iso.clause_parse import parse_iso_document_text

    standard = default_standard.upper().replace(" ", "")
    text = preprocess_extracted_text(raw)
    clauses = parse_iso_document_text(text)
    return standard, clauses


def parse_upload(
    content: bytes,
    *,
    filename: str,
    standard: str,
    language: str,
) -> tuple[str, list[ParsedClause]]:
    if language not in ("en", "he", "both"):
        raise ValueError("language must be en, he, or both")

    lower = filename.lower()
    if lower.endswith(".json"):
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            raise ValueError("Empty file")
        if language == "both" or is_bilingual_json(content):
            raise ValueError("Use import_iso_upload for bilingual JSON")
        return parse_json_payload(text, default_standard=standard)
    if language == "both":
        raise ValueError("Bilingual bundle requires JSON with en/he blocks per clause")

    if lower.endswith((".pdf", ".doc", ".docx")):
        from app.iso.clause_parse import parse_document_bytes

        std = standard.upper().replace(" ", "")
        return std, parse_document_bytes(content, filename=filename)

    text = content.decode("utf-8", errors="replace").strip()

    if not text:
        raise ValueError("Empty file")
    if lower.endswith((".txt", ".md", ".markdown")):
        return parse_text_payload(text, default_standard=standard)
    raise ValueError("Unsupported format; use .json, .md, .txt, .pdf, .doc, or .docx")
