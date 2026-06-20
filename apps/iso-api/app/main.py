"""ISO Compliance Platform API."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db import ensure_schema, get_document_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    yield


app = FastAPI(title="ISO Compliance API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "iso-api"}


@app.get("/ready")
def ready():
    try:
        count = get_document_count()
        return {"status": "ready", "rag_documents": count}
    except Exception as exc:  # noqa: BLE001 — surface DB errors to probes
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(exc)},
        )


@app.get("/v1/corpus/summary")
def corpus_summary():
    return {
        "standards": ["ISO9001", "ISO14001", "ISO45001", "ISO13485"],
        "rag_documents": get_document_count(),
        "llm_gateway": os.getenv("LLM_GATEWAY_URL", ""),
    }
