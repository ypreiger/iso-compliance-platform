from __future__ import annotations

from app.iso.document_extract import _fix_hebrew_spacing, _reconstruct_hebrew_line


def test_hebrew_spacing_fix_does_not_merge_valid_short_words():
    raw = "על כל מסמך פנימי הארגון יבצע בקרה"
    assert _fix_hebrew_spacing(raw) == raw


def test_hebrew_spacing_fix_repairs_split_letters_and_prefixes():
    raw = "ה א ר ג ו ן חייב ל פקח על תהליך"
    assert _fix_hebrew_spacing(raw) == "הארגון חייב לפקח על תהליך"


def test_reconstruct_hebrew_line_keeps_clause_number_first():
    # x coordinates are left-to-right physical order from PDF extraction.
    line = _reconstruct_hebrew_line(
        [
            (10.0, "4.1"),
            (30.0, "ארגון"),
            (60.0, "ה"),
            (90.0, "הבנת"),
        ]
    )
    assert line == "4.1 הבנת הארגון"
