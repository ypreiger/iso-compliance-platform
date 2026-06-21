"""ISO document ingest pipeline.

Orchestrates the full flow for one uploaded file:

  1. store_file()      — save original bytes → corpus_files table
  2. parse_via_agent() — call doc-agent /parse (LLM + text extraction)
                         falls back to inline LLM if doc-agent unreachable
  3. import_to_db()    — write to iso_clause_text + rag_documents
  4. validate()        — sample-check RAG retrieval quality
  5. return report     — stored in corpus_documents.metadata

Doc-agent endpoint is configured via DOC_AGENT_URL env var
(default: http://iso-docgen:8080 — the in-cluster service name on OpenShift).
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any
from uuid import uuid4

import httpx

from app.iso.import_service import _import_language_clauses
from app.iso.parser import ParsedClause, dedupe_clauses, _sort_key
from app.iso.rag_index import file_sha256
from app.iso.validate import validate_import

log = logging.getLogger(__name__)

_DOC_AGENT_URL = os.getenv("DOC_AGENT_URL", "http://iso-docgen:8080")


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


# ── step 2: parse via doc-agent ────────────────────────────────────────────

def _call_doc_agent(
    content: bytes,
    *,
    filename: str,
    standard: str,
    language: str,
    timeout: float = 300.0,
) -> dict:
    """POST to doc-agent /parse; return parsed response dict."""
    url = f"{_DOC_AGENT_URL.rstrip('/')}/parse"
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

    raw_text = extract_text(content, filename=filename)

    try:
        clauses = parse_text_with_llm(raw_text, standard=standard, language=language)
        method = "llm-inline"
    except Exception as exc:
        log.warning("Inline LLM failed (%s); using regex", exc)
        clauses = parse_iso_document_text(raw_text, roll_up=False)
        method = "regex"

    return clauses, method


def parse_via_agent(
    content: bytes,
    *,
    filename: str,
    standard: str,
    language: str,
) -> tuple[list[ParsedClause], str]:
    """Parse document via doc-agent, fall back to inline if unreachable.

    Returns (clauses, parse_method).
    """
    try:
        result = _call_doc_agent(
            content, filename=filename, standard=standard, language=language
        )
        raw_clauses = result.get("clauses") or []
        method = result.get("parse_method", "llm")
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
        log.info(
            "doc-agent parsed %d clauses (method=%s model=%s)",
            len(clauses), method, result.get("model_used", "?"),
        )
        if clauses:
            return clauses, method
        log.warning("doc-agent returned 0 clauses; falling back to inline")
    except Exception as exc:
        log.warning("doc-agent unreachable (%s); falling back to inline parse", exc)

    return _inline_parse(content, filename=filename, standard=standard, language=language)


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
) -> dict:
    std = standard.upper().replace(" ", "")
    sha = file_sha256(content)
    steps: list[dict] = []

    def log_step(name: str, **kwargs) -> None:
        steps.append({"step": name, **kwargs})
        log.info("pipeline[%s/%s] %s %s", std, language, name, kwargs)

    # 1. Store original file
    content_type = _infer_content_type(filename)
    file_id = store_file(
        conn, corpus_id=corpus_id, filename=filename,
        content=content, content_type=content_type,
    )
    log_step("store_file", file_id=file_id, size_bytes=len(content))

    # 2. Parse via agent
    parsed, method = parse_via_agent(
        content, filename=filename, standard=std, language=language
    )
    parsed, warnings = dedupe_clauses(parsed)

    if not parsed:
        raise ValueError(
            "No ISO clauses extracted. Ensure the document contains structured "
            "text with clause headings like '4.1 Title'."
        )
    log_step("parse", method=method, clauses=len(parsed), warnings=len(warnings))

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
