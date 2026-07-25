"""Tests for hierarchical ISO clause parsing."""
from __future__ import annotations

from app.iso.clause_parse import parse_iso_document_text, repair_broken_words


def test_hebrew_tokenized_lines_are_rejoined_into_paragraphs():
    from app.iso.parser import normalize_hebrew_body

    raw = (
        "אימוץ\n\n"
        "מערכת\n\n"
        "ניהול\n\n"
        "איכות\n\n"
        "הוא\n\n"
        "החלטה\n\n"
        "אסטרטגית.\n\n"
        "הארגון\n\n"
        "יקבע\n\n"
        "את\n\n"
        "הקשרו."
    )
    joined = normalize_hebrew_body(raw)
    assert "\n\nאימוץ\n\n" not in f"\n\n{joined}\n\n"
    assert "אימוץ מערכת ניהול איכות הוא החלטה אסטרטגית." in joined.replace("\n", " ")
    assert "הארגון יקבע את הקשרו." in joined.replace("\n", " ")


def test_introduction_section_zero_is_kept():
    from app.iso.parser import preprocess_extracted_text
    from app.iso.clause_parse import parse_iso_document_text

    raw = preprocess_extracted_text(
        """
Introduction
0.1 General
The adoption of a quality management system is a strategic decision.
0.2 Quality management principles
This International Standard is based on the quality management principles.
1 Scope
This International Standard specifies requirements.
"""
    )
    clauses = parse_iso_document_text(raw)
    by_id = {c.clause_id: c for c in clauses}
    assert "0" in by_id or "0.1" in by_id
    assert "0.1" in by_id
    assert "strategic decision" in by_id["0.1"].body
    assert "1" in by_id


def test_copyright_footer_does_not_drop_clause_body():
    from app.iso.clause_parse import parse_iso_document_text

    raw = """
5.1.2 Customer focus
Top management shall demonstrate leadership and commitment with respect to customer focus by
ensuring that customer requirements are determined.
© ISO 2015 – All rights reserved
5.2 Policy
Top management shall establish a quality policy.
"""
    clauses = parse_iso_document_text(raw)
    by_id = {c.clause_id: c for c in clauses}
    assert "customer requirements are determined" in by_id["5.1.2"].body
    assert "© ISO" not in by_id["5.1.2"].body


def test_hebrew_pdf_dot_chrome_does_not_crash_reflow():
    from app.iso.clause_parse import parse_iso_document_text

    # Real HE PDF pattern: TOC dotted leaders + id/title split across lines.
    raw = """
5.1.2
................................
. התמקדות בלקוח
ההנהלה הבכירה תפגין מנהיגות.
5.2
.
מדיניות
מדיניות האיכות תיקבע.
"""
    clauses = parse_iso_document_text(raw)
    by_id = {c.clause_id: c for c in clauses}
    assert "5.1.2" in by_id
    assert "5.2" in by_id


def test_hebrew_rtl_leading_dot_clause_ids_are_normalized():
    from app.iso.parser import preprocess_extracted_text
    from app.iso.clause_parse import parse_iso_document_text

    # Real Hebrew DOCX extract order: short title, then dotted id, then body.
    raw = preprocess_extracted_text(
        """
5.1 מנהיגות ומחויבות
ההנהלה הבכירה תפגין מנהיגות.
כללי
.5.1.1
ההנהלה הבכירה תהיה אחראית.
התמקדות בלקוח
.5.1.2
דרישות הלקוח ייקבעו.
"""
    )
    clauses = parse_iso_document_text(raw)
    by_id = {c.clause_id: c for c in clauses}
    assert "5.1.1" in by_id
    assert "5.1.2" in by_id
    assert "כללי" in by_id["5.1.1"].title
    assert "אחראית" in by_id["5.1.1"].body
    assert "התמקדות" in by_id["5.1.2"].title


def test_promote_nested_clauses_splits_level3_from_parent_body():
    from app.iso.clause_parse import promote_nested_clauses
    from app.iso.parser import ParsedClause, _sort_key

    clauses = [
        ParsedClause(
            "5.1",
            "Leadership and commitment",
            "Top management shall demonstrate leadership.\n"
            "5.1.1 General\n"
            "Top management shall be accountable.\n"
            "5.1.2 Customer focus\n"
            "Customer requirements shall be determined.",
            _sort_key("5.1"),
        )
    ]
    out = promote_nested_clauses(clauses)
    by_id = {c.clause_id: c for c in out}
    assert "5.1.1" in by_id
    assert "5.1.2" in by_id
    assert "accountable" in by_id["5.1.1"].body
    assert "Customer requirements" in by_id["5.1.2"].body
    assert "5.1.1" not in by_id["5.1"].body


def test_stack_parser_assigns_body_to_correct_clause():
    raw = """
4 Context of the organization
4.1 Understanding the organization and its context
The organization shall determine external and internal issues relevant to its purpose.
The organization shall monitor information about these issues.
4.2 Understanding the needs and expectations of interested parties
The organization shall determine interested parties relevant to the QMS.
4.2.1 General
Interested parties can affect the organization.
"""
    clauses = parse_iso_document_text(raw)
    by_id = {c.clause_id: c for c in clauses}
    assert "4.1" in by_id
    assert "external and internal issues" in by_id["4.1"].body
    assert "interested parties relevant" in by_id["4.2"].body
    assert "Interested parties can affect" in by_id["4.2.1"].body


def test_roll_up_parent_section_body():
    raw = """
4.4 Quality management system and its processes
4.4.1 The organization shall establish processes needed for the QMS.
4.4.2 The organization shall maintain documented information.
"""
    clauses = parse_iso_document_text(raw, roll_up=True)
    parent = next(c for c in clauses if c.clause_id == "4.4")
    assert "establish processes" in parent.body
    assert "documented information" in parent.body


def test_reflows_broken_pdf_lines():
    raw = """
4.1 Understanding the org anization and its context
The org anization shall determine external and internal issues.
4.2 Needs of interested parties
The org anization shall determine interested parties.
"""
    clauses = parse_iso_document_text(raw)
    c41 = next(c for c in clauses if c.clause_id == "4.1")
    assert "shall determine external" in c41.body


def test_repair_broken_words_does_not_corrupt_hebrew():
    raw = "הארגון יבצע בקרה על מסמכים פנימיים"
    assert repair_broken_words(raw) == raw


def test_split_heading_lines_from_pdf_are_joined():
    raw = """
4
Context of the organization
4.1
Understanding the organization and its context
The organization shall determine internal and external issues.
"""
    clauses = parse_iso_document_text(raw)
    by_id = {c.clause_id: c for c in clauses}
    assert by_id["4"].title == "Context of the organization"
    assert "internal and external issues" in by_id["4.1"].body
