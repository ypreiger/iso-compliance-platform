"""Load RAG/manifest.yaml and walk seed folders."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Collection:
    id: str
    path: Path
    kind: str
    optional: bool
    ingest: dict[str, Any]
    languages: list[str]
    standards: list[str]


def load_manifest(rag_root: Path) -> list[Collection]:
    manifest_path = rag_root / "manifest.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    out: list[Collection] = []
    for item in data.get("collections", []):
        rel = item["path"]
        out.append(
            Collection(
                id=item["id"],
                path=rag_root / rel,
                kind=item.get("kind", "unknown"),
                optional=bool(item.get("optional", False)),
                ingest=item.get("ingest", {}),
                languages=list(item.get("languages", ["en"])),
                standards=list(item.get("standards", [])),
            )
        )
    return out


def iter_seed_files(collection: Collection) -> list[Path]:
    if not collection.path.is_dir():
        if collection.optional:
            return []
        raise FileNotFoundError(f"required collection path missing: {collection.path}")
    files = [
        p
        for p in sorted(collection.path.rglob("*"))
        if p.is_file() and p.name not in {".gitkeep", ".DS_Store"}
    ]
    if not files and not collection.optional:
        raise ValueError(f"no files in required collection: {collection.path}")
    return files
