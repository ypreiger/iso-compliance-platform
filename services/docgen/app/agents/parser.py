"""Document text extraction from PDF, DOC, DOCX, and Excel.

VENDORED MODULE: This code is duplicated in apps/iso-api/app/iso/document_extract.py
for service isolation. Bug fixes must be applied to BOTH locations.

This layer is purely mechanical — it extracts raw text without interpretation.
The LLM extractor (extractor.py) handles semantic structuring.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ── PDF ────────────────────────────────────────────────────────────────────

def extract_pdf(data: bytes) -> str:
    """Extract text from PDF in reading order using PyMuPDF (fitz).

    For Hebrew PDFs, uses word-based extraction for better quality.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")

        # Check if Hebrew content (sample first 2 pages)
        is_hebrew = False
        for page_num in range(min(2, len(doc))):
            sample = doc[page_num].get_text("text")[:400]
            if sum(1 for c in sample if '֐' <= c <= '׿') > 15:
                is_hebrew = True
                break

        pages: list[str] = []

        if is_hebrew:
            # Use words mode for better Hebrew extraction
            for page in doc:
                words_list = page.get_text("words", sort=True)
                if not words_list:
                    continue
                # Group by line (y-coordinate)
                lines_dict: dict[int, list[str]] = {}
                for word_tuple in words_list:
                    word = word_tuple[4]
                    y = int(word_tuple[1])
                    line_key = (y // 5) * 5
                    lines_dict.setdefault(line_key, []).append(word)
                # Reconstruct lines
                line_texts = [' '.join(lines_dict[y]) for y in sorted(lines_dict.keys())]
                pages.append('\n'.join(line_texts))
        else:
            # Standard text extraction
            for page in doc:
                text = page.get_text("text", sort=True)
                if text.strip():
                    pages.append(text)
                    continue
                blocks = page.get_text("blocks", sort=True)
                for b in blocks:
                    if b[6] == 0:
                        pages.append(b[4])

        doc.close()
        text = "\n".join(pages)
    except ImportError:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)

    if not text.strip():
        raise ValueError("PDF contains no extractable text (scanned PDF not supported)")
    return _normalize(text)


# ── DOCX ───────────────────────────────────────────────────────────────────

def extract_docx(data: bytes) -> str:
    """Extract text from DOCX; prefix headings with ## for downstream detection."""
    from docx import Document
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(BytesIO(data))
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            para = Paragraph(child, doc)
            text = re.sub(r"\s+", " ", para.text).strip()
            if not text:
                continue
            style = (para.style.name or "").lower()
            lines.append(f"## {text}" if "heading" in style else text)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            for row in table.rows:
                cells = [re.sub(r"\s+", " ", c.text).strip() for c in row.cells if c.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
    return _normalize("\n".join(lines))


# ── DOC (legacy) ───────────────────────────────────────────────────────────

def extract_doc(data: bytes) -> str:
    """Extract text from legacy .doc via antiword binary."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "upload.doc"
        p.write_bytes(data)
        env = {"ANTIWORDHOME": "/usr/share/antiword", **os.environ}
        try:
            res = subprocess.run(
                ["antiword", "-m", "UTF-8.txt", "-w", "0", str(p)],
                check=True, capture_output=True, timeout=120, env=env,
            )
        except FileNotFoundError as e:
            raise ValueError("antiword not installed in container") from e
        except subprocess.CalledProcessError:
            # Retry without explicit mapping when map files are missing.
            try:
                res = subprocess.run(
                    ["antiword", "-w", "0", str(p)],
                    check=True, capture_output=True, timeout=120, env=env,
                )
            except subprocess.CalledProcessError as e:
                raise ValueError(f".doc extraction failed: {(e.stderr or b'').decode()[:300]}") from e
        text = res.stdout.decode("utf-8", errors="replace")
        if not text.strip():
            raise ValueError(".doc file has no extractable text")
        return _normalize(text)


# ── Excel ──────────────────────────────────────────────────────────────────

def extract_excel(data: bytes) -> dict:
    """Parse Excel file; return sheet data as list of dicts (headers as keys)."""
    import openpyxl
    wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    sheets: list[dict] = []
    for ws in wb.worksheets:
        rows_raw = list(ws.iter_rows(values_only=True))
        if not rows_raw:
            continue
        headers = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(rows_raw[0])]
        rows: list[dict] = []
        for row in rows_raw[1:]:
            if all(v is None for v in row):
                continue
            rows.append({headers[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(row)})
        sheets.append({"name": ws.title, "headers": headers, "rows": rows})
    wb.close()
    return {"sheets": sheets}


# ── unified ────────────────────────────────────────────────────────────────

def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from any supported document type."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_pdf(data)
    if lower.endswith(".docx"):
        return extract_docx(data)
    if lower.endswith(".doc"):
        return extract_doc(data)
    raise ValueError(f"Unsupported file type for text extraction: {filename}. Use .pdf, .doc, or .docx")
