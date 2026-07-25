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
    # 0.x = Introduction; 1–10 = normative requirements.
    if top < 0 or top > 10:
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
    # Reject obvious non-titles that structure parse sometimes attaches.
    if re.search(r"https?://|www\.iso\.org", title, re.I):
        return False
    if title in {"סעיף", "א -", "( א -", "א-", "Clause"}:
        return False
    return True


def strip_correspondence_annexes(text: str) -> str:
    """Remove informative comparison/correspondence annexes before parsing.

    ISO 13485 Annex B (and similar tables) list ISO 9001 clause IDs beside
    ISO 13485 IDs. If parsed, they overwrite real titles with hybrids such as
    ``7 Support 6 Resource management`` instead of ``7 Product realization``.
    """
    patterns = (
        # Annex B correspondence / Annex A comparison tables
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
    if cut is None:
        return text
    return text[:cut].rstrip()


def strip_toc_artifact_lines(text: str) -> str:
    """Drop table-of-contents rows so they cannot pollute clause bodies/titles."""
    out: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if re.search(r"\.{5,}|…{3,}", s):
            continue
        if re.match(
            r"^Annex\s+[A-Z]\s*\(informative\).+\d+\s*$",
            s,
            re.I,
        ):
            continue
        if re.match(
            r"^(Foreword|Introduction|Bibliography|Contents)\b.+\d+\s*$",
            s,
            re.I,
        ) and re.search(r"\d+\s*$", s):
            continue
        out.append(line)
    return "\n".join(out)


def preprocess_extracted_text(raw: str) -> str:
    """Fix common PDF/DOCX spacing artifacts before clause detection."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = strip_correspondence_annexes(text)
    text = strip_toc_artifact_lines(text)
    text = re.sub(r"(\d)\s+\.\s+(\d)", r"\1.\2", text)
    # Hebrew/RTL extractors often emit leading dots: ".5.1.1" → "5.1.1"
    text = re.sub(
        r"(?m)^\.+(\d{1,2}(?:\.\d{1,2}){0,4})(?=\s|$)",
        r"\1",
        text,
    )
    text = re.sub(
        r"(?m)([^\d.])\.+(\d{1,2}(?:\.\d{1,2}){0,4})(?=\s|$)",
        r"\1\2",
        text,
    )
    # Hebrew PDFs often emit one token per line; rejoin prefix letters / wraps.
    text = _rejoin_hebrew_line_tokens(text)
    # Normalize intro section headings used by ISO EN/HE editions.
    text = re.sub(r"(?im)^(Introduction|מבוא)\s*$", r"0 \1", text)
    # TOC artifact: "1 Scope1" / "2 Normative references1" → split page numeral.
    text = re.sub(
        r"(?m)^(\d{1,2}(?:\.\d{1,2}){0,4})\s+([A-Za-z\u0590-\u05FF].*?[A-Za-z\u0590-\u05FF])(\d{1,3})\s*$",
        r"\1 \2",
        text,
    )
    return text


_CLAUSE_ID_LINE = re.compile(r"^\.?\d{1,2}(?:\.\d{1,2}){0,4}(?:\s|$)")


def _is_short_hebrew_token_line(line: str) -> bool:
    """True for one-word / short Hebrew lines produced by tokenized PDFs."""
    s = line.strip()
    if not s or len(s) > 48:
        return False
    if _CLAUSE_ID_LINE.match(s):
        return False
    letters = re.findall(r"[A-Za-z\u0590-\u05FF]", s)
    if not letters:
        return False
    he = sum(1 for ch in letters if "\u0590" <= ch <= "\u05FF")
    if he / len(letters) < 0.5:
        return False
    return len(s.split()) <= 5


def _rejoin_hebrew_line_tokens(text: str) -> str:
    """Join split Hebrew prefix letters before clause detection.

    Keep this conservative: aggressive paragraph collapse here breaks the
    Hebrew title-before-id pattern (e.g. "כללי" then ".5.1.1").
    """
    lines = [ln.strip() for ln in text.split("\n")]
    out: list[str] = []
    i = 0
    prefix = set("ובכלמהש")
    while i < len(lines):
        ln = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if (
            ln
            and nxt
            and re.fullmatch(r"[\u0590-\u05FF]{1,2}", ln)
            and re.match(r"[\u0590-\u05FF]", nxt)
            and not re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,4}", nxt)
        ):
            if len(ln) == 1 or ln in prefix:
                out.append(ln + nxt)
                i += 2
                continue
        if (
            ln
            and nxt
            and re.fullmatch(r"[\u0590-\u05FF]{2,8}", ln)
            and re.fullmatch(r"[\u0590-\u05FF]{1,4}", nxt)
            and len(ln) + len(nxt) <= 12
            and not re.fullmatch(r"\d{1,2}(?:\.\d{1,2}){0,4}", nxt)
        ):
            if len(nxt) <= 2:
                out.append(ln + nxt)
                i += 2
                continue
        out.append(ln)
        i += 1
    return "\n".join(out)


def _collapse_hebrew_token_paragraphs(text: str) -> str:
    """Collapse one-word-per-line Hebrew bodies into readable paragraphs.

    Used only on already-parsed clause bodies — never on full-document text
    before heading detection.
    """
    lines = [ln.strip() for ln in text.split("\n")]
    out: list[str] = []
    buf: list[str] = []

    def flush_buf(*, paragraph_break: bool = False) -> None:
        nonlocal buf
        if not buf:
            return
        out.append(" ".join(buf))
        buf = []
        if paragraph_break:
            out.append("")

    for ln in lines:
        if not ln:
            continue
        if _CLAUSE_ID_LINE.match(ln) and not _is_short_hebrew_token_line(ln):
            flush_buf(paragraph_break=True)
            out.append(ln)
            continue
        if _is_short_hebrew_token_line(ln):
            buf.append(ln)
            if ln.endswith((".", ":", ";", "?", "!")) and len(buf) >= 6:
                flush_buf(paragraph_break=True)
            continue
        flush_buf(paragraph_break=True)
        out.append(ln)
    flush_buf()

    cleaned: list[str] = []
    for ln in out:
        if ln == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(ln)
    return "\n".join(cleaned)


def normalize_hebrew_body(body: str) -> str:
    """Re-join tokenized Hebrew clause bodies for display / storage."""
    if not body or not re.search(r"[\u0590-\u05FF]", body):
        return body
    # Lazy import avoids circular import with document_extract helpers.
    from app.iso.document_extract import _fix_hebrew_spacing

    rejoined = _collapse_hebrew_token_paragraphs(_rejoin_hebrew_line_tokens(body))
    return _fix_hebrew_spacing(rejoined)


@dataclass
class ParsedClause:
    clause_id: str
    title: str
    body: str
    sort_order: int


def dedupe_clauses(clauses: list[ParsedClause]) -> tuple[list[ParsedClause], list[str]]:
    """Collapse duplicate clause_id values within one upload (merge bodies).

    First occurrence wins for titles (main body before correspondence annexes).
    Later duplicates may only fill an empty body — never overwrite a real title.
    """
    by_id: dict[str, ParsedClause] = {}
    warnings: list[str] = []
    for clause in clauses:
        if clause.clause_id in by_id:
            warnings.append(f"Duplicate clause {clause.clause_id} in file; kept first title")
            prev = by_id[clause.clause_id]
            merged_body = prev.body
            if not merged_body.strip() and clause.body.strip():
                merged_body = clause.body
            title = prev.title if prev.title.strip() else clause.title
            by_id[clause.clause_id] = ParsedClause(
                clause.clause_id,
                title,
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
