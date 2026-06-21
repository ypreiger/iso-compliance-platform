"""Extract clean reading-order text from PDF, DOC, and DOCX.

PDF  → PyMuPDF (fitz) — better reading order than pypdf
DOCX → python-docx — heading styles + paragraph walk
DOC  → antiword (compiled into image) → plain text
"""
from __future__ import annotations

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


# ── PDF ────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from a PDF using PyMuPDF in reading order.

    PyMuPDF uses heuristics to order text blocks correctly across columns
    and header/footer zones, which is essential for multi-column ISO PDFs.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Fallback to pypdf if PyMuPDF is not installed
        return _extract_pdf_pypdf(content)

    doc = fitz.open(stream=content, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        # sort=True uses reading-order sort (left-right, top-bottom)
        blocks = page.get_text("blocks", sort=True)
        for block in blocks:
            if block[6] == 0:  # type 0 = text block
                pages.append(block[4])
    doc.close()

    text = "\n".join(pages)
    if not text.strip():
        raise ValueError("PDF contains no extractable text (scanned images are not supported)")
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
        try:
            result = subprocess.run(
                ["antiword", str(doc_path)],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "Legacy .doc files require antiword in the API container."
            ) from exc
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
