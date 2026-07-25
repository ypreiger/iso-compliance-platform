"""Translation must not silently drop clause body text."""
from __future__ import annotations

import pytest

from app.iso.translate import (
    _parse_json_object,
    _split_body_chunks,
    _translation_too_short,
)


def test_split_body_chunks_keeps_full_text():
    body = "Para one.\n\n" + ("Sentence. " * 200) + "\n\nPara end."
    chunks = _split_body_chunks(body, max_chars=400)
    assert len(chunks) > 1
    assert "".join(c.replace(" ", "") for c in chunks).count("Sentence") >= 200
    # All content preserved (allowing whitespace normalize)
    joined = "\n\n".join(chunks)
    assert "Para one." in joined
    assert "Para end." in joined


def test_refuse_truncated_json_salvage():
    # Closing brace present but string still open — old salvage path would invent body.
    with pytest.raises(ValueError, match="truncated|invalid"):
        _parse_json_object('{"title":"X","body":"incomplete}')


def test_translation_too_short_detects_drop():
    src = "The organization shall ensure that product which does not conform " * 5
    assert _translation_too_short(src, "יש לשמור.")
    assert not _translation_too_short("Short.", "קצר.")
