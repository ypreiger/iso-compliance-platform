"""ISO Compliance Platform API."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.deps import get_current_user
from app.db import ensure_schema, get_document_count
from app.routes import auth, corpus, coverage, documents, exports, findings, instructions, iso_text, mapping, projects, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    yield


app = FastAPI(title="ISO Compliance API Orchestrator", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(findings.router)
app.include_router(mapping.router)
app.include_router(coverage.router)
app.include_router(corpus.router)
app.include_router(documents.router)
app.include_router(instructions.router)
app.include_router(iso_text.router)
app.include_router(exports.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "iso-api-orchestrator", "version": "0.2.0"}


@app.get("/ready")
def ready():
    try:
        count = get_document_count()
        return {"status": "ready", "rag_documents": count}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(exc)},
        )


@app.get("/auth/me")
def auth_me(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "roles": user.roles,
        "can_access_projects": user.can_access_projects,
    }


@app.get("/v1/corpus/summary")
def public_corpus_summary(user=Depends(get_current_user)):
    return {
        "standards": ["ISO9001", "ISO14001", "ISO45001", "ISO13485"],
        "rag_documents": get_document_count(),
    }
