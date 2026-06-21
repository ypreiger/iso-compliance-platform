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


def _fix_hebrew_spacing(text: str) -> str:
    """Fix spacing artifacts in Hebrew text from PDF extraction.

    PyMuPDF sometimes inserts spurious SINGLE spaces within Hebrew words,
    particularly after certain letters. We remove single spaces between Hebrew
    letters ONLY when the pattern looks like a broken word.

    Heuristic: Remove single space between Hebrew letters when:
    - Both surrounding "words" are very short (1-2 chars)
    - The second part starts with a vowel-taking letter
    """
    if not text:
        return text

    # Check if text contains Hebrew
    if not any('֐' <= c <= '׿' for c in text):
        return text

    lines = text.split('\n')
    fixed_lines: list[str] = []

    for line in lines:
        # Don't process if line has no Hebrew
        if not any('֐' <= c <= '׿' for c in line):
            fixed_lines.append(line)
            continue

        # Strategy: Look for patterns like "ה ת" or "י ו" where single space splits a word
        # Hebrew letter followed by exactly ONE space followed by Hebrew letter
        # But only if it creates very short fragments

        words = line.split()
        rebuilt = []
        i = 0
        while i < len(words):
            word = words[i]

            # Check if current word is 1-2 Hebrew chars and next word starts with Hebrew
            if (i + 1 < len(words) and
                len(word) <= 2 and
                all('֐' <= c <= '׿' for c in word if c.isalpha()) and
                words[i+1] and ('֐' <= words[i+1][0] <= '׿')):
                # Likely broken word - join them
                rebuilt.append(word + words[i+1])
                i += 2
            else:
                rebuilt.append(word)
                i += 1

        fixed_lines.append(' '.join(rebuilt))

    return '\n'.join(fixed_lines)


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
        hebrew_count = sum(1 for c in sample_text if '֐' <= c <= '׿')
        if hebrew_count > 20:
            is_hebrew = True
            break

    pages: list[str] = []

    if is_hebrew:
        # For Hebrew PDFs, use 'words' extraction for better boundaries
        for page in doc:
            words_list = page.get_text("words", sort=True)  # Returns list of (x0, y0, x1, y1, word, block, line, word_num)
            if not words_list:
                continue

            # Group words by line (same y0 coordinate, with tolerance)
            lines_dict: dict[int, list[str]] = {}
            for word_tuple in words_list:
                word_text = word_tuple[4]
                y0 = int(word_tuple[1])  # y-coordinate
                # Round to nearest 5 pixels to group lines
                line_key = (y0 // 5) * 5
                if line_key not in lines_dict:
                    lines_dict[line_key] = []
                lines_dict[line_key].append(word_text)

            # Reconstruct lines in order
            line_texts = []
            for y in sorted(lines_dict.keys()):
                line_texts.append(' '.join(lines_dict[y]))

            pages.append('\n'.join(line_texts))
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

    # Apply Hebrew text fixes if needed (still helpful for word order)
    if is_hebrew:
        text = _fix_hebrew_spacing(text)
        text = _fix_hebrew_word_order(text)

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
