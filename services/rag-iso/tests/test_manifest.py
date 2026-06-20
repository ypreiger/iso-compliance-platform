from pathlib import Path

import pytest

from rag_iso.manifest import load_manifest


def test_manifest_collections():
    root = Path(__file__).resolve().parents[3] / "RAG"
    cols = load_manifest(root)
    ids = {c.id for c in cols}
    assert "iso-standards" in ids
    assert "iso-samples" in ids
    assert any(c.path.name == "RAG-Standards" for c in cols)
