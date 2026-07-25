"""Application model-call metrics + embedding helper."""
from __future__ import annotations

import os

os.environ["USE_SQLITE"] = "1"
os.environ["SQLITE_PATH"] = "/tmp/iso-model-metrics-test.db"
os.environ["AUTH_DEV_MODE"] = "1"
os.environ["RAG_EMBED_ON_INDEX"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.observability.model_metrics import record_model_call  # noqa: E402


def test_metrics_endpoint_exposes_model_series():
    record_model_call(
        task="embed_index",
        model="bge-m3",
        status="ok",
        latency_s=0.12,
        prompt_tokens=8,
        total_tokens=8,
    )
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "iso_app_model_requests_total" in body
    assert 'model="bge-m3"' in body
    assert 'task="embed_index"' in body


def test_embeddings_disabled_under_sqlite():
    from app.iso.embeddings import embeddings_enabled

    assert embeddings_enabled() is False
