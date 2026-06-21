"""Parse ISO documents preserving source order (PDF/DOC/DOCX)."""
from __future__ import annotations

import re
from io import BytesIO

from app.iso.parser import (
    ParsedClause,
    _clean_body,
    is_plausible_clause,
    normalize_clause_id,
    preprocess_extracted_text,
)

CLAUSE_LINE = re.compile(
    r"^(?:#{1,4}\s*)?"
    r"(\d{1,2}(?:\.\d{1,2}){0,4})"
    r"(?:\s*[\.\)]?\s*)"
    r"(\S(?:.*\S)?)\s*$"
)
CLAUSE_ID_ONLY = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,4}$")

JUNK_LINE = re.compile(
    r"(©\s*ISO|All rights reserved|Licensed to|ANSI order|Downloaded \d/"
    r"|^\s*ISO\s*9001|\bINTERNATIONAL\s+STANDARD\b|^\d+\s*$)",
    re.IGNORECASE,
)


def clause_level(clause_id: str) -> int:
    return len(normalize_clause_id(clause_id).split("."))


def try_clause_header(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or JUNK_LINE.search(stripped):
        return None
    match = CLAUSE_LINE.match(stripped)
    if not match:
        return None
    clause_id = normalize_clause_id(match.group(1))
    title = match.group(2).strip()
    if len(title) > 240:
        return None
    if not is_plausible_clause(clause_id, title, "placeholder"):
        return None
    return clause_id, title


def split_title_and_lead_body(title: str) -> tuple[str, str]:
    t = title.strip()
    norm = re.search(r"\b(shall|must|should|חייב|יידרש| יש )\b", t, re.IGNORECASE)
    if norm and norm.start() > 4:
        head = t[: norm.start()].strip().rstrip(".")
        tail = t[norm.start() :].strip()
        return head or "Requirements", tail
    if len(t) > 90:
        cut = t[:80].rsplit(" ", 1)[0]
        return cut, t[len(cut) :].strip()
    return t, ""


def repair_broken_words(text: str) -> str:
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was", "be", "to", "of", "in",
        "on", "at", "by", "or", "an", "as", "is", "it", "its", "shall", "will", "not", "may", "can",
        "has", "have", "had", "were", "been", "being",
    }
    # Apply only to latin words. Running this on Hebrew caused valid words
    # to be merged and damaged clause readability.
    return re.sub(
        r"\b([a-z]{2,4})\s+([a-z]{4,})\b",
        lambda m: m.group(1) + m.group(2) if m.group(1) not in stop else m.group(0),
        text,
    )


def reflow_continuation_lines(text: str) -> list[str]:
    raw_lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n")]
    logical: list[str] = []
    buffer = ""

    def flush_buffer() -> None:
        nonlocal buffer
        if buffer:
            logical.append(buffer)
            buffer = ""

    for line in raw_lines:
        if not line:
            flush_buffer()
            continue
        if try_clause_header(line):
            flush_buffer()
            logical.append(line)
            continue
        # Common PDF extraction pattern:
        #   4.1
        #   Understanding the organization...
        # Join these two lines into one clause header.
        if buffer and CLAUSE_ID_ONLY.fullmatch(buffer):
            joined = f"{buffer} {line}"
            if try_clause_header(joined):
                logical.append(joined)
                buffer = ""
                continue
        if not buffer:
            buffer = line
            continue
        last = buffer.split()[-1] if buffer else ""
        if last and len(last) <= 4 and last.isalpha() and line[0].islower():
            buffer = f"{buffer}{line}"
        elif line[0].islower() or len(line) < 48:
            buffer = f"{buffer} {line}"
        else:
            flush_buffer()
            buffer = line
    flush_buffer()
    return logical


def _append_body(store: dict[str, list[str]], clause_id: str, text: str) -> None:
    if text.strip():
        store.setdefault(clause_id, []).append(text.strip())


def parse_docx_faithful(content: bytes) -> list[ParsedClause]:
    """Walk DOCX blocks in document order; assign paragraphs to clauses faithfully."""
    from docx import Document

    from app.iso.document_extract import iter_docx_blocks

    doc = Document(BytesIO(content))
    clauses_by_id: dict[str, ParsedClause] = {}
    order: list[str] = []
    body_parts: dict[str, list[str]] = {}
    current_id: str | None = None
    seq = 0

    def open_clause(clause_id: str, title: str) -> None:
        nonlocal current_id, seq
        short_title, lead = split_title_and_lead_body(title)
        if clause_id not in clauses_by_id:
            clauses_by_id[clause_id] = ParsedClause(clause_id, short_title, "", seq)
            order.append(clause_id)
            seq += 1
            body_parts[clause_id] = []
        else:
            clauses_by_id[clause_id].title = short_title or clauses_by_id[clause_id].title
        if lead:
            _append_body(body_parts, clause_id, lead)
        current_id = clause_id

    for block in iter_docx_blocks(doc):
        if block.__class__.__name__ == "Paragraph":
            text = re.sub(r"\s+", " ", block.text).strip()
            if not text:
                continue
            style = (block.style.name or "").lower() if block.style else ""
            header = try_clause_header(text)
            if header:
                open_clause(header[0], header[1])
                continue
            if current_id:
                _append_body(body_parts, current_id, text)
        else:
            for row in block.rows:
                cells = [re.sub(r"\s+", " ", c.text).strip() for c in row.cells if c.text.strip()]
                if not cells:
                    continue
                joined = " ".join(cells)
                header = try_clause_header(joined)
                if header and len(joined) < 200:
                    open_clause(header[0], header[1])
                elif current_id:
                    _append_body(body_parts, current_id, joined)

    result: list[ParsedClause] = []
    for clause_id in order:
        clause = clauses_by_id[clause_id]
        body = repair_broken_words(_clean_body("\n\n".join(body_parts.get(clause_id, []))))
        result.append(ParsedClause(clause.clause_id, clause.title, body, clause.sort_order))
    if not result:
        raise ValueError("No clause headings found in DOC/DOCX")
    return result


def parse_hierarchical_lines(lines: list[str], *, roll_up: bool = False) -> list[ParsedClause]:
    clauses_by_id: dict[str, ParsedClause] = {}
    order: list[str] = []
    stack: list[str] = []
    body_parts: dict[str, list[str]] = {}
    seq = 0

    def start_clause(clause_id: str, title: str) -> None:
        nonlocal seq
        level = clause_level(clause_id)
        while stack and clause_level(stack[-1]) >= level:
            stack.pop()
        short_title, lead = split_title_and_lead_body(title)
        if clause_id not in clauses_by_id:
            clauses_by_id[clause_id] = ParsedClause(clause_id, short_title, "", seq)
            order.append(clause_id)
            seq += 1
            body_parts[clause_id] = []
        else:
            clauses_by_id[clause_id].title = short_title or clauses_by_id[clause_id].title
        if lead:
            _append_body(body_parts, clause_id, lead)
        stack.append(clause_id)

    for line in lines:
        header = try_clause_header(line)
        if header:
            start_clause(header[0], header[1])
            continue
        if stack and not JUNK_LINE.search(line):
            _append_body(body_parts, stack[-1], line)

    result: list[ParsedClause] = []
    for clause_id in order:
        clause = clauses_by_id[clause_id]
        body = repair_broken_words(_clean_body("\n\n".join(body_parts.get(clause_id, []))))
        result.append(ParsedClause(clause.clause_id, clause.title, body, clause.sort_order))

    if roll_up:
        result = roll_up_empty_parents(result)
    return result


def roll_up_empty_parents(clauses: list[ParsedClause]) -> list[ParsedClause]:
    by_id = {c.clause_id: c for c in clauses}
    children: dict[str, list[str]] = {}
    for cid in by_id:
        parts = cid.split(".")
        if len(parts) > 1:
            parent = ".".join(parts[:-1])
            if parent in by_id:
                children.setdefault(parent, []).append(cid)

    updated: list[ParsedClause] = []
    for clause in clauses:
        body = clause.body.strip()
        if not body and clause.clause_id in children:
            chunks: list[str] = []
            for child_id in sorted(children[clause.clause_id], key=lambda x: by_id[x].sort_order):
                child = by_id[child_id]
                child_body = child.body.strip() or child.title
                if child_body:
                    chunks.append(f"{child_id} {child.title}\n\n{child_body}")
            body = "\n\n".join(chunks)
        updated.append(ParsedClause(clause.clause_id, clause.title, body, clause.sort_order))
    return updated


def parse_iso_document_text(raw: str, *, roll_up: bool = False) -> list[ParsedClause]:
    lines = reflow_continuation_lines(raw)
    clauses = parse_hierarchical_lines(lines, roll_up=roll_up)
    if not clauses:
        raise ValueError(
            "No ISO clause headings found in document text. "
            "Ensure lines like '4.1 Understanding the organization' exist."
        )
    return [c for c in clauses if c.title.strip()]


def parse_document_bytes(content: bytes, *, filename: str) -> list[ParsedClause]:
    """Single entry for PDF/DOC/DOCX uploads (regex-based, no LLM)."""
    from app.iso.document_extract import extract_text

    lower = filename.lower()
    if lower.endswith(".docx"):
        # Use DOCX block walk for best structure preservation
        return parse_docx_faithful(content)
    if lower.endswith((".pdf", ".doc")):
        text = extract_text(content, filename=filename)
        text = preprocess_extracted_text(text)
        return parse_iso_document_text(text, roll_up=False)
    raise ValueError("Use parse_upload for .json/.md/.txt")
