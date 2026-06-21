# ISO Document Parsing & RAG Architecture

## Overview

This document describes the end-to-end pipeline for ingesting ISO standard documents
(PDF, DOC, DOCX) into the ISO Compliance Platform, populating the viewer database,
and indexing content for retrieval-augmented generation (RAG).

---

## Pipeline Diagram

```
Upload PDF / DOC / DOCX
        │
        ▼
┌─────────────────────────────────┐
│ 1. Store original file           │  corpus_files (BYTEA in PostgreSQL)
│    corpus_files table            │  → downloadable at any time
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 2. Extract raw text              │
│    PDF  → PyMuPDF (fitz)         │  reading-order block extraction
│    DOCX → python-docx            │  heading styles preserved
│    DOC  → antiword binary        │  legacy Word 6–2000
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 3. LLM Parsing Agent             │  GPT-4o via OpenAI API
│    • System prompt: ISO expert   │  Handles multi-lingual (EN + HE)
│    • Text → structured JSON      │  [{clause_id, title, body}, ...]
│    • Segments by top-level §§    │  ≤ 12 000 chars per call
│    • Merge + dedupe results      │
│                                  │
│    Fallback: regex parser        │  if LLM unavailable / returns 0 clauses
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 4. Import to Database            │
│    iso_clause_text               │  structured viewer store
│    rag_documents                 │  1 200-char overlapping chunks
│    (replace or merge mode)       │  keyed by standard + language + clause_id
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│ 5. Validation Agent              │
│    • Sample up to 20 clauses     │
│    • For each: fetch RAG chunks  │
│    • Check key phrase presence   │
│    • Report rag_hit_rate +       │
│      phrase_hit_rate             │
│    • Result stored in metadata   │
│      and shown in UI badge       │
└─────────────────────────────────┘
        │
        ▼
     Upload response
     {clauses_imported, rag_chunks,
      parse_method, validation{...},
      file_id, warnings}
```

---

## Components

### `app/iso/document_extract.py`
Extracts plain text from binary documents:
- **`extract_text_from_pdf()`** — PyMuPDF `page.get_text("blocks", sort=True)`, falls back to `pypdf`
- **`extract_text_from_docx()`** — python-docx paragraph walk; heading styles emit `## heading`
- **`extract_text_from_doc()`** — antiword subprocess (compiled from source in Containerfile)
- **`extract_text()`** — unified entry point

### `app/iso/llm_parser.py`
LLM-powered ISO clause extraction agent:
- **`pre_segment(text)`** — splits at top-level ISO section headings to keep each call ≤ 12 000 chars
- **`_llm_parse_segment(segment, ...)`** — single GPT-4o call with zero temperature; returns raw dicts
- **`_merge_results(items)`** — deduplicates clause_ids, joins split bodies
- **`parse_text_with_llm(text, ...)`** — public API; segments → calls → merge

The system prompt instructs GPT-4o to:
1. Return only the normative clauses (skip ToC, copyright, bibliography)
2. Use exact ISO clause numbering (4, 4.1, 4.1.1 …)
3. Preserve full body text verbatim
4. Return strict JSON array `[{clause_id, title, body}]`

### `app/iso/clause_parse.py`
Regex-based fallback parser (used when LLM unavailable):
- `parse_iso_document_text()` — hierarchical stack parser
- `parse_docx_faithful()` — block-order DOCX walk

### `app/iso/pipeline.py`
Orchestrates all five steps for one file upload:
- `run_ingest_pipeline(conn, ...)` — called from the upload route
- Logs each step; partial failures surface as HTTP 400/500 with clear messages

### `app/iso/rag_index.py`
Chunks and indexes clauses into `rag_documents`:
- 1 200-char chunks with 200-char overlap
- Metadata: `{standard, language, edition, clause_id, title, corpus_id, source}`
- `purge_standard_language()` — delete all chunks before replace-mode import

### `app/iso/validate.py`
Post-import validation:
- `validate_import(conn, standard, language, sample_n=20)` → `ValidationReport`
- Picks every N-th clause; checks RAG has chunk for it; checks key bigrams appear
- Thresholds: rag_hit_rate ≥ 80%, phrase_hit_rate ≥ 70% → `passed=True`

### `app/iso/rag_search.py`
Keyword search for `run-auto` mapping:
- `search_iso_rag(conn, standard, language, query, limit=1)`
- Scores chunks by term frequency; returns best-matching clause

### `app/routes/documents.py`
Original-file management:
- `GET  /admin/corpus/files` — list all stored files (metadata only)
- `GET  /admin/corpus/files/{id}` — download original (auth required)
- `DELETE /admin/corpus/files/{id}` — remove stored file (admin only)

---

## Database Tables

| Table | Purpose |
|-------|---------|
| `corpus_documents` | Upload records; `metadata` JSONB holds pipeline result |
| `corpus_files` | Original binary content (`file_data BYTEA`) |
| `iso_clause_text` | Structured viewer store per standard/language/clause |
| `rag_documents` | Chunked text for keyword/RAG search |

---

## Configuration

| Env var | Purpose | Default |
|---------|---------|---------|
| `OPENAI_API_KEY` | OpenAI key for LLM agent | — |
| `LLM_API_KEY` | Alternative key (used if OPENAI_API_KEY absent) | — |
| `LLM_GATEWAY_URL` | Custom OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `LLM_MODEL_MAPPING` | Model name | `gpt-4o` |

If neither key is set, the LLM agent is skipped and the regex parser is used.

---

## Translation Flow

```
EN clauses (iso_clause_text)
        │
        ▼  POST /admin/corpus/iso/translate
  translate_clause_text()  [GPT-4o]
        │
        ▼
HE clauses (iso_clause_text)
  + HE RAG chunks (rag_documents) — replaced
```

Supports EN→HE and HE→EN. Select direction in the admin UI.

---

## Retrieval Flow (ISO Viewer)

```
GET /v1/iso/clauses?standard=ISO9001&language=he
        │
        ▼
iso_clause_text WHERE standard='ISO9001' AND language='he'
  → if clause missing in HE, fall back to EN with fallback=true flag
        │
        ▼
Client renders clause list; fallback shown with EN badge
```

## Retrieval Flow (Auto-Mapping)

```
POST /v1/projects/{id}/mapping/run-auto
        │
        ▼
finding_text  →  search_iso_rag()
  CASE-score each rag_documents chunk by term overlap
        │
        ▼
  Best-matching clause_id + title → finding_clause_mappings
```

---

## Deployment

See [CLUSTER_DEPLOY.md](./CLUSTER_DEPLOY.md).

Quick rebuild:
```bash
oc start-build iso-api --from-dir=apps/iso-api --wait --follow
oc start-build iso-web --from-dir=apps/iso-web --wait --follow
oc rollout restart deployment/iso-api deployment/iso-web -n iso-platform
```

antiword is compiled from vendored source (`apps/iso-api/vendor/antiword-0.37`) in the Containerfile.
PyMuPDF (fitz) is installed via `pip install pymupdf`.
