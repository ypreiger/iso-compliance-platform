"""Corpus admin — ISO upload, translate, delete, samples, templates."""
from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any
from uuid import uuid4

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.deps import CurrentUser, require_admin
from app.db import get_conn, rows_to_list
from app.iso.import_service import import_translated_clauses
from app.iso.parser import _sort_key
from app.iso.pipeline import store_file
from app.iso.standard_cleanup import delete_iso_standard
from app.iso.translate import translate_clause_rows

router = APIRouter(prefix="/admin/corpus", tags=["corpus"])
log = logging.getLogger(__name__)


def _parse_form_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


# ── request models ─────────────────────────────────────────────────────────

class CorpusCreate(BaseModel):
    doc_type: str
    name: str
    standards: list[str] = []
    language: str = "en"
    edition: str = ""


class TranslateRequest(BaseModel):
    standard: str
    edition: str = "2015"
    source_language: str = "en"
    target_language: str = "he"
    clause_ids: list[str] | None = None


class DeleteStandardRequest(BaseModel):
    standard: str
    languages: list[str] | None = None


# ── list / register ────────────────────────────────────────────────────────

@router.get("/{doc_type}")
def list_corpus(doc_type: str, admin: Annotated[CurrentUser, Depends(require_admin)]):
    if doc_type not in ("iso", "samples", "templates"):
        raise HTTPException(status_code=400, detail="Invalid doc_type")
    type_map = {"iso": "iso_standard", "samples": "sample_report", "templates": "template"}
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, standards, language, edition, status, metadata, created_at
            FROM corpus_documents WHERE doc_type = %s ORDER BY created_at DESC
            """,
            (type_map[doc_type],),
        ).fetchall()
        if doc_type == "iso":
            # Per-standard collections (iso-standards-ISO9001, …) plus legacy shared id.
            rag_count = conn.execute(
                """
                SELECT COUNT(*) AS c FROM rag_documents
                WHERE collection_id = 'iso-standards'
                   OR collection_id LIKE 'iso-standards-%%'
                """
            ).fetchone()
        else:
            rag_count = conn.execute(
                "SELECT COUNT(*) AS c FROM rag_documents WHERE collection_id = %s",
                (f"iso-{doc_type}",),
            ).fetchone()
        clause_counts = conn.execute(
            """
            SELECT standard, language, COUNT(*) AS c, MAX(edition) AS edition
            FROM iso_clause_text GROUP BY standard, language ORDER BY standard, language
            """
        ).fetchall()
    return {
        "documents": rows_to_list(rows),
        "indexed_chunks": int(rag_count["c"]) if rag_count else 0,
        "clause_counts": rows_to_list(clause_counts),
    }


@router.post("/{doc_type}")
def register_corpus(
    doc_type: str,
    body: CorpusCreate,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    type_map = {"iso": "iso_standard", "samples": "sample_report", "templates": "template"}
    if doc_type not in type_map:
        raise HTTPException(status_code=400, detail="Invalid doc_type")
    cid = str(uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO corpus_documents (id, doc_type, name, standards, language, edition, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'ready')
            """,
            (cid, type_map[doc_type], body.name, body.standards, body.language, body.edition),
        )
        conn.commit()
    return {"id": cid, "status": "ready"}


# ── PDF / DOC / DOCX upload (async pipeline) ───────────────────────────────

def _content_type_for(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".doc"):
        return "application/msword"
    return "application/octet-stream"


def _run_ingest_job(
    *,
    corpus_id: str,
    file_id: str,
    content: bytes,
    filename: str,
    standard: str,
    language: str,
    edition: str,
    admin_id: str,
    replace: bool,
) -> None:
    """Background worker: parse + index after the HTTP response has returned."""
    try:
        from app.db import audit
        from app.iso.pipeline import run_ingest_pipeline

        with get_conn() as conn:
            result = run_ingest_pipeline(
                conn,
                content=content,
                filename=filename,
                standard=standard,
                language=language,
                edition=edition,
                corpus_id=corpus_id,
                admin_id=admin_id,
                replace_previous=replace,
                skip_store=True,
                file_id=file_id,
            )
            conn.execute(
                """
                UPDATE corpus_documents
                SET status = 'ready',
                    metadata = metadata || %s::jsonb
                WHERE id = %s
                """,
                (json.dumps(result), corpus_id),
            )
            audit(
                conn,
                admin_id,
                "corpus.iso.uploaded",
                "corpus_document",
                corpus_id,
                after={
                    "standard": standard,
                    "language": language,
                    "edition": edition,
                    "clauses": result["clauses_imported"],
                    "parse_method": result["parse_method"],
                    "validation": result["validation"],
                },
            )
            conn.commit()
        log.info(
            "async ingest ready corpus_id=%s clauses=%s method=%s",
            corpus_id,
            result.get("clauses_imported"),
            result.get("parse_method"),
        )
    except Exception as exc:
        log.exception("async ingest failed corpus_id=%s", corpus_id)
        _mark_failed(corpus_id, str(exc))


@router.get("/iso/upload/{corpus_id}")
def get_iso_upload_status(
    corpus_id: str,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """Poll async ISO upload progress."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, standards, language, edition, status, metadata, created_at
            FROM corpus_documents
            WHERE id = %s AND doc_type = 'iso_standard'
            """,
            (corpus_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return {
        "corpus_id": row["id"],
        "status": row["status"],
        "standard": (row.get("standards") or [None])[0],
        "language": row.get("language"),
        "edition": row.get("edition"),
        "filename": row.get("name"),
        "created_at": row.get("created_at"),
        "clauses_imported": meta.get("clauses_imported") or meta.get("translated_clauses"),
        "translated_clauses": meta.get("translated_clauses"),
        "rag_chunks": meta.get("rag_chunks"),
        "parse_method": meta.get("parse_method"),
        "source_language": meta.get("source_language"),
        "target_language": meta.get("target_language"),
        "job_type": meta.get("job_type") or "upload",
        "warnings": meta.get("warnings") or meta.get("errors") or [],
        "validation": meta.get("validation"),
        "file_id": meta.get("file_id"),
        "error": meta.get("error"),
    }


@router.post("/iso/upload")
async def upload_iso_standard(
    admin: Annotated[CurrentUser, Depends(require_admin)],
    file: UploadFile = File(...),
    standard: str = Form(...),
    language: str = Form("en"),
    edition: str = Form("2015"),
    replace_previous: str = Form("true"),
):
    """Accept an ISO PDF/DOC/DOCX upload and process it asynchronously.

    Returns HTTP 202 quickly after persisting the file so browser/proxy
    timeouts and Argo rollouts cannot interrupt the long GPT-oss parse.
    Poll GET /admin/corpus/iso/upload/{corpus_id} until status is ready/failed.
    """
    if language not in ("en", "he", "both"):
        raise HTTPException(status_code=400, detail="language must be en, he, or both")
    replace = _parse_form_bool(replace_previous)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "upload.bin"
    lower = filename.lower()

    # JSON uploads go through the legacy bilingual path (no LLM needed)
    if lower.endswith(".json"):
        from app.iso.import_service import import_iso_upload

        try:
            with get_conn() as conn:
                result = import_iso_upload(
                    conn,
                    content=content,
                    filename=filename,
                    standard=standard,
                    language=language,
                    edition=edition,
                    admin_id=admin.id,
                    replace_previous=replace,
                )
                conn.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc
        return result

    # PDF / DOC / DOCX → async LLM pipeline
    if not any(lower.endswith(ext) for ext in (".pdf", ".doc", ".docx")):
        raise HTTPException(
            status_code=400,
            detail="Supported formats: .pdf, .doc, .docx, .json",
        )

    corpus_id = str(uuid4())
    std = standard.upper().replace(" ", "")

    def _prepare() -> str:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO corpus_documents
                  (id, doc_type, name, standards, language, edition, status, metadata)
                VALUES (%s, 'iso_standard', %s, %s, %s, %s, 'processing', %s::jsonb)
                """,
                (
                    corpus_id,
                    filename,
                    [std],
                    language,
                    edition,
                    json.dumps(
                        {
                            "source": "upload",
                            "filename": filename,
                            "size_bytes": len(content),
                        }
                    ),
                ),
            )
            file_id = store_file(
                conn,
                corpus_id=corpus_id,
                filename=filename,
                content=content,
                content_type=_content_type_for(filename),
            )
            conn.execute(
                """
                UPDATE corpus_documents
                SET metadata = metadata || %s::jsonb
                WHERE id = %s
                """,
                (json.dumps({"file_id": file_id}), corpus_id),
            )
            conn.commit()
            return file_id

    try:
        file_id = await asyncio.to_thread(_prepare)
    except Exception as exc:
        _mark_failed(corpus_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Upload store failed: {exc}") from exc

    asyncio.create_task(
        asyncio.to_thread(
            _run_ingest_job,
            corpus_id=corpus_id,
            file_id=file_id,
            content=content,
            filename=filename,
            standard=std,
            language=language,
            edition=edition,
            admin_id=admin.id,
            replace=replace,
        )
    )

    return JSONResponse(
        status_code=202,
        content={
            "corpus_id": corpus_id,
            "status": "processing",
            "standard": std,
            "language": language,
            "edition": edition,
            "file_id": file_id,
            "replace_previous": replace,
            "message": "File stored; clause extraction running in background.",
        },
    )


def _mark_failed(corpus_id: str, error: str) -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE corpus_documents SET status='failed', "
                "metadata = metadata || %s::jsonb WHERE id = %s",
                (json.dumps({"error": error}), corpus_id),
            )
            conn.commit()
    except Exception:
        pass


# ── translate ──────────────────────────────────────────────────────────────

async def _async_translate_job(
    *,
    corpus_id: str,
    standard: str,
    edition: str,
    source_language: str,
    target_language: str,
    clause_ids: list[str] | None,
    admin_id: str,
) -> None:
    """Background worker: translate source→target and replace target RAG."""
    try:
        with get_conn() as conn:
            sql = """
                SELECT clause_id, title, body, sort_order
                FROM iso_clause_text
                WHERE standard = %s AND language = %s
            """
            params: list = [standard, source_language]
            if clause_ids:
                placeholders = ", ".join(["%s"] * len(clause_ids))
                sql += f" AND clause_id IN ({placeholders})"
                params.extend(clause_ids)
            sql += " ORDER BY sort_order, clause_id"
            rows = rows_to_list(conn.execute(sql, params).fetchall())

        ordered_rows = sorted(
            rows,
            key=lambda r: (_sort_key(str(r["clause_id"])), str(r["clause_id"])),
        )
        if not ordered_rows:
            raise ValueError(f"No {source_language} clauses found for {standard}")

        with get_conn() as conn:
            conn.execute(
                """
                UPDATE corpus_documents
                SET metadata = metadata || %s::jsonb
                WHERE id = %s
                """,
                (
                    json.dumps(
                        {
                            "progress": f"0/{len(ordered_rows)}",
                            "total_source": len(ordered_rows),
                        }
                    ),
                    corpus_id,
                ),
            )
            conn.commit()

        translated, errors = await translate_clause_rows(
            ordered_rows,
            source_language=source_language,
            target_language=target_language,
            concurrency=4,
        )
        if not translated:
            raise ValueError(f"Translation failed: {'; '.join(errors[:3])}")

        from app.iso.parser import ParsedClause
        from app.iso.rag_index import file_sha256, index_clauses

        parsed = [
            ParsedClause(cid, title, body_text, sort_order)
            for cid, title, body_text, sort_order in translated
        ]
        replace_all = not bool(clause_ids)
        with get_conn() as conn:
            count = import_translated_clauses(
                conn,
                standard=standard,
                edition=edition,
                clauses=translated,
                target_language=target_language,
                admin_id=admin_id,
                corpus_id=corpus_id,
                replace_all=replace_all,
            )
            rag_chunks = index_clauses(
                conn,
                standard=standard,
                language=target_language,
                edition=edition,
                corpus_id=corpus_id,
                source_name=f"{standard}-{target_language}-translated",
                clauses=parsed,
                content_sha256=file_sha256(
                    f"translated:{standard}:{target_language}:{corpus_id}".encode()
                ),
                replace_all=replace_all,
                source="translated",
            )
            result = {
                "job_type": "translate",
                "standard": standard,
                "source_language": source_language,
                "target_language": target_language,
                "translated_clauses": count,
                "clauses_imported": count,
                "rag_chunks": rag_chunks,
                "errors": errors,
                "replace_rag": True,
            }
            conn.execute(
                """
                UPDATE corpus_documents
                SET status = 'ready',
                    language = %s,
                    metadata = metadata || %s::jsonb
                WHERE id = %s
                """,
                (target_language, json.dumps(result), corpus_id),
            )
            conn.commit()
        log.info(
            "async translate ready corpus_id=%s %s→%s clauses=%s rag=%s",
            corpus_id,
            source_language,
            target_language,
            count,
            rag_chunks,
        )
    except Exception as exc:
        log.exception("async translate failed corpus_id=%s", corpus_id)
        _mark_failed(corpus_id, str(exc))


@router.post("/iso/translate")
async def translate_iso_clauses(
    body: TranslateRequest,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """Translate clauses EN↔HE and replace target-language clauses + RAG.

    Returns HTTP 202 quickly; poll GET /admin/corpus/iso/upload/{corpus_id}.
    """
    if body.source_language not in ("en", "he") or body.target_language not in ("en", "he"):
        raise HTTPException(status_code=400, detail="source_language and target_language must be en or he")
    if body.source_language == body.target_language:
        raise HTTPException(status_code=400, detail="source and target language must differ")

    std = body.standard.upper().replace(" ", "")
    with get_conn() as conn:
        sql = """
            SELECT COUNT(*) AS c
            FROM iso_clause_text
            WHERE standard = %s AND language = %s
        """
        params: list = [std, body.source_language]
        if body.clause_ids:
            placeholders = ", ".join(["%s"] * len(body.clause_ids))
            sql += f" AND clause_id IN ({placeholders})"
            params.extend(body.clause_ids)
        count_row = conn.execute(sql, params).fetchone()
        source_count = int(count_row["c"] if isinstance(count_row, dict) else count_row[0])

    if source_count == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No {body.source_language} clauses found for standard",
        )

    corpus_id = str(uuid4())

    def _prepare() -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO corpus_documents
                  (id, doc_type, name, standards, language, edition, status, metadata)
                VALUES (%s, 'iso_standard', %s, %s, %s, %s, 'processing', %s::jsonb)
                """,
                (
                    corpus_id,
                    f"translate-{std}-{body.source_language}-{body.target_language}",
                    [std],
                    body.target_language,
                    body.edition,
                    json.dumps(
                        {
                            "job_type": "translate",
                            "source": "translate",
                            "source_language": body.source_language,
                            "target_language": body.target_language,
                            "total_source": source_count,
                            "replace_rag": True,
                        }
                    ),
                ),
            )
            conn.commit()

    await asyncio.to_thread(_prepare)
    asyncio.create_task(
        _async_translate_job(
            corpus_id=corpus_id,
            standard=std,
            edition=body.edition,
            source_language=body.source_language,
            target_language=body.target_language,
            clause_ids=body.clause_ids,
            admin_id=admin.id,
        )
    )
    return JSONResponse(
        status_code=202,
        content={
            "corpus_id": corpus_id,
            "status": "processing",
            "standard": std,
            "source_language": body.source_language,
            "target_language": body.target_language,
            "edition": body.edition,
            "total_source": source_count,
            "replace_rag": True,
            "message": (
                f"Translating {source_count} clauses "
                f"{body.source_language}→{body.target_language}; "
                "target language clauses and RAG will be replaced."
            ),
        },
    )


# ── delete standard ────────────────────────────────────────────────────────

@router.post("/iso/delete-standard")
def delete_standard_corpus(
    body: DeleteStandardRequest,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    with get_conn() as conn:
        result = delete_iso_standard(
            conn,
            standard=body.standard,
            languages=body.languages,
            admin_id=admin.id,
        )
        conn.commit()
    return result


# ── summary ────────────────────────────────────────────────────────────────

@router.get("/summary/all")
def corpus_summary(admin: Annotated[CurrentUser, Depends(require_admin)]):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT doc_type, COUNT(*) AS count FROM corpus_documents GROUP BY doc_type"
        ).fetchall()
        chunks = conn.execute("SELECT COUNT(*) AS c FROM rag_documents").fetchone()
    return {"by_type": rows_to_list(rows), "total_chunks": int(chunks["c"]) if chunks else 0}
