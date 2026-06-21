"""Ingest seed files into PostgreSQL (text stub chunks; embeddings later)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg

from rag_iso.manifest import Collection, iter_seed_files, load_manifest


def _ensure_iso_parser_path() -> None:
    candidates = [
        Path("/opt/app-root/src"),
        Path(__file__).resolve().parents[2] / "apps" / "iso-api",
    ]
    for path in candidates:
        if (path / "app").exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
            return


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".yaml", ".yml"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".pdf", ".doc", ".docx"}:
        _ensure_iso_parser_path()
        try:
            from app.iso.clause_parse import parse_document_bytes

            clauses = parse_document_bytes(path.read_bytes(), filename=path.name)
            parts: list[str] = []
            for clause in clauses:
                parts.append(f"{clause.clause_id} {clause.title}")
                if clause.body.strip():
                    parts.append(clause.body)
            return "\n\n".join(parts)
        except Exception as exc:
            return f"[parse-error:{suffix}] {path.name}: {exc}"
    stat = path.stat()
    return f"[binary:{suffix or 'unknown'}] {path.name} size={stat.st_size}"


def _dsn() -> str:
    host = os.getenv("DATABASE_HOST", "iso-postgres")
    port = os.getenv("DATABASE_PORT", "5432")
    user = os.getenv("DATABASE_USER", "iso")
    password = os.getenv("DATABASE_PASSWORD", "")
    name = os.getenv("DATABASE_NAME", "iso")
    return f"host={host} port={port} dbname={name} user={user} password={password}"


def _infer_language(path: Path, collection: Collection) -> str:
    name = path.name.lower()
    if "-he" in name or "_he." in name or name.endswith(".he.md"):
        return "he"
    if "-en" in name or "_en." in name:
        return "en"
    langs = collection.languages or ["en"]
    return langs[0]


def _infer_standard(path: Path, collection: Collection) -> str:
    name = path.stem.upper()
    for std in collection.standards or []:
        if std.upper() in name:
            return std.upper()
    return ""


def _infer_edition(path: Path) -> str:
    import re

    match = re.search(r"(20\d{2})", path.name)
    return match.group(1) if match else ""


def _chunk(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += max(1, size - overlap)
    return chunks


def ensure_schema(conn: psycopg.Connection) -> None:
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


def ingest_collection(conn: psycopg.Connection, collection: Collection) -> int:
    inserted = 0
    chunk_size = int(collection.ingest.get("chunk_size", 1000))
    overlap = int(collection.ingest.get("chunk_overlap", 100))
    for file_path in iter_seed_files(collection):
        rel = str(file_path.relative_to(collection.path.parent))
        text = _read_text(file_path)
        for idx, piece in enumerate(_chunk(text, chunk_size, overlap)):
            meta = {
                "kind": collection.kind,
                "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
                "language": _infer_language(file_path, collection),
                "standard": _infer_standard(file_path, collection),
                "edition": _infer_edition(file_path),
            }
            conn.execute(
                """
                INSERT INTO rag_documents (collection_id, source_path, chunk_index, content, metadata)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (collection_id, source_path, chunk_index) DO UPDATE
                SET content = EXCLUDED.content, metadata = EXCLUDED.metadata
                """,
                (collection.id, rel, idx, piece, json.dumps(meta)),
            )
            inserted += 1
    return inserted


def main() -> None:
    rag_root = Path(os.getenv("RAG_ROOT", "/seed/RAG"))
    store = Path(os.getenv("RAG_STORE", "/data/rag"))
    store.mkdir(parents=True, exist_ok=True)

    collections = load_manifest(rag_root)
    total = 0
    with psycopg.connect(_dsn(), autocommit=True) as conn:
        ensure_schema(conn)
        for coll in collections:
            n = ingest_collection(conn, coll)
            print(f"ingested {n} chunks from {coll.id}")
            total += n
    (store / "ingest.complete").write_text(f"chunks={total}\n", encoding="utf-8")
    print(f"done total_chunks={total}")


if __name__ == "__main__":
    main()
