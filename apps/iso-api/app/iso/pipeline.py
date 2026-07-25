"""ISO document ingest pipeline.

Orchestrates the full flow for one uploaded file:

  1. store_file()      — save original bytes → corpus_files table
  2. parse_via_agent() — structure/regex first; LLM only when needed
  3. import_to_db()    — write to iso_clause_text + rag_documents
  4. validate()        — sample-check RAG retrieval quality
  5. return report     — stored in corpus_documents.metadata

Doc parse-agent endpoint is configured via DOC_PARSE_AGENT_URL env var
(fallback: DOC_AGENT_URL, default: http://iso-doc-parse-rag:8080).
"""
from __future__ import annotations

import base64
import logging
import os
import re
from typing import Any
from uuid import uuid4

import httpx

from app.iso.clause_parse import (
    ensure_parent_clauses,
    parse_document_bytes,
    promote_nested_clauses,
)
from app.iso.import_service import _import_language_clauses
from app.iso.parser import (
    ParsedClause,
    dedupe_clauses,
    normalize_hebrew_body,
    _sort_key,
)
from app.iso.rag_index import file_sha256
from app.iso.validate import validate_import

log = logging.getLogger(__name__)

_DOC_PARSE_AGENT_URL = (
    os.getenv("DOC_PARSE_AGENT_URL")
    or os.getenv("DOC_AGENT_URL")
    or "http://iso-doc-parse-rag:8080"
)


# ── step 1: file storage ───────────────────────────────────────────────────

def store_file(
    conn: Any,
    *,
    corpus_id: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    file_id = str(uuid4())
    conn.execute(
        """
        INSERT INTO corpus_files
          (id, corpus_id, filename, content_type, size_bytes, file_data)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (file_id, corpus_id, filename, content_type, len(content), content),
    )
    return file_id


# ── parse helpers ──────────────────────────────────────────────────────────

def _core_clauses(clauses: list[ParsedClause]) -> list[ParsedClause]:
    """Keep ISO introduction (0.x) + normative sections 1–10."""
    out: list[ParsedClause] = []
    for c in clauses:
        top = c.clause_id.split(".", 1)[0]
        if top.isdigit() and 0 <= int(top) <= 10:
            out.append(c)
    return out


def _normative_clauses(clauses: list[ParsedClause]) -> list[ParsedClause]:
    """Backward-compatible alias used by scoring helpers."""
    return _core_clauses(clauses)


def _level3_count(clauses: list[ParsedClause]) -> int:
    return sum(1 for c in clauses if c.clause_id.count(".") >= 2)


def _body_chars(clauses: list[ParsedClause]) -> int:
    return sum(len((c.body or "").strip()) for c in clauses)


def _bad_title(title: str, clause_id: str) -> bool:
    t = (title or "").strip()
    if not t or t.startswith("Clause "):
        return True
    if t in {"סעיף", "וסעיף", "א -", "( א -", "א-", "חשיבה", "– ה", "ה", "-", "–", "הקדמה"}:
        return True
    if re.search(r"https?://|www\.iso\.org", t, re.I):
        return True
    if re.search(r"ציור\s*\d|Figure\s*\d", t, re.I):
        return True
    if t.startswith(("הערה", "( הערה", "(הערה", "Note:", "NOTE")):
        return True
    if t.endswith((";", ",")) and not re.search(r"[\u0590-\u05FF]", t):
        return True
    # English sentence fragments used as titles ("evaluate the effectiveness...").
    if re.match(r"^[a-z]", t):
        return True
    if len(t) > 90 and not re.search(r"[\u0590-\u05FF]", t):
        return True
    # Body text stolen as a Hebrew title (long / multi-comma sentences).
    if re.search(r"[\u0590-\u05FF]", t) and (len(t) > 60 or t.count(",") >= 2):
        return True
    # Tiny Hebrew fragments are almost never real ISO headings.
    he = re.findall(r"[\u0590-\u05FF]+", t)
    if he and sum(len(x) for x in he) < 3:
        return True
    return False


def _structure_quality_ok(clauses: list[ParsedClause], *, language: str) -> bool:
    core = _core_clauses(clauses)
    if len(core) < 40:
        return False
    if _level3_count(core) < 12:
        return False
    min_chars = 8_000 if language.lower().startswith("he") else 4_000
    if _body_chars(core) < min_chars:
        return False
    # Reject parses whose titles are mostly garbage — common for HE PDFs where
    # extractors emit one token/line and structure invents headings.
    bad = sum(1 for c in core if _bad_title(c.title, c.clause_id))
    max_bad = 0.15 if language.lower().startswith("he") else 0.25
    if bad / max(1, len(core)) > max_bad:
        return False
    has_intro = any(c.clause_id == "0" or c.clause_id.startswith("0.") for c in core)
    if not has_intro:
        return False
    # Known anchors that a healthy ISO 9001 parse should contain.
    by_id = {c.clause_id: c for c in core}
    if "4.1" in by_id and _bad_title(by_id["4.1"].title, "4.1"):
        return False
    if "1" in by_id and _bad_title(by_id["1"].title, "1"):
        return False
    return True


def _dicts_to_clauses(raw_clauses: list[dict]) -> list[ParsedClause]:
    clauses = [
        ParsedClause(
            clause_id=c["clause_id"],
            title=c.get("title", ""),
            body=c.get("body", ""),
            sort_order=_sort_key(c["clause_id"]),
        )
        for c in raw_clauses
        if c.get("clause_id")
    ]
    return promote_nested_clauses(clauses)


def _local_structure_parse(
    content: bytes,
    *,
    filename: str,
) -> list[ParsedClause]:
    try:
        return promote_nested_clauses(parse_document_bytes(content, filename=filename))
    except Exception as exc:
        log.info("local structure parse unavailable (%s)", exc)
        return []


def _call_doc_agent(
    content: bytes,
    *,
    filename: str,
    standard: str,
    language: str,
    timeout: float = 600.0,
) -> dict:
    """POST to doc-agent /parse; return parsed response dict."""
    url = f"{_DOC_PARSE_AGENT_URL.rstrip('/')}/parse"
    payload = {
        "filename": filename,
        "content_b64": base64.b64encode(content).decode(),
        "standard": standard,
        "language": language,
        "task": "iso_clauses",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


def _inline_parse(
    content: bytes,
    *,
    filename: str,
    standard: str,
    language: str,
) -> tuple[list[ParsedClause], str]:
    """Inline fallback: extract text locally then call LLM directly."""
    from app.iso.document_extract import extract_text
    from app.iso.llm_parser import parse_text_with_llm
    from app.iso.clause_parse import parse_iso_document_text
    from app.iso.parser import preprocess_extracted_text

    raw_text = extract_text(content, filename=filename)
    raw_text = preprocess_extracted_text(raw_text)

    try:
        clauses = promote_nested_clauses(
            parse_text_with_llm(raw_text, standard=standard, language=language)
        )
        method = "llm-inline"
    except Exception as exc:
        log.warning("Inline LLM failed (%s); using regex", exc)
        clauses = parse_iso_document_text(raw_text, roll_up=False)
        method = "regex"

    return clauses, method


def _merge_clause_lists(*sets: list[ParsedClause]) -> list[ParsedClause]:
    """Union ParsedClause sets, preferring better titles and longer bodies."""
    best: dict[str, ParsedClause] = {}
    for clauses in sets:
        for clause in clauses or []:
            prev = best.get(clause.clause_id)
            if prev is None:
                best[clause.clause_id] = clause
                continue
            prev_bad = _bad_title(prev.title, prev.clause_id)
            cur_bad = _bad_title(clause.title, clause.clause_id)
            title = clause.title if (prev_bad and not cur_bad) or (
                not cur_bad and len(clause.title) > len(prev.title)
            ) else prev.title
            body = clause.body if len((clause.body or "").strip()) >= len((prev.body or "").strip()) else prev.body
            best[clause.clause_id] = ParsedClause(
                clause.clause_id,
                title or prev.title,
                body,
                min(prev.sort_order, clause.sort_order),
            )
    return sorted(best.values(), key=lambda c: (c.sort_order, c.clause_id))


def _choose_best(
    *,
    primary: list[ParsedClause],
    primary_method: str,
    fallback: list[ParsedClause],
    fallback_method: str,
    language: str,
) -> tuple[list[ParsedClause], str]:
    if not primary:
        return fallback, fallback_method
    if not fallback:
        return primary, primary_method

    p = _normative_clauses(primary) or primary
    f = _normative_clauses(fallback) or fallback
    p_l3, f_l3 = _level3_count(p), _level3_count(f)
    p_chars, f_chars = _body_chars(p), _body_chars(f)

    # Level-3 granularity is the product goal — prefer it when present.
    if p_l3 >= f_l3 + 5 and p_chars >= int(f_chars * 0.55):
        return primary, primary_method
    if f_l3 >= p_l3 + 5 and f_chars >= int(p_chars * 0.55):
        return fallback, fallback_method

    min_ratio = 0.85 if language.lower().startswith("he") else 0.70
    if len(p) >= max(1, int(len(f) * min_ratio)) and p_chars >= int(f_chars * min_ratio):
        return primary, primary_method
    return fallback, fallback_method


def parse_via_agent(
    content: bytes,
    *,
    filename: str,
    standard: str,
    language: str,
) -> tuple[list[ParsedClause], str]:
    """Parse document: structure/regex first, LLM only when coverage is weak.

    Returns (clauses, parse_method).
    """
    local = _local_structure_parse(content, filename=filename)
    local_ok = bool(local) and _structure_quality_ok(local, language=language)
    if local_ok:
        log.info(
            "structure-first parse OK: %d clauses (%d level-3); skipping LLM",
            len(local),
            _level3_count(local),
        )
        return local, "structure"

    # Prefer doc-agent (has concurrent gpt-oss extract + regex fidelity gate).
    try:
        result = _call_doc_agent(
            content, filename=filename, standard=standard, language=language
        )
        clauses = _dicts_to_clauses(result.get("clauses") or [])
        method = result.get("parse_method", "llm")
        log.info(
            "doc-agent parsed %d clauses (method=%s model=%s level3=%d)",
            len(clauses),
            method,
            result.get("model_used", "?"),
            _level3_count(clauses),
        )
        if clauses:
            # Merge agent output with local structure so HE keeps intro/IDs from
            # structure while adopting better LLM titles/bodies when available.
            if local:
                merged = _merge_clause_lists(clauses, local)
                if local_ok:
                    chosen, chosen_method = _choose_best(
                        primary=merged,
                        primary_method=f"{method}+structure",
                        fallback=local,
                        fallback_method="structure",
                        language=language,
                    )
                    return chosen, chosen_method
                return merged, f"{method}+structure"
            return clauses, method
        log.warning("doc-agent returned 0 clauses; falling back")
    except Exception as exc:
        log.warning("doc-agent unreachable (%s); falling back to inline parse", exc)

    try:
        inline, inline_method = _inline_parse(
            content, filename=filename, standard=standard, language=language
        )
        if inline:
            if local_ok:
                return _choose_best(
                    primary=inline,
                    primary_method=inline_method,
                    fallback=local,
                    fallback_method="structure",
                    language=language,
                )
            return inline, inline_method
    except Exception as exc:
        log.warning("inline parse failed (%s)", exc)

    if local:
        log.info("using local structure parse (%d clauses) as last resort", len(local))
        return local, "structure"
    raise ValueError("No ISO clauses extracted from document")


# Canonical titles are keyed by STANDARD then language.
# Never apply one standard's headings to another (e.g. ISO9001 "Support"
# must not become ISO13485 clause 7 — that is "Product realization").
_KNOWN_TITLES_BY_STANDARD: dict[str, dict[str, dict[str, str]]] = {
    "ISO9001": {
        "he": {
            "0": "מבוא",
            "0.1": "כללי",
            "0.2": "עקרונות ניהול איכות",
            "0.3": "גישה תהליכית",
            "0.3.1": "כללי",
            "0.3.2": "מחזור תכנן-עשה-בדוק-פעל (PDCA)",
            "0.3.3": "חשיבה מבוססת סיכונים",
            "0.4": "קשר לתקני מערכות ניהול אחרים",
            "1": "היקף",
            "2": "אזכורים נורמטיביים",
            "3": "מונחים והגדרות",
            "4": "הקשר הארגון",
            "4.1": "הבנת הארגון והקשרו",
            "4.2": "הבנת הצרכים והציפיות של מחזיקי עניין",
            "4.3": "קביעת היקף מערכת ניהול האיכות",
            "4.4": "מערכת ניהול איכות ותהליכיה",
            "5": "מנהיגות",
            "5.1": "מנהיגות ומחויבות",
            "5.1.1": "כללי",
            "5.1.2": "התמקדות בלקוח",
            "5.2": "מדיניות",
            "5.2.1": "קביעת מדיניות האיכות",
            "5.2.2": "תקשור מדיניות האיכות",
            "5.3": "תפקידים, אחריויות וסמכויות בארגון",
            "6": "תכנון",
            "7": "תמיכה",
            "7.1.3": "תשתית",
            "7.5.3.2": "בקרת מידע מתועד",
            "8": "תפעול",
            "8.2.3.2": "מידע מתועד לסקירת דרישות",
            "8.3.2": "תכנון תכן ופיתוח",
            "8.3.5": "תוצאות תכן ופיתוח",
            "8.4.2": "סוג והיקף הבקרה",
            "8.5.4": "שימור",
            "8.5.5": "פעילויות לאחר האספקה",
            "9": "הערכת ביצועים",
            "9.3": "סקירת הנהלה",
            "9.3.1": "כללי",
            "9.3.2": "קלט לסקירת הנהלה",
            "9.3.3": "פלט מסקירת הנהלה",
            "10": "שיפור",
        },
        "en": {
            "0": "Introduction",
            "0.1": "General",
            "0.2": "Quality management principles",
            "0.3": "Process approach",
            "0.3.1": "General",
            "0.3.2": "Plan-Do-Check-Act cycle",
            "0.3.3": "Risk-based thinking",
            "0.4": "Relationship with other management system standards",
            "1": "Scope",
            "2": "Normative references",
            "3": "Terms and definitions",
            "4": "Context of the organization",
            "4.1": "Understanding the organization and its context",
            "5": "Leadership",
            "5.1": "Leadership and commitment",
            "5.1.1": "General",
            "5.1.2": "Customer focus",
            "6": "Planning",
            "7": "Support",
            "8": "Operation",
            "9": "Performance evaluation",
            "10": "Improvement",
        },
    },
}

# Distinctive HLS titles used only to detect cross-standard contamination
# (correspondence annex bleed). Never used to invent titles for another standard.
_DISTINCTIVE_TITLES_BY_STANDARD: dict[str, dict[str, set[str]]] = {
    "ISO9001": {
        "en": {
            "Context of the organization",
            "Support",
            "Operation",
            "Performance evaluation",
            "Organizational knowledge",
            "Competence",
            "Resources",  # 9001 7.1 — not 13485 "Planning of product realization"
        },
        "he": {"תמיכה", "תפעול", "הערכת ביצועים", "הקשר הארגון", "משאבים"},
    },
    "ISO13485": {
        "en": {
            "Product realization",
            "Resource management",
            "Management responsibility",
            "Measurement, analysis and improvement",
        },
        "he": {"מימוש מוצר", "ניהול משאבים", "אחריות ההנהלה"},
    },
    "ISO14001": {
        "en": {"Environmental aspects", "Life cycle perspective"},
        "he": {"היבטים סביבתיים"},
    },
    "ISO45001": {
        "en": {"Hazard identification", "OH&S"},
        "he": {"זיהוי מפגעים"},
    },
}


def _normalize_standard_key(standard: str) -> str:
    return (standard or "").upper().replace(" ", "").replace("-", "")


def _title_fallback(clause_id: str, *, language: str) -> str:
    lang = language.lower()[:2]
    return f"סעיף {clause_id}" if lang == "he" else f"Clause {clause_id}"


def _is_foreign_standard_title(title: str, *, standard: str, language: str) -> bool:
    """True when title matches a distinctive heading from a *different* standard."""
    std = _normalize_standard_key(standard)
    lang = language.lower()[:2]
    cleaned = (title or "").strip()
    if not cleaned:
        return False
    for other_std, by_lang in _DISTINCTIVE_TITLES_BY_STANDARD.items():
        if other_std == std:
            continue
        markers = by_lang.get(lang, set())
        for marker in markers:
            if cleaned == marker or cleaned.startswith(marker + " ") or f" {marker}" in cleaned:
                # Own-standard distinctive titles are OK even if they share words.
                own = _DISTINCTIVE_TITLES_BY_STANDARD.get(std, {}).get(lang, set())
                if cleaned in own:
                    return False
                return True
    return False


def _repair_known_titles(
    clauses: list[ParsedClause],
    *,
    language: str,
    standard: str,
) -> list[ParsedClause]:
    """Fix broken titles using *this standard's* dictionary only.

    Never copies titles from another ISO standard. For non-ISO9001 uploads,
    bad/garbage titles fall back to ``Clause {id}`` / ``סעיף {id}`` — not HLS
    headings borrowed from ISO 9001.
    """
    std = _normalize_standard_key(standard)
    lang = language.lower()[:2]
    known = _KNOWN_TITLES_BY_STANDARD.get(std, {}).get(lang, {})
    out: list[ParsedClause] = []
    for clause in clauses:
        title = (clause.title or "").strip()
        canonical = known.get(clause.clause_id)  # None unless this standard has a map
        foreign = _is_foreign_standard_title(title, standard=std, language=lang)
        if foreign:
            # Correspondence-annex / crosswalk pollution — never keep foreign HLS.
            title = canonical or _title_fallback(clause.clause_id, language=lang)
        elif canonical and (
            _bad_title(title, clause.clause_id)
            or (
                title != canonical
                and (
                    len(title) > 60
                    or "ציור" in title
                    or (
                        title in {"הקדמה", "מנהיגות ומחויבות"}
                        and clause.clause_id in {"0.1", "5.1.1"}
                    )
                )
            )
        ):
            title = canonical
        elif _bad_title(title, clause.clause_id):
            # Never leave body-text / garbage as a heading in the viewer.
            title = canonical or _title_fallback(clause.clause_id, language=lang)
        out.append(ParsedClause(clause.clause_id, title, clause.body, clause.sort_order))
    return out


def _normalize_clause_bodies(clauses: list[ParsedClause], *, language: str) -> list[ParsedClause]:
    if not language.lower().startswith("he"):
        return clauses
    return [
        ParsedClause(
            c.clause_id,
            c.title,
            normalize_hebrew_body(c.body or ""),
            c.sort_order,
        )
        for c in clauses
    ]


# ── main pipeline ──────────────────────────────────────────────────────────

def run_ingest_pipeline(
    conn: Any,
    *,
    content: bytes,
    filename: str,
    standard: str,
    language: str,
    edition: str,
    corpus_id: str,
    admin_id: str | None,
    replace_previous: bool = True,
    skip_store: bool = False,
    file_id: str | None = None,
) -> dict:
    std = standard.upper().replace(" ", "")
    sha = file_sha256(content)
    steps: list[dict] = []

    def log_step(name: str, **kwargs) -> None:
        steps.append({"step": name, **kwargs})
        log.info("pipeline[%s/%s] %s %s", std, language, name, kwargs)

    # 1. Store original file (skipped when caller already persisted + committed)
    if skip_store:
        if not file_id:
            raise ValueError("file_id is required when skip_store=True")
        log_step("store_file", file_id=file_id, size_bytes=len(content), skipped=True)
    else:
        content_type = _infer_content_type(filename)
        file_id = store_file(
            conn, corpus_id=corpus_id, filename=filename,
            content=content, content_type=content_type,
        )
        log_step("store_file", file_id=file_id, size_bytes=len(content))
        # Commit before LLM parse — holding RowExclusiveLocks across minutes of
        # GPT-oss work blocks CREATE TABLE IF NOT EXISTS on new API pods (NetworkError).
        if hasattr(conn, "commit"):
            conn.commit()

    # 2. Parse via agent (no open DB transaction)
    parsed, method = parse_via_agent(
        content, filename=filename, standard=std, language=language
    )
    parsed, warnings = dedupe_clauses(parsed)
    parsed = ensure_parent_clauses(promote_nested_clauses(parsed))
    parsed = _repair_known_titles(parsed, language=language, standard=std)
    parsed = _normalize_clause_bodies(parsed, language=language)

    if not parsed:
        raise ValueError(
            "No ISO clauses extracted. Ensure the document contains structured "
            "text with clause headings like '4.1 Title'."
        )
    log_step(
        "parse",
        method=method,
        clauses=len(parsed),
        level3=_level3_count(parsed),
        warnings=len(warnings),
    )

    # 3. Import to DB + RAG
    rag_chunks = _import_language_clauses(
        conn,
        std=std, language=language, edition=edition,
        clauses=parsed, corpus_id=corpus_id,
        filename=filename, sha=sha,
        replace_previous=replace_previous,
    )
    log_step("import_db", clauses=len(parsed), rag_chunks=rag_chunks)

    # 4. Validate
    report = validate_import(conn, standard=std, language=language, sample_n=20)
    log_step(
        "validate",
        rag_hit_rate=report.rag_hit_rate,
        phrase_hit_rate=report.phrase_hit_rate,
        passed=report.passed,
    )

    return {
        "file_id": file_id,
        "sha256": sha,
        "parse_method": method,
        "clauses_imported": len(parsed),
        "level3_clauses": _level3_count(parsed),
        "rag_chunks": rag_chunks,
        "warnings": warnings,
        "validation": report.to_dict(),
        "steps": steps,
        "replace_previous": replace_previous,
    }


def _infer_content_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".doc"):
        return "application/msword"
    return "application/octet-stream"
