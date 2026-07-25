"""Golden fidelity checks: ISO 13485 RAG titles/bodies must match the PDF."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Keep text-layer fidelity tests fast/deterministic (OCR covered separately).
os.environ["ISO_PDF_OCR"] = "0"

from app.iso.clause_parse import parse_document_bytes
from app.iso.parser import dedupe_clauses, preprocess_extracted_text, strip_correspondence_annexes

PDF = Path(__file__).resolve().parents[3] / "RAG" / "RAG-Standards" / "ISO 13485 - 2016 EN.pdf"

# Verbatim titles from ISO 13485:2016 main body (not Annex B / ISO 9001 mapping).
EXPECTED = {
    "4": "Quality management system",
    "4.1": "General requirements",
    "5": "Management responsibility",
    "5.1": "Management commitment",
    "6": "Resource management",
    "6.1": "Provision of resources",
    "6.2": "Human resources",
    "7": "Product realization",
    "7.1": "Planning of product realization",
    "7.2": "Customer-related processes",
    "7.2.1": "Determination of requirements related to product",
    "7.3": "Design and development",
    "7.3.2": "Design and development planning",
    "8": "Measurement, analysis and improvement",
}


@pytest.mark.skipif(not PDF.is_file() or PDF.stat().st_size < 1000, reason="ISO13485 PDF missing")
def test_iso13485_clause7_matches_original_not_iso9001_mapping():
    content = PDF.read_bytes()
    parsed = parse_document_bytes(content, filename=PDF.name)
    parsed, _ = dedupe_clauses(parsed)
    by_id = {c.clause_id: c for c in parsed}

    assert "7" in by_id, "clause 7 missing"
    assert by_id["7"].title == "Product realization"
    assert "Support" not in by_id["7"].title
    assert "Resource management" not in by_id["7"].title

    assert "7.1" in by_id
    assert by_id["7.1"].title == "Planning of product realization"
    assert "Resources" not in by_id["7.1"].title
    # Body must be taken from the document, not invented.
    assert "plan and develop the processes needed for product realization" in by_id["7.1"].body

    # No ISO 9001 mapping titles anywhere in EN 13485 parse.
    contaminated = [
        f"{c.clause_id}:{c.title}"
        for c in parsed
        if any(
            bad in c.title
            for bad in (
                "Support",
                "Competence",
                "Organizational knowledge",
                "Leadership and commitment",
                "Context of the organization",
            )
        )
        and c.clause_id.split(".")[0] in {"6", "7", "8"}
    ]
    assert not contaminated, contaminated


@pytest.mark.skipif(not PDF.is_file() or PDF.stat().st_size < 1000, reason="ISO13485 PDF missing")
def test_iso13485_core_titles_match_original():
    content = PDF.read_bytes()
    parsed = parse_document_bytes(content, filename=PDF.name)
    parsed, _ = dedupe_clauses(parsed)
    by_id = {c.clause_id: c for c in parsed}

    failures = []
    for cid, title in EXPECTED.items():
        got = by_id.get(cid)
        if not got:
            failures.append(f"{cid}: MISSING")
            continue
        if got.title.strip() != title:
            failures.append(f"{cid}: got {got.title!r} want {title!r}")
        # No ISO 9001:2015 mapping leftovers in titles
        for bad in ("Support", "Leadership and commitment", "Context of the organization", "Performance evaluation"):
            if bad in got.title and bad not in title:
                failures.append(f"{cid}: contaminated with {bad!r} → {got.title!r}")
    assert not failures, "\n".join(failures)


def test_strip_correspondence_annex_removes_table_b2():
    raw = """
7 Product realization
7.1 Planning of product realization
The organization shall plan and develop the processes needed for product realization.

Annex B
(informative)

Correspondence between ISO 13485:2016 and ISO 9001:2015
Table B.2 — Correspondence between ISO 9001:2015 and ISO 13485:2016
7 Support
6 Resource management
7.1 Resources
6 Resource management
"""
    cleaned = strip_correspondence_annexes(raw)
    assert "Product realization" in cleaned
    assert "7 Support" not in cleaned
    assert "Correspondence between ISO" not in cleaned
    # preprocess must also strip
    pre = preprocess_extracted_text(raw)
    assert "7 Support" not in pre


def test_repair_titles_never_merges_iso9001_into_iso13485():
    """Known-title repair must not copy ISO 9001 HLS onto ISO 13485 clauses."""
    from app.iso.parser import ParsedClause
    from app.iso.pipeline import _repair_known_titles
    from app.iso.rag_index import collection_id_for_standard

    contaminated = [
        ParsedClause("7", "Support", "body", 700000000),
        ParsedClause("7.1", "Resources", "body", 701000000),
        ParsedClause("8", "Operation", "body", 800000000),
    ]
    fixed = _repair_known_titles(contaminated, language="en", standard="ISO13485")
    by_id = {c.clause_id: c.title for c in fixed}
    assert by_id["7"] == "Clause 7"
    assert by_id["7.1"] == "Clause 7.1"
    assert by_id["8"] == "Clause 8"
    assert "Support" not in by_id.values()
    assert "Operation" not in by_id.values()

    # ISO9001 may still use its own dictionary for bad titles.
    bad_9001 = [ParsedClause("7", "ציור garbage long title that is broken", "x", 7)]
    fixed_9001 = _repair_known_titles(bad_9001, language="en", standard="ISO9001")
    assert fixed_9001[0].title == "Support"

    assert collection_id_for_standard("ISO13485") == "iso-standards-ISO13485"
    assert collection_id_for_standard("ISO9001") != collection_id_for_standard("ISO13485")
