"""Translate EN↔HE and replace target RAG."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

from app.db import ensure_schema, get_conn
from app.iso.import_service import clear_standard_language, import_translated_clauses
from app.iso.parser import ParsedClause
from app.iso.rag_index import index_clauses
from app.iso.translate import translate_clause_rows


def test_translate_clause_rows_he_to_en():
    rows = [
        {"clause_id": "4.1", "title": "הבנת הארגון", "body": "הארגון יקבע נושאים.", "sort_order": 1},
        {"clause_id": "4.2", "title": "מחזיקי עניין", "body": "הארגון יקבע צרכים.", "sort_order": 2},
    ]

    async def fake_translate(title, body, *, source_language, target_language):
        assert source_language == "he"
        assert target_language == "en"
        return f"EN:{title}", f"EN:{body}"

    async def run():
        with patch("app.iso.translate.translate_clause_text", new=AsyncMock(side_effect=fake_translate)):
            return await translate_clause_rows(
                rows, source_language="he", target_language="en", concurrency=2
            )

    translated, errors = asyncio.run(run())
    assert not errors
    assert [t[0] for t in translated] == ["4.1", "4.2"]
    assert translated[0][1].startswith("EN:")
    assert translated[0][2].startswith("EN:")


def test_translate_clause_rows_en_to_he():
    rows = [
        {"clause_id": "1", "title": "Scope", "body": "This standard specifies requirements.", "sort_order": 1},
    ]

    async def fake_translate(title, body, *, source_language, target_language):
        assert source_language == "en"
        assert target_language == "he"
        return "היקף", "תקן זה מפרט דרישות."

    async def run():
        with patch("app.iso.translate.translate_clause_text", new=AsyncMock(side_effect=fake_translate)):
            return await translate_clause_rows(
                rows, source_language="en", target_language="he", concurrency=1
            )

    translated, errors = asyncio.run(run())
    assert not errors
    assert translated[0][1] == "היקף"
    assert "דרישות" in translated[0][2]


def _row_get(row, key, idx):
    if isinstance(row, dict):
        return row[key]
    return row[idx]


def test_import_translated_replaces_target_clauses_and_rag():
    """Target language wipe + reindex path used by both directions."""
    os.environ["USE_SQLITE"] = "1"
    os.environ["SQLITE_PATH"] = "/tmp/iso-translate-test.db"
    try:
        from app.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass

    ensure_schema()
    with get_conn() as conn:
        clear_standard_language(conn, std="ISO14001", language="en")
        clear_standard_language(conn, std="ISO14001", language="he")
        conn.execute(
            """
            INSERT INTO iso_clause_text
              (standard, clause_id, title, language, body, sort_order, edition, source)
            VALUES
              ('ISO14001', '4.1', 'הבנת הארגון', 'he', 'גוף', 1, '2015', 'upload'),
              ('ISO14001', '4.1', 'Old EN', 'en', 'old', 1, '2015', 'upload')
            """
        )
        index_clauses(
            conn,
            standard="ISO14001",
            language="en",
            edition="2015",
            corpus_id="old",
            source_name="old-en",
            clauses=[ParsedClause("4.1", "Old EN", "old", 1)],
            content_sha256="old",
        )
        conn.commit()

        count = import_translated_clauses(
            conn,
            standard="ISO14001",
            edition="2015",
            clauses=[("4.1", "Understanding the organization", "The organization shall…", 401000000)],
            target_language="en",
            admin_id=None,
            corpus_id="translate-job",
        )
        chunks = index_clauses(
            conn,
            standard="ISO14001",
            language="en",
            edition="2015",
            corpus_id="translate-job",
            source_name="ISO14001-en-translated",
            clauses=[
                ParsedClause(
                    "4.1",
                    "Understanding the organization",
                    "The organization shall…",
                    401000000,
                )
            ],
            content_sha256="new",
            source="translated",
        )
        conn.commit()

        en_rows = conn.execute(
            "SELECT title, source, corpus_id FROM iso_clause_text WHERE standard='ISO14001' AND language='en'"
        ).fetchall()
        he_rows = conn.execute(
            "SELECT clause_id FROM iso_clause_text WHERE standard='ISO14001' AND language='he'"
        ).fetchall()
        rag = conn.execute(
            """
            SELECT content, metadata
            FROM rag_documents
            WHERE metadata LIKE '%ISO14001%' AND metadata LIKE '%"language": "en"%'
               OR (json_extract(metadata, '$.standard') = 'ISO14001'
                   AND json_extract(metadata, '$.language') = 'en')
            """
        ).fetchall()

    assert count == 1
    assert chunks >= 1
    assert len(en_rows) == 1
    assert _row_get(en_rows[0], "title", 0) == "Understanding the organization"
    assert len(he_rows) == 1  # source language preserved
    assert rag
