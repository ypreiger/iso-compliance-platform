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
    r"|^\s*ISO\s*9001|\bINTERNATIONAL\s+STANDARD\b|^\d+\s*$"
    r"|\.{10,}|…{3,})",  # Table of contents dotted leaders
    re.IGNORECASE,
)


def clause_level(clause_id: str) -> int:
    return len(normalize_clause_id(clause_id).split("."))


def try_clause_header(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or JUNK_LINE.search(stripped):
        return None

    # Skip table of contents lines (clause + title + dots/page number)
    # Pattern: "4.1 Understanding the organization.................5"
    if re.search(r'\.{5,}', stripped):  # Line has 5+ consecutive dots = TOC entry
        return None

    # Skip quoted references to clauses (e.g., in Annex or commentary)
    # Pattern: '4.1: "The organization shall...' or '4.1: "The organization...'
    # Handles both ASCII quotes and Unicode smart quotes
    if re.match(r'^\d+(?:\.\d+)*:\s*["\'“”‘’]', stripped):
        return None

    match = CLAUSE_LINE.match(stripped)
    if not match:
        return None
    clause_id = normalize_clause_id(match.group(1))
    title = match.group(2).strip()

    # Clean up any remaining TOC artifacts
    title = re.sub(r'\.{3,}.*$', '', title).strip()  # Remove trailing dots and everything after
    title = re.sub(r'…{2,}.*$', '', title).strip()   # Remove ellipsis
    title = re.sub(r'\s+\d+\s*$', '', title).strip()  # Remove trailing page numbers

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


def parse_docx_by_structure(content: bytes) -> list[ParsedClause]:
    """Parse DOCX by heading hierarchy when clause numbers aren't in text.

    Detects heading level pattern (English uses H3/H5/H6, Hebrew uses H1/H2) and
    maps to clause numbers: top level = 1,2,3..., second level = X.1, X.2...
    """
    from docx import Document

    from app.iso.document_extract import iter_docx_blocks

    doc = Document(BytesIO(content))

    # Detect which heading levels are used by sampling
    heading_levels_found = set()
    for para in doc.paragraphs[:300]:
        if para.style and 'heading' in para.style.name.lower():
            heading_levels_found.add(para.style.name.lower())

    # Determine heading level mapping
    if 'heading 3' in heading_levels_found:
        # English pattern: H3=top, H5=sub, H6=subsub
        level_map = {'heading 3': 0, 'heading 5': 1, 'heading 6': 2}
        start_keywords = ["scope", "normative", "terms", "context"]
    else:
        # Hebrew pattern: H1=top, H2=sub
        level_map = {'heading 1': 0, 'heading 2': 1}
        start_keywords = ["חלות", "אזכור", "מונחים", "הקשר"]  # Hebrew equivalents

    clauses: list[ParsedClause] = []
    clause_counters = [0, 0, 0, 0]
    current_clause_id = ""
    body_parts: dict[str, list[str]] = {}
    seq = 0
    started = False

    for block in iter_docx_blocks(doc):
        if block.__class__.__name__ == "Paragraph":
            text = re.sub(r"\s+", " ", block.text).strip()
            if not text:
                continue

            style = (block.style.name or "").lower() if block.style else ""

            # Start numbering when we hit first main section
            if not started and style in level_map:
                text_lower = text.lower()
                if level_map[style] == 0 and any(kw in text_lower for kw in start_keywords):
                    started = True

            if not started:
                continue

            # Get heading level (0=top, 1=second, 2=third)
            if style not in level_map:
                # Regular paragraph
                if current_clause_id:
                    _append_body(body_parts, current_clause_id, text)
                continue

            level = level_map[style]

            if level == 0:
                # Top level: 1, 2, 3, 4...
                clause_counters[0] += 1
                clause_counters[1] = 0
                clause_counters[2] = 0
                current_clause_id = str(clause_counters[0])
            elif level == 1:
                # Second level: X.1, X.2...
                if clause_counters[0] == 0:
                    continue
                clause_counters[1] += 1
                clause_counters[2] = 0
                current_clause_id = f"{clause_counters[0]}.{clause_counters[1]}"
            elif level == 2:
                # Third level: X.Y.1, X.Y.2...
                if clause_counters[1] == 0:
                    continue
                clause_counters[2] += 1
                current_clause_id = f"{clause_counters[0]}.{clause_counters[1]}.{clause_counters[2]}"

            clauses.append(ParsedClause(current_clause_id, text, "", seq))
            body_parts[current_clause_id] = []
            seq += 1

        elif current_clause_id:
            # Table content
            for row in block.rows:
                cells = [re.sub(r"\s+", " ", c.text).strip() for c in row.cells if c.text.strip()]
                if cells:
                    _append_body(body_parts, current_clause_id, " | ".join(cells))

    # Assign bodies
    result: list[ParsedClause] = []
    for clause in clauses:
        body = _clean_body("\n\n".join(body_parts.get(clause.clause_id, [])))
        result.append(ParsedClause(clause.clause_id, clause.title, body, clause.sort_order))

    if not result:
        raise ValueError("No clause headings found in DOCX")

    return result


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
        # Try clause-number-based parsing first
        try:
            clauses = parse_docx_faithful(content)
            # If we got very few clauses, likely means clause numbers aren't in text
            # Try structure-based parsing instead
            if len(clauses) < 15:
                try:
                    structure_clauses = parse_docx_by_structure(content)
                    # Use structure-based if it found significantly more clauses
                    if len(structure_clauses) > len(clauses) * 2:
                        return structure_clauses
                except Exception:
                    pass  # Fall back to faithful result
            return clauses
        except ValueError as e:
            # If faithful parsing failed completely, try structure-based
            if "No clause headings" in str(e):
                return parse_docx_by_structure(content)
            raise
    if lower.endswith((".pdf", ".doc")):
        text = extract_text(content, filename=filename)
        text = preprocess_extracted_text(text)
        return parse_iso_document_text(text, roll_up=False)
    raise ValueError("Use parse_upload for .json/.md/.txt")
