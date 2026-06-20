"""Database helpers."""
from __future__ import annotations

import os

import psycopg


def _dsn() -> str:
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")
    user = os.getenv("DATABASE_USER", "iso")
    password = os.getenv("DATABASE_PASSWORD", "iso")
    name = os.getenv("DATABASE_NAME", "iso")
    return f"host={host} port={port} dbname={name} user={user} password={password}"


def ensure_schema() -> None:
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        conn.execute(
            """
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
            """
        )


def get_document_count() -> int:
    with psycopg.connect(_dsn()) as conn:
        row = conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()
        return int(row[0]) if row else 0
