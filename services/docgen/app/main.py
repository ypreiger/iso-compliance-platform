"""ISO Doc-Agent — document parsing and generation microservice.

Architecture:
  POST /parse         — PDF/DOC/DOCX/Excel → structured JSON (LLM-powered)
  POST /generate      — structured data → Excel/DOCX/PDF
  GET  /models        — configured model endpoints per task
  GET  /health        — liveness probe
  GET  /ready         — readiness probe
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.parse import router as parse_router
from app.routes.generate import router as generate_router


_AGENT_MODE = os.getenv("DOC_AGENT_MODE", "all").strip().lower()
if _AGENT_MODE not in {"all", "parse-rag", "generate"}:
    _AGENT_MODE = "all"

app = FastAPI(
    title="ISO Doc-Agent",
    version="1.0.0",
    description=(
        "Document parsing (PDF, DOC, DOCX, Excel) and generation (Excel, DOCX, PDF) "
        "with LLM-powered ISO clause extraction. "
        "Each task uses an independently configurable model endpoint."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _AGENT_MODE in {"all", "parse-rag"}:
    app.include_router(parse_router)
if _AGENT_MODE in {"all", "generate"}:
    app.include_router(generate_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "doc-agent",
        "version": "1.0.0",
        "mode": _AGENT_MODE,
    }


@app.get("/ready")
def ready():
    # Verify key dependencies are importable
    missing: list[str] = []
    for lib in ("fitz", "docx", "openpyxl", "xlsxwriter", "reportlab"):
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)
    if missing:
        return {"status": "degraded", "missing_libs": missing}
    return {"status": "ready"}


@app.get("/models")
def models():
    """Return the model endpoints currently configured for each task."""
    from app.config import get_model_config
    cfg = get_model_config()
    # Redact key values for security
    return {
        task: {
            "url": vals["url"],
            "model": vals["model"],
            "key_set": bool(vals["key"]),
        }
        for task, vals in cfg.items()
    }
