"""Sparse Print-to-PDF pages must be detected and OCR-recoverable."""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("ISO_PDF_OCR", "auto")

from app.iso.document_extract import page_text_looks_sparse, _extract_page_text_en


def test_sparse_mid_sentence_body_detected():
    sample = """
8.3.3 Actions in response to nonconforming product detected after delivery
shall be maintained (see 4.2.5).
4.2.5).
"""
    assert page_text_looks_sparse(sample)


def test_full_page_not_sparse():
    sample = "4.1 Understanding\n\n" + ("The organization shall determine issues. " * 80)
    assert not page_text_looks_sparse(sample)


def test_glued_ocr_heading_splits_body():
    from app.iso.clause_parse import try_clause_header, split_title_and_lead_body

    line = (
        "8.3.2 Actions in response to nonconforming product detected before delivery "
        "The organization shall deal with nonconforming product by one or more of the following ways:"
    )
    header = try_clause_header(line)
    assert header is not None
    assert header[0] == "8.3.2"
    title, lead = split_title_and_lead_body(header[1])
    assert title == "Actions in response to nonconforming product detected before delivery"
    assert lead.startswith("The organization shall deal")


def test_ocr_preferred_when_sparse_layer(monkeypatch):
    class FakePage:
        def get_text(self, *args, **kwargs):
            return (
                "8.3.3 Actions in response to nonconforming product detected after delivery\n"
                "shall be maintained (see 4.2.5).\n"
            )

        def get_textpage_ocr(self, **kwargs):
            raise RuntimeError("no tesseract")

        def get_pixmap(self, dpi=250):
            raise RuntimeError("no pixmap")

    full = (
        "8.3.3 Actions in response to nonconforming product detected after delivery\n"
        "When nonconforming product is detected after delivery or use has started, "
        "the organization shall take action appropriate to the effects of the nonconformity. "
        "Records of actions taken shall be maintained (see 4.2.5). "
        "The organization shall document procedures for issuing advisory notices."
    )
    monkeypatch.setenv("ISO_PDF_OCR", "auto")
    with patch("app.iso.document_extract.ocr_pdf_page", return_value=full):
        out = _extract_page_text_en(FakePage())
    assert "advisory notices" in out
    assert out.startswith("8.3.3")
