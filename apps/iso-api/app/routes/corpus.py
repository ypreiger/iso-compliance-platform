"""Corpus admin — ISO upload, translate, delete, samples, templates."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth.deps import CurrentUser, require_admin
from app.db import get_conn, rows_to_list
from app.iso.import_service import import_translated_clauses
from app.iso.parser import _sort_key
from app.iso.standard_cleanup import delete_iso_standard
from app.iso.translate import translate_clause_text

router = APIRouter(prefix="/admin/corpus", tags=["corpus"])


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
        rag_count = conn.execute(
            "SELECT COUNT(*) AS c FROM rag_documents WHERE collection_id = %s",
            ("iso-standards" if doc_type == "iso" else f"iso-{doc_type}",),
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


# ── PDF / DOC / DOCX upload (full pipeline) ────────────────────────────────

@router.post("/iso/upload")
async def upload_iso_standard(
    admin: Annotated[CurrentUser, Depends(require_admin)],
    file: UploadFile = File(...),
    standard: str = Form(...),
    language: str = Form("en"),
    edition: str = Form("2015"),
    replace_previous: str = Form("true"),
):
    """Upload a PDF, DOC, or DOCX ISO standard file.

    Pipeline:
      1. Store original file (corpus_files)
      2. Extract text with PyMuPDF / antiword / python-docx
      3. Parse clauses via LLM agent (GPT-4o) with regex fallback
      4. Index into iso_clause_text + rag_documents
      5. Validate retrieval; return report
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

    # PDF / DOC / DOCX → LLM pipeline
    if not any(lower.endswith(ext) for ext in (".pdf", ".doc", ".docx")):
        raise HTTPException(
            status_code=400,
            detail="Supported formats: .pdf, .doc, .docx, .json",
        )

    corpus_id = str(uuid4())
    try:
        with get_conn() as conn:
            # Create corpus_documents record first so corpus_files FK works
            conn.execute(
                """
                INSERT INTO corpus_documents
                  (id, doc_type, name, standards, language, edition, status, metadata)
                VALUES (%s, 'iso_standard', %s, %s, %s, %s, 'processing', %s::jsonb)
                """,
                (
                    corpus_id,
                    filename,
                    [standard.upper().replace(" ", "")],
                    language,
                    edition,
                    json.dumps({"source": "upload", "filename": filename}),
                ),
            )
            conn.commit()

            from app.iso.pipeline import run_ingest_pipeline

            result = run_ingest_pipeline(
                conn,
                content=content,
                filename=filename,
                standard=standard,
                language=language,
                edition=edition,
                corpus_id=corpus_id,
                admin_id=admin.id,
                replace_previous=replace,
            )

            # Update record with full metadata
            conn.execute(
                """
                UPDATE corpus_documents
                SET status = 'ready',
                    metadata = metadata || %s::jsonb
                WHERE id = %s
                """,
                (json.dumps(result), corpus_id),
            )

            from app.db import audit
            audit(
                conn,
                admin.id,
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

    except ValueError as exc:
        _mark_failed(corpus_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _mark_failed(corpus_id, str(exc))
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    return {
        "corpus_id": corpus_id,
        "standard": standard.upper().replace(" ", ""),
        "language": language,
        "edition": edition,
        "clauses_imported": result["clauses_imported"],
        "rag_chunks": result["rag_chunks"],
        "parse_method": result["parse_method"],
        "warnings": result.get("warnings", []),
        "validation": result["validation"],
        "file_id": result["file_id"],
        "replace_previous": replace,
    }


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

@router.post("/iso/translate")
async def translate_iso_clauses(
    body: TranslateRequest,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    if body.source_language not in ("en", "he") or body.target_language not in ("en", "he"):
        raise HTTPException(status_code=400, detail="source_language and target_language must be en or he")
    if body.source_language == body.target_language:
        raise HTTPException(status_code=400, detail="source and target language must differ")

    std = body.standard.upper().replace(" ", "")
    with get_conn() as conn:
        sql = """
            SELECT clause_id, title, body, sort_order
            FROM iso_clause_text
            WHERE standard = %s AND language = %s
        """
        params: list = [std, body.source_language]
        if body.clause_ids:
            placeholders = ", ".join(["%s"] * len(body.clause_ids))
            sql += f" AND clause_id IN ({placeholders})"
            params.extend(body.clause_ids)
        sql += " ORDER BY sort_order, clause_id"
        rows = conn.execute(sql, params).fetchall()

    ordered_rows = sorted(
        rows_to_list(rows),
        key=lambda r: (_sort_key(str(r["clause_id"])), str(r["clause_id"])),
    )

    if not ordered_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No {body.source_language} clauses found for standard",
        )

    translated: list[tuple[str, str, str, int]] = []
    errors: list[str] = []
    for row in ordered_rows:
        try:
            title_out, body_out = await translate_clause_text(
                row["title"],
                row["body"],
                source_language=body.source_language,
                target_language=body.target_language,
            )
            translated.append(
                (
                    row["clause_id"],
                    title_out,
                    body_out,
                    _sort_key(str(row["clause_id"])),
                )
            )
        except Exception as exc:
            errors.append(f"{row['clause_id']}: {exc}")

    if not translated:
        raise HTTPException(status_code=502, detail=f"Translation failed: {'; '.join(errors[:3])}")

    with get_conn() as conn:
        count = import_translated_clauses(
            conn,
            standard=std,
            edition=body.edition,
            clauses=translated,
            target_language=body.target_language,
            admin_id=admin.id,
        )
        from app.iso.parser import ParsedClause
        from app.iso.rag_index import file_sha256, index_clauses

        parsed = [
            ParsedClause(cid, title, body_text, sort_order)
            for cid, title, body_text, sort_order in translated
        ]
        index_clauses(
            conn,
            standard=std,
            language=body.target_language,
            edition=body.edition,
            corpus_id=f"translate-{std}",
            source_name=f"{std}-{body.target_language}-translated",
            clauses=parsed,
            content_sha256=file_sha256(b"translated"),
        )
        conn.commit()

    return {
        "standard": std,
        "source_language": body.source_language,
        "target_language": body.target_language,
        "translated_clauses": count,
        "errors": errors,
    }


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
