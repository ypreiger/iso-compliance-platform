"""Database schema and connection helpers."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Iterable
from uuid import uuid4

from app.config import get_settings

USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    roles TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    standards TEXT NOT NULL DEFAULT '[]',
    edition TEXT NOT NULL DEFAULT '2015',
    status TEXT NOT NULL DEFAULT 'draft',
    supervisor_id TEXT,
    owner_id TEXT,
    context TEXT NOT NULL DEFAULT '{}',
    mapping_approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    finding_text TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    sort_order INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS finding_clause_mappings (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL,
    standard TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    clause_title TEXT NOT NULL DEFAULT '',
    relevance_pct INTEGER NOT NULL DEFAULT 0,
    severity TEXT NOT NULL DEFAULT 'minor',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (finding_id, standard, clause_id)
);
CREATE TABLE IF NOT EXISTS clause_coverage (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    standard TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_checked',
    reason TEXT NOT NULL DEFAULT '',
    UNIQUE (project_id, standard, clause_id)
);
CREATE TABLE IF NOT EXISTS corpus_documents (
    id TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,
    name TEXT NOT NULL,
    standards TEXT NOT NULL DEFAULT '[]',
    language TEXT NOT NULL DEFAULT 'en',
    edition TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ready',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS prompt_templates (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'en',
    version INTEGER NOT NULL DEFAULT 1,
    body TEXT NOT NULL,
    is_published INTEGER NOT NULL DEFAULT 0,
    published_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (stage, locale, version)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rag_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (collection_id, source_path, chunk_index)
);
CREATE TABLE IF NOT EXISTS iso_clause_text (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL,
    body TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    edition TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'seed',
    UNIQUE (standard, clause_id, language)
);
CREATE TABLE IF NOT EXISTS corpus_files (
    id TEXT PRIMARY KEY,
    corpus_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    file_data BLOB NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    roles TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    standards TEXT[] NOT NULL DEFAULT '{}',
    edition TEXT NOT NULL DEFAULT '2015',
    status TEXT NOT NULL DEFAULT 'draft',
    supervisor_id UUID REFERENCES users(id),
    owner_id UUID REFERENCES users(id),
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    mapping_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS findings (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    finding_text TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    sort_order INT NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS finding_clause_mappings (
    id UUID PRIMARY KEY,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    standard TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    clause_title TEXT NOT NULL DEFAULT '',
    relevance_pct INT NOT NULL DEFAULT 0,
    severity TEXT NOT NULL DEFAULT 'minor',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (finding_id, standard, clause_id)
);
CREATE TABLE IF NOT EXISTS clause_coverage (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    standard TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_checked',
    reason TEXT NOT NULL DEFAULT '',
    UNIQUE (project_id, standard, clause_id)
);
CREATE TABLE IF NOT EXISTS corpus_documents (
    id UUID PRIMARY KEY,
    doc_type TEXT NOT NULL,
    name TEXT NOT NULL,
    standards TEXT[] NOT NULL DEFAULT '{}',
    language TEXT NOT NULL DEFAULT 'en',
    edition TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ready',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY,
    stage TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'en',
    version INT NOT NULL DEFAULT 1,
    body TEXT NOT NULL,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    published_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (stage, locale, version)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_json JSONB,
    after_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS rag_documents (
    id SERIAL PRIMARY KEY,
    collection_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (collection_id, source_path, chunk_index)
);
CREATE TABLE IF NOT EXISTS iso_clause_text (
    id SERIAL PRIMARY KEY,
    standard TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL,
    body TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    edition TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'seed',
    UNIQUE (standard, clause_id, language)
);
CREATE INDEX IF NOT EXISTS idx_findings_project ON findings(project_id);
CREATE TABLE IF NOT EXISTS corpus_files (
    id UUID PRIMARY KEY,
    corpus_id UUID NOT NULL REFERENCES corpus_documents(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes INT NOT NULL DEFAULT 0,
    file_data BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_corpus_files_corpus ON corpus_files(corpus_id);
"""


class SqliteConn:
    """Minimal wrapper so routes can use similar execute/fetchone/commit."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple | list = ()):
        pg_sql = sql
        pg_sql = pg_sql.replace("%s", "?").replace("::jsonb", "").replace("::json", "")
        pg_sql = pg_sql.replace("NOW()", "CURRENT_TIMESTAMP")
        pg_sql = pg_sql.replace(" ILIKE ", " LIKE ")
        pg_sql = pg_sql.replace(" excluded.", " excluded.")  # keep
        pg_sql = re.sub(r"metadata->>'(\w+)'", r"json_extract(metadata, '$.\1')", pg_sql)
        pg_sql = pg_sql.replace("ON CONFLICT DO NOTHING", "ON CONFLICT DO NOTHING")
        pg_sql = pg_sql.replace("TRUE", "1").replace("FALSE", "0")
        # SQLite doesn't support jsonb merge operator; replace with simple assignment
        pg_sql = re.sub(r"metadata\s*\|\|\s*\?", "?", pg_sql)
        new_params = []
        for p in params:
            if isinstance(p, (list, dict)):
                new_params.append(json.dumps(p))
            elif isinstance(p, (bytes, bytearray, memoryview)):
                new_params.append(bytes(p))  # SQLite stores as BLOB
            else:
                new_params.append(p)
        cur = self._conn.execute(pg_sql, tuple(new_params))
        return _SqliteResult(cur)

    def commit(self) -> None:
        self._conn.commit()


class _SqliteResult:
    def __init__(self, cur: sqlite3.Cursor) -> None:
        self._rows = [dict(r) for r in cur.fetchall()]

    def _normalize(self, d: dict) -> dict:
        for key in ("roles", "standards"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    d[key] = [x.strip() for x in d[key].split(",") if x.strip()]
        for key in ("context", "metadata", "before_json", "after_json"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key] or "{}")
                except json.JSONDecodeError:
                    pass
        for key in ("mapping_approved", "is_active", "is_published"):
            if key in d:
                d[key] = bool(d[key])
        return d

    def fetchone(self):
        if not self._rows:
            return None
        return self._normalize(self._rows.pop(0))

    def fetchall(self):
        out = []
        while self._rows:
            row = self.fetchone()
            if row:
                out.append(row)
        return out


@contextmanager
def get_conn() -> Generator[Any, None, None]:
    if USE_SQLITE:
        path = os.getenv("SQLITE_PATH", "/tmp/iso-platform.db")
        raw = sqlite3.connect(path)
        try:
            yield SqliteConn(raw)
        finally:
            raw.close()
    else:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(get_settings().dsn, row_factory=dict_row) as conn:
            yield conn


def ensure_schema() -> None:
    settings = get_settings()
    if USE_SQLITE:
        path = os.getenv("SQLITE_PATH", "/tmp/iso-platform.db")
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA_SQLITE)
        _migrate_iso_clause_columns(SqliteConn(conn))
        conn.commit()
        _seed_all(SqliteConn(conn))
        conn.close()
        return
    import psycopg
    with psycopg.connect(settings.dsn, autocommit=True) as conn:
        # Avoid indefinite hang when an upload holds table locks (CREATE TABLE
        # IF NOT EXISTS takes ShareLock, which conflicts with RowExclusiveLock).
        conn.execute("SET lock_timeout = '10s'")
        try:
            conn.execute(SCHEMA_PG)
            _migrate_iso_clause_columns_pg(conn)
            _seed_postgres(conn)
        except Exception as exc:
            # Schema already exists in production; fail-open so /health can bind.
            import logging
            logging.getLogger(__name__).warning(
                "ensure_schema skipped/partial due to lock or error: %s", exc
            )


def _migrate_iso_clause_columns(conn: Any) -> None:
    for col, typedef in (("edition", "TEXT NOT NULL DEFAULT ''"), ("source", "TEXT NOT NULL DEFAULT 'seed'")):
        try:
            conn.execute(f"ALTER TABLE iso_clause_text ADD COLUMN {col} {typedef}")
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            pass


def _migrate_iso_clause_columns_pg(conn: Any) -> None:
    conn.execute("ALTER TABLE iso_clause_text ADD COLUMN IF NOT EXISTS edition TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE iso_clause_text ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'seed'")


def _seed_all(conn: Any) -> None:
    settings = get_settings()
    for email in settings.admin_emails:
        row = conn.execute("SELECT id FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (id, email, name, roles, is_active) VALUES (%s, %s, %s, %s, 1)",
                (str(uuid4()), email, email.split("@")[0], json.dumps(["admin"])),
            )
    _seed_prompts(conn)
    _seed_iso_clauses(conn)
    if hasattr(conn, "commit"):
        conn.commit()


def _seed_postgres(conn: Any) -> None:
    settings = get_settings()
    for email in settings.admin_emails:
        row = conn.execute("SELECT id FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (id, email, name, roles, is_active) VALUES (%s, %s, %s, %s, TRUE) ON CONFLICT DO NOTHING",
                (str(uuid4()), email, email.split("@")[0], ["admin"]),
            )
    _seed_prompts(conn)
    _seed_iso_clauses(conn)


def _seed_prompts(conn: Any) -> None:
    stages = [
        ("context_summarize", "Summarize organization context: {{org_profile}}"),
        ("finding_normalize", "Normalize finding text: {{finding}}"),
        ("iso_map_and_score", "Map finding to ISO clauses for {{standard}}: {{finding}}"),
        ("clause_coverage", "Assess clause coverage for {{standard}}"),
        ("corrective_action_draft", "Draft corrective action for {{finding}} clause {{clause_ref}}"),
        ("ofi_instruction_draft", "Draft OFI instruction for minor finding {{finding}}"),
        ("report_narrative", "Generate regulatory narrative in {{locale}}"),
    ]
    pub = "1" if USE_SQLITE else "TRUE"
    for stage, body in stages:
        exists = conn.execute("SELECT 1 FROM prompt_templates WHERE stage = %s LIMIT 1", (stage,)).fetchone()
        if not exists:
            conn.execute(
                f"INSERT INTO prompt_templates (id, stage, locale, version, body, is_published) VALUES (%s, %s, 'en', 1, %s, {pub})",
                (str(uuid4()), stage, body),
            )


def _seed_iso_clauses(conn: Any) -> None:
    from pathlib import Path
    from app.iso.parser import _sort_key

    seed_path = Path(__file__).parent / "data" / "iso_clauses_seed.json"
    items = json.loads(seed_path.read_text(encoding="utf-8"))
    for item in items:
        standard = item["standard"]
        clause_id = item["clause_id"]
        sort_order = int(item.get("sort_order", _sort_key(clause_id)))
        for lang in ("en", "he"):
            loc = item[lang]
            conn.execute(
                """
                INSERT INTO iso_clause_text (standard, clause_id, title, language, body, sort_order, edition, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'seed')
                ON CONFLICT (standard, clause_id, language) DO UPDATE SET
                  title = EXCLUDED.title,
                  body = EXCLUDED.body,
                  sort_order = EXCLUDED.sort_order,
                  edition = EXCLUDED.edition
                """,
                (standard, clause_id, loc["title"], lang, loc["body"], sort_order, ""),
            )


def get_document_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM rag_documents").fetchone()
        if USE_SQLITE:
            return int(row["c"]) if row else 0
        return int(row["c"]) if row else 0


def audit(conn: Any, user_id: str | None, action: str, entity_type: str, entity_id: str,
          before: Any = None, after: Any = None) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, before_json, after_json)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_id, action, entity_type, entity_id,
         json.dumps(before) if before is not None else None,
         json.dumps(after) if after is not None else None),
    )


def rows_to_list(rows: Iterable[dict]) -> list[dict]:
    return [dict(r) for r in rows]
