"""Hebrew ISO title garbage must fail structure gate and be repaired."""
from __future__ import annotations

from app.iso.parser import ParsedClause
from app.iso.pipeline import (
    _bad_title,
    _repair_known_titles,
    _structure_quality_ok,
    _title_compatible,
)


def test_amendment_sheet_is_bad_title():
    assert _bad_title("גיליון התיקון מס '", "1")
    assert _bad_title("ההקשרשל", "4")
    assert _bad_title("Corrigendum 1", "1")
    assert not _bad_title("היקף", "1")
    assert not _bad_title("הבנת הארגון והקשרו", "4.1")


def test_truncated_he_title_not_compatible_with_canonical():
    assert not _title_compatible("גישה", "גישה תהליכית")
    assert _title_compatible("גישה תהליכית", "גישה תהליכית")
    assert _title_compatible(
        "הבנת הארגון והקשר שלו",
        "הבנת הארגון והקשרו",
    )


def test_repair_replaces_amendment_and_swapped_hls_titles():
    raw = [
        ParsedClause("1", "גיליון התיקון מס '", "body", 100000000),
        ParsedClause("4", "ההקשרשל", "body", 400000000),
        ParsedClause("6", "אזכורים נורמטיביים", "body", 600000000),
        ParsedClause("7", "הצרכים והציפיותשל מחזיקי עניין", "body", 700000000),
        ParsedClause("8", "ומחויבות", "body", 800000000),
        ParsedClause("9", "מדיניות האיכות", "body", 900000000),
        ParsedClause("10", "איכותוה תכנון להשגתן", "body", 1000000000),
    ]
    fixed = _repair_known_titles(raw, language="he", standard="ISO9001")
    by_id = {c.clause_id: c.title for c in fixed}
    assert by_id["1"] == "היקף"
    assert by_id["4"] == "הקשר הארגון"
    assert by_id["6"] == "תכנון"
    assert by_id["7"] == "תמיכה"
    assert by_id["8"] == "תפעול"
    assert by_id["9"] == "הערכת ביצועים"
    assert by_id["10"] == "שיפור"


def test_he_pdf_style_parse_fails_structure_gate():
    """Amendment-contaminated HE PDF must not skip LLM."""
    clauses = [
        ParsedClause("0", "מבוא", "", 0),
        ParsedClause("0.1", "כללי", "x" * 200, 1000000),
        ParsedClause("1", "גיליון התיקון מס '", "x" * 500, 100000000),
        ParsedClause("4", "ההקשרשל", "x" * 200, 400000000),
        ParsedClause("4.1", "הבנת הארגון והקשר שלו", "x" * 200, 401000000),
        ParsedClause("6", "אזכורים נורמטיביים", "x" * 50, 600000000),
        ParsedClause("7", "תמיכה", "x" * 100, 700000000),
        ParsedClause("8", "תפעול", "x" * 100, 800000000),
        ParsedClause("9", "הערכת ביצועים", "x" * 100, 900000000),
        ParsedClause("10", "שיפור", "x" * 100, 1000000000),
    ]
    # Pad to look "complete" numerically but still fail anchors.
    for i in range(40):
        cid = f"5.1.{i+1}" if i < 20 else f"8.5.{i-19}"
        clauses.append(ParsedClause(cid, "כללי", "body text here " * 20, 500000000 + i))
    assert not _structure_quality_ok(clauses, language="he")
