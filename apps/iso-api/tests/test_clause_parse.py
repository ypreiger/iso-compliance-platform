"""Tests for hierarchical ISO clause parsing."""
from __future__ import annotations

from app.iso.clause_parse import parse_iso_document_text


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
