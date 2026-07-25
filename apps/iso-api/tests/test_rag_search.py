"""Tests for ISO RAG keyword search."""
from __future__ import annotations

import json
import os

import pytest

os.environ["USE_SQLITE"] = "1"
os.environ["SQLITE_PATH"] = "/tmp/iso-rag-search-test.db"
os.environ["AUTH_DEV_MODE"] = "1"

from app.db import ensure_schema, get_conn  # noqa: E402
from app.iso.rag_search import search_iso_rag  # noqa: E402


@pytest.fixture(autouse=True)
def _schema():
    if os.path.exists(os.environ["SQLITE_PATH"]):
        os.remove(os.environ["SQLITE_PATH"])
    ensure_schema()


def test_rag_search_finds_matching_clause():
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO rag_documents (collection_id, source_path, chunk_index, content, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                "iso-standards-ISO9001",
                "test#4.1",
                0,
                "4.1 Understanding the organization shall determine external and internal issues.",
                json.dumps(
                    {
                        "standard": "ISO9001",
                        "language": "en",
                        "clause_id": "4.1",
                        "title": "Understanding the organization",
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO rag_documents (collection_id, source_path, chunk_index, content, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                "iso-standards-ISO13485",
                "test#7.1",
                0,
                "7.1 Planning of product realization organization shall plan processes.",
                json.dumps(
                    {
                        "standard": "ISO13485",
                        "language": "en",
                        "clause_id": "7.1",
                        "title": "Planning of product realization",
                    }
                ),
            ),
        )
        conn.commit()
        hits = search_iso_rag(
            conn,
            standard="ISO9001",
            language="en",
            query="organization shall determine external issues",
            limit=1,
        )
        # Must not return ISO13485 chunks when searching ISO9001
        cross = search_iso_rag(
            conn,
            standard="ISO9001",
            language="en",
            query="product realization plan processes",
            limit=5,
        )
    assert hits
    assert hits[0]["clause_id"] == "4.1"
    assert all(h.get("clause_id") != "7.1" or "product realization" not in (h.get("content") or "").lower() for h in (cross or []))
    # Stronger: no 13485 hit when standard filter is ISO9001
    assert not any("product realization" in (h.get("content") or "").lower() for h in (cross or []))
