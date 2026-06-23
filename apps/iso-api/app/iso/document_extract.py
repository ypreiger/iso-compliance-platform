"""Extract clean reading-order text from PDF, DOC, and DOCX.

VENDORED MODULE: This code is duplicated in services/docgen/app/agents/parser.py
for service isolation. Bug fixes must be applied to BOTH locations.

PDF  → PyMuPDF (fitz) — better reading order than pypdf
DOCX → python-docx — heading styles + paragraph walk
DOC  → antiword (compiled into image) → plain text
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

HEBREW_CHAR_RE = re.compile(r"[\u0590-\u05FF]")
CLAUSE_ID_TOKEN_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,4}[\.\)]?$")
HEBREW_PREFIX_LETTERS = {"ו", "ב", "כ", "ל", "מ", "ש", "ה"}


# ── normalisation ──────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Remove form-feeds, collapse whitespace, strip blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    lines: list[str] = []
    for line in text.split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _contains_hebrew(text: str) -> bool:
    return bool(HEBREW_CHAR_RE.search(text))


def _hebrew_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    hebrew = sum(1 for c in letters if HEBREW_CHAR_RE.match(c))
    return hebrew / len(letters)


def _is_single_hebrew_letter(token: str) -> bool:
    return len(token) == 1 and bool(HEBREW_CHAR_RE.match(token))


def _starts_with_hebrew(token: str) -> bool:
    for char in token:
        if char.isalpha():
            return bool(HEBREW_CHAR_RE.match(char))
    return False


def _fix_hebrew_spacing(text: str) -> str:
    """Conservative fix for Hebrew token fragmentation.

    Earlier logic merged many legitimate short Hebrew words (for example
    "על כל" -> "עלכל"). We now only join high-confidence breakage cases:
    - runs of isolated single-letter Hebrew tokens ("ה א ר ג ו ן")
    - Hebrew prefix letters split from their following word ("ב קרה" -> "בקרה")
    """
    if not text:
        return text

    if not _contains_hebrew(text):
        return text

    lines = text.split("\n")
    fixed_lines: list[str] = []

    for line in lines:
        if not _contains_hebrew(line):
            fixed_lines.append(line)
            continue

        words = line.split()
        rebuilt = []
        i = 0
        while i < len(words):
            word = words[i]
            # Case 1: "ה א ר ג ו ן" style char-by-char extraction.
            if _is_single_hebrew_letter(word):
                run = [word]
                j = i + 1
                while j < len(words) and _is_single_hebrew_letter(words[j]):
                    run.append(words[j])
                    j += 1
                if len(run) >= 2:
                    rebuilt.append("".join(run))
                    i = j
                    continue

                # Case 2: detached Hebrew prefix letter ("ב קרה" -> "בקרה").
                if (
                    j < len(words)
                    and word in HEBREW_PREFIX_LETTERS
                    and _starts_with_hebrew(words[j])
                ):
                    rebuilt.append(word + words[j])
                    i = j + 1
                    continue

            rebuilt.append(word)
            i += 1

        fixed_lines.append(" ".join(rebuilt))

    return "\n".join(fixed_lines)


def _is_clause_id_token(token: str) -> bool:
    return bool(CLAUSE_ID_TOKEN_RE.match(token))


def _reconstruct_hebrew_line(entries: list[tuple[float, str]]) -> str:
    """Reconstruct a line from PDF words while preserving RTL readability."""
    if not entries:
        return ""

    # Left-to-right physical order from page coordinates.
    tokens = [word for _, word in sorted(entries, key=lambda item: item[0])]
    sample = " ".join(tokens)
    if _hebrew_ratio(sample) < 0.4:
        return " ".join(tokens)

    # Keep leading clause numbers in place, reverse the Hebrew body.
    prefix_len = 0
    for tok in tokens:
        if _is_clause_id_token(tok):
            prefix_len += 1
            continue
        break

    ordered = tokens[:prefix_len] + list(reversed(tokens[prefix_len:]))
    return _fix_hebrew_spacing(" ".join(ordered))


def _extract_hebrew_page_text(page) -> str:
    """Extract one Hebrew-heavy PDF page by preserving blocks and line order."""
    words_list = page.get_text("words", sort=False)
    if not words_list:
        return page.get_text("text", sort=True)

    words_by_block: dict[int, dict[int, list[tuple[float, float, str]]]] = {}
    for item in words_list:
        if len(item) < 8:
            continue
        x0, y0, _x1, _y1, word, block_no, line_no, _word_no = item[:8]
        word_text = str(word).strip()
        if not word_text:
            continue
        words_by_block.setdefault(int(block_no), {}).setdefault(int(line_no), []).append(
            (float(x0), float(y0), word_text)
        )

    rendered_blocks: list[str] = []
    seen_blocks: set[int] = set()

    for block in page.get_text("blocks", sort=True):
        if len(block) < 7 or int(block[6]) != 0:  # text blocks only
            continue
        block_no = int(block[5])
        seen_blocks.add(block_no)
        line_map = words_by_block.get(block_no)
        if not line_map:
            fallback = str(block[4]).strip()
            if fallback:
                rendered_blocks.append(fallback)
            continue

        rendered_lines: list[tuple[float, int, str]] = []
        for line_no, words in line_map.items():
            line = _reconstruct_hebrew_line([(x, text) for x, _y, text in words]).strip()
            if line:
                y0 = min(y for _x, y, _text in words)
                rendered_lines.append((y0, line_no, line))
        rendered_lines.sort(key=lambda item: (item[0], item[1]))
        if rendered_lines:
            rendered_blocks.append("\n".join(line for _y, _ln, line in rendered_lines))

    # Keep any lines from unseen blocks (defensive fallback).
    for block_no, line_map in words_by_block.items():
        if block_no in seen_blocks:
            continue
        rendered_lines: list[tuple[float, int, str]] = []
        for line_no, words in line_map.items():
            line = _reconstruct_hebrew_line([(x, text) for x, _y, text in words]).strip()
            if line:
                y0 = min(y for _x, y, _text in words)
                rendered_lines.append((y0, line_no, line))
        rendered_lines.sort(key=lambda item: (item[0], item[1]))
        if rendered_lines:
            rendered_blocks.append("\n".join(line for _y, _ln, line in rendered_lines))

    return "\n\n".join(rendered_blocks)


def _fix_hebrew_word_order(text: str) -> str:
    """Fix reversed Hebrew words that occur in some PDF extractions.

    Some PDF extractors reverse the order of Hebrew words in RTL text.
    This function detects Hebrew-heavy lines and reverses word order if needed.
    """
    if not text:
        return text

    # Check if text contains significant Hebrew content
    hebrew_chars = sum(1 for c in text if '֐' <= c <= '׿')
    if hebrew_chars < 10:  # Not enough Hebrew to warrant processing
        return text

    lines = text.split("\n")
    fixed_lines: list[str] = []

    for line in lines:
        line_hebrew = sum(1 for c in line if '֐' <= c <= '׿')
        line_total = len([c for c in line if c.isalpha()])

        # If line is >60% Hebrew, it might be reversed
        if line_total > 0 and line_hebrew / line_total > 0.6:
            words = line.split()
            # Check if it looks reversed: numbers at end, Hebrew at start
            if words and words[0] and any('֐' <= c <= '׿' for c in words[0]):
                # Don't reverse if line starts with a clause number pattern
                if not re.match(r'^\d+(\.\d+)*\s', line):
                    # Heuristic: if first word is Hebrew and last might be English/number
                    if words and (words[-1].isdigit() or words[-1][0].isascii()):
                        # Likely reversed, fix it
                        fixed_lines.append(" ".join(reversed(words)))
                        continue

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


# ── PDF ────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from a PDF using PyMuPDF in reading order.

    PyMuPDF uses heuristics to order text blocks correctly across columns
    and header/footer zones, which is essential for multi-column ISO PDFs.

    For Hebrew text, uses 'words' mode to get better word boundaries.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Fallback to pypdf if PyMuPDF is not installed
        return _extract_pdf_pypdf(content)

    doc = fitz.open(stream=content, filetype="pdf")

    # Check if document contains significant Hebrew content (sample first 3 pages)
    is_hebrew = False
    for page_num in range(min(3, len(doc))):
        sample_text = doc[page_num].get_text("text")[:500]
        hebrew_count = sum(1 for c in sample_text if HEBREW_CHAR_RE.match(c))
        if hebrew_count > 20:
            is_hebrew = True
            break

    pages: list[str] = []

    if is_hebrew:
        # For Hebrew PDFs, preserve block/line structure and reconstruct RTL lines.
        for page in doc:
            text = _extract_hebrew_page_text(page)
            if text.strip():
                pages.append(text)
    else:
        # For non-Hebrew PDFs, use standard text extraction
        for page in doc:
            text = page.get_text("text", sort=True)
            if text.strip():
                pages.append(text)
                continue
            blocks = page.get_text("blocks", sort=True)
            for block in blocks:
                if block[6] == 0:  # type 0 = text block
                    pages.append(block[4])

    doc.close()

    text = "\n".join(pages)
    if not text.strip():
        raise ValueError("PDF contains no extractable text (scanned images are not supported)")

    # Apply spacing fix only; line order is handled during extraction.
    if is_hebrew:
        text = _fix_hebrew_spacing(text)

    return normalize_text(text)


def _extract_pdf_pypdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        if t.strip():
            parts.append(t)
    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("PDF contains no extractable text (scanned images are not supported)")
    return normalize_text(text)


# ── DOCX ───────────────────────────────────────────────────────────────────

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX preserving heading hierarchy markers.

    Heading paragraphs get a prefix like '## ' so the LLM and regex parser
    can easily identify clause-level boundaries.
    """
    from docx import Document

    doc = Document(BytesIO(content))
    lines: list[str] = []

    for para in doc.paragraphs:
        text = re.sub(r"\s+", " ", para.text).strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if "heading" in style:
            lines.append(f"## {text}")
        else:
            lines.append(text)

    # Also pull table cells in document order
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    lines_full: list[str] = []
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            para = Paragraph(child, doc)
            text = re.sub(r"\s+", " ", para.text).strip()
            if not text:
                continue
            style = (para.style.name or "").lower()
            lines_full.append(f"## {text}" if "heading" in style else text)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            for row in table.rows:
                cells = [re.sub(r"\s+", " ", c.text).strip() for c in row.cells]
                line = " | ".join(c for c in cells if c)
                if line:
                    lines_full.append(line)

    result = "\n".join(lines_full) if lines_full else "\n".join(lines)
    return normalize_text(result)


# ── DOC (legacy) ───────────────────────────────────────────────────────────

def extract_text_from_doc(content: bytes) -> str:
    """Extract text from legacy .doc via antiword binary."""
    with tempfile.TemporaryDirectory() as tmp:
        doc_path = Path(tmp) / "upload.doc"
        doc_path.write_bytes(content)
        env = {"ANTIWORDHOME": "/usr/share/antiword", **os.environ}
        try:
            result = subprocess.run(
                ["antiword", "-m", "UTF-8.txt", "-w", "0", str(doc_path)],
                check=True,
                capture_output=True,
                timeout=120,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "Legacy .doc files require antiword in the API container."
            ) from exc
        except subprocess.CalledProcessError:
            # Fallback to antiword defaults if mapping resources are unavailable.
            try:
                result = subprocess.run(
                    ["antiword", "-w", "0", str(doc_path)],
                    check=True,
                    capture_output=True,
                    timeout=120,
                    env=env,
                )
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or b"").decode(errors="replace")
                raise ValueError(f".doc text extraction failed: {stderr[:400]}") from exc
        text = result.stdout.decode("utf-8", errors="replace")
        if not text.strip():
            raise ValueError(".doc file contains no extractable text")
        return normalize_text(text)


# ── unified entry point ────────────────────────────────────────────────────

def extract_text(content: bytes, *, filename: str) -> str:
    """Extract plain text from PDF, DOC, or DOCX for LLM parsing."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if lower.endswith(".docx"):
        return extract_text_from_docx(content)
    if lower.endswith(".doc"):
        return extract_text_from_doc(content)
    raise ValueError(f"Unsupported file type: {filename}. Use .pdf, .doc, or .docx")


# ── legacy helpers still used by clause_parse.py ──────────────────────────

def iter_docx_blocks(document) -> list:
    """Yield paragraphs and tables in document order (used by clause_parse)."""
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    parent = document.element.body
    blocks = []
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            blocks.append(Paragraph(child, document))
        elif isinstance(child, CT_Tbl):
            blocks.append(Table(child, document))
    return blocks
