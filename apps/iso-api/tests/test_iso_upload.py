"""Tests for ISO parser and upload import."""
from __future__ import annotations

import json
import os

import pytest

os.environ["USE_SQLITE"] = "1"
os.environ["SQLITE_PATH"] = "/tmp/iso-parser-test.db"
os.environ["AUTH_DEV_MODE"] = "1"

from app.db import ensure_schema  # noqa: E402
from app.iso.parser import parse_upload  # noqa: E402
from app.iso.import_service import import_iso_upload  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _schema():
    if os.path.exists(os.environ["SQLITE_PATH"]):
        os.remove(os.environ["SQLITE_PATH"])
    ensure_schema()


def test_sort_key_fits_postgres_integer():
    from app.iso.parser import _sort_key

    assert _sort_key("4.1") == 401
    assert _sort_key("10.1") == 1001
    assert _sort_key("4.1.2") == 40102
    assert _sort_key("4.1") < 2_147_483_647


def test_parse_markdown_clauses():
    raw = b"""4.1 Understanding the organization

The organization shall determine external and internal issues.

4.2 Needs of interested parties

The organization shall determine interested parties.
"""
    std, clauses = parse_upload(raw, filename="iso.md", standard="ISO9001", language="en")
    assert std == "ISO9001"
    assert len(clauses) == 2
    assert clauses[0].clause_id == "4.1"


def test_import_replaces_language_rows():
    content = json.dumps(
        [
            {"clause_id": "4.1", "title": "A", "body": "Body A", "sort_order": 401},
            {"clause_id": "4.2", "title": "B", "body": "Body B", "sort_order": 402},
        ]
    ).encode()
    with get_conn() as conn:
        import_iso_upload(
            conn,
            content=content,
            filename="iso.json",
            standard="ISO9001",
            language="en",
            edition="2015",
            admin_id=None,
        )
        conn.commit()
    token = client.post("/auth/dev-login", json={"email": "yaakovpreiger@gmail.com"}).json()["access_token"]
    r = client.get(
        "/v1/iso/clauses?standard=ISO9001&language=en",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["clauses"]) == 2


def test_import_bilingual_json():
    content = json.dumps(
        {
            "standard": "ISO9001",
            "clauses": [
                {
                    "clause_id": "4.1",
                    "sort_order": 401,
                    "en": {"title": "Understanding", "body": "English body"},
                    "he": {"title": "הבנת הארגון", "body": "גוף בעברית"},
                },
            ],
        }
    ).encode()
    with get_conn() as conn:
        result = import_iso_upload(
            conn,
            content=content,
            filename="iso-bilingual.json",
            standard="ISO9001",
            language="both",
            edition="2015",
            admin_id=None,
        )
        conn.commit()
    assert result["language"] == "both"
    assert result["clauses_en"] == 1
    assert result["clauses_he"] == 1
    token = client.post("/auth/dev-login", json={"email": "yaakovpreiger@gmail.com"}).json()["access_token"]
    en = client.get(
        "/v1/iso/clauses?standard=ISO9001&language=en",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["clauses"]
    he = client.get(
        "/v1/iso/clauses?standard=ISO9001&language=he",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["clauses"]
    assert any(c["clause_id"] == "4.1" and "English body" in c["text"] for c in en)
    assert any(c["clause_id"] == "4.1" and "גוף בעברית" in c["text"] for c in he)


def test_parse_docx_clauses():
    from docx import Document

    buf = __import__("io").BytesIO()
    doc = Document()
    doc.add_paragraph("4.1 Understanding the organization")
    doc.add_paragraph("The organization shall determine external and internal issues.")
    doc.add_paragraph("4.2 Needs of interested parties")
    doc.add_paragraph("The organization shall determine interested parties.")
    doc.save(buf)
    std, clauses = parse_upload(buf.getvalue(), filename="iso.docx", standard="ISO9001", language="en")
    assert std == "ISO9001"
    assert len(clauses) == 2
    assert clauses[0].clause_id == "4.1"


def test_parse_pdf_clauses():
    from unittest.mock import patch

    sample = """4.1 Understanding the organization

The organization shall determine external and internal issues.

4.2 Needs of interested parties

The organization shall determine interested parties.
"""
    with patch("app.iso.document_extract.extract_text_from_pdf", return_value=sample):
        std, clauses = parse_upload(b"%PDF-1.4", filename="iso.pdf", standard="ISO9001", language="en")
    assert len(clauses) == 2
    assert clauses[0].clause_id == "4.1"


def test_dedupe_duplicate_clause_ids_in_upload():
    content = json.dumps(
        [
            {"clause_id": "1", "title": "First", "body": "A", "sort_order": 100},
            {"clause_id": "1", "title": "Second", "body": "B", "sort_order": 100},
            {"clause_id": "4.1", "title": "C", "body": "C body", "sort_order": 401},
        ]
    ).encode()
    with get_conn() as conn:
        result = import_iso_upload(
            conn,
            content=content,
            filename="iso.json",
            standard="ISO9001",
            language="en",
            edition="2015",
            admin_id=None,
            replace_previous=True,
        )
        conn.commit()
    assert result["clauses_imported"] == 2
    assert len(result["warnings"]) == 1
    token = client.post("/auth/dev-login", json={"email": "yaakovpreiger@gmail.com"}).json()["access_token"]
    clauses = client.get(
        "/v1/iso/clauses?standard=ISO9001&language=en",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["clauses"]
    c1 = next(c for c in clauses if c["clause_id"] == "1")
    assert "A" in c1["text"] and "B" in c1["text"]


def test_filters_pdf_noise():
    raw = (
        "000 Quality management systems\n\n"
        "Fundamentals junk\n\n"
        "4.1 Understanding the organization\n\n"
        "The organization shall determine issues.\n\n"
        "(c) ISO 2015 All rights reserved\n\n"
        "4.2 Needs of interested parties\n\n"
        "The organization shall determine interested parties.\n"
    ).encode()
    std, clauses = parse_upload(raw, filename="iso.txt", standard="ISO9001", language="en")
    assert std == "ISO9001"
    assert len(clauses) == 2
    assert clauses[0].clause_id == "4.1"


def test_hebrew_view_uses_hebrew_rows():
    content = json.dumps(
        [
            {"clause_id": "4.1", "title": "HE title", "body": "גוף בעברית", "sort_order": 401},
        ]
    ).encode()
    with get_conn() as conn:
        import_iso_upload(
            conn,
            content=content,
            filename="iso-he.json",
            standard="ISO9001",
            language="he",
            edition="2015",
            admin_id=None,
            replace_previous=True,
        )
        conn.commit()
    token = client.post("/auth/dev-login", json={"email": "yaakovpreiger@gmail.com"}).json()["access_token"]
    r = client.get(
        "/v1/iso/clauses?standard=ISO9001&language=he",
        headers={"Authorization": f"Bearer {token}"},
    )
    c41 = next(c for c in r.json()["clauses"] if c["clause_id"] == "4.1")
    assert "גוף בעברית" in c41["text"]
    assert c41.get("fallback") is not True


def test_hebrew_fallback_to_english():
    token = client.post("/auth/dev-login", json={"email": "yaakovpreiger@gmail.com"}).json()["access_token"]
    r = client.get(
        "/v1/iso/clauses?standard=ISO9001&language=he",
        headers={"Authorization": f"Bearer {token}"},
    )
    clauses = r.json()["clauses"]
    assert len(clauses) >= 1
    # Seeded data has Hebrew — ensure API returns Hebrew text for 4.1
    c41 = next(c for c in clauses if c["clause_id"] == "4.1")
    assert "ארגון" in c41["text"] or c41.get("fallback")
