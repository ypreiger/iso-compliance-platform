# ISO Compliance Platform — Agent Architecture

## Overview

The platform is built as a set of focused microservice agents, each responsible
for a specific document or AI task. Every agent connects to an LLM **Model as a
Service** endpoint, configurable independently per task and per deployment flavor.

---

## Service Map

```
Browser / API client
        │
        ▼
┌───────────────────┐
│    iso-web         │  React SPA  (nginx)
└───────────────────┘
        │ REST
        ▼
┌───────────────────┐
│    iso-api         │  Orchestrator  (FastAPI)
│                   │  ─ projects, findings, mapping, viewer
│                   │  ─ corpus upload → calls doc-agent
│                   │  ─ translation (calls LLM directly)
└──────┬────────────┘
       │ HTTP POST /parse
       │ HTTP POST /generate
       ▼
┌───────────────────┐         ┌─────────────────────────────┐
│    doc-agent       │ ──────▶ │  Model as a Service          │
│   (iso-docgen)     │         │                              │
│                   │         │  OpenShift flavor:            │
│  /parse           │         │    vLLM / OpenShift AI        │
│  /generate/excel  │         │    ServingRuntime +           │
│  /generate/docx   │         │    InferenceService CRDs      │
│  /generate/pdf    │         │                              │
│  /models          │         │  Kubernetes flavor:           │
└───────────────────┘         │    Ollama (on-cluster)        │
                              │    or OpenAI API              │
                              └─────────────────────────────┘
```

---

## Services

### `iso-api` — Orchestrator API
**Path:** `apps/iso-api/`
**URL (OpenShift):** `https://iso-api-iso-platform.apps.ocp.../`

| Endpoint | Description |
|----------|-------------|
| `POST /admin/corpus/iso/upload` | Upload PDF/DOC/DOCX → calls doc-agent /parse → stores clauses |
| `POST /admin/corpus/iso/translate` | Translate EN↔HE via LLM |
| `POST /admin/corpus/iso/delete-standard` | Remove all data for a standard |
| `GET  /v1/iso/clauses` | Bilingual viewer — ISO clause text |
| `POST /v1/projects/{id}/mapping/run-auto` | Auto-map findings to clauses (keyword RAG search) |
| `POST /admin/corpus/files/{id}` | Download stored original file |

### `doc-agent` — Document Parsing + Generation
**Path:** `services/docgen/`
**In-cluster name:** `iso-docgen` (OpenShift) / `doc-agent` (Kubernetes)

This is the core document intelligence agent. It handles:

#### Parsing (input documents)
| Format | Extraction method | Structuring |
|--------|-------------------|-------------|
| PDF | PyMuPDF (reading-order blocks) | LLM (gpt-4o or vLLM) |
| DOCX | python-docx block walk + heading styles | LLM |
| DOC  | antiword binary | LLM |
| Excel (.xlsx) | openpyxl (no LLM needed) | Structured |

#### Generation (output documents)
| Format | Library | Use case |
|--------|---------|----------|
| Excel (.xlsx) | xlsxwriter | Compliance reports, coverage matrix, findings list |
| DOCX | python-docx | Audit report narrative |
| PDF | ReportLab | Summary report, certificate |

#### API
```
POST /parse
  Body: {filename, content_b64, standard, language, task}
  Returns: {clauses: [{clause_id, title, body}], model_used, parse_method, ...}

POST /generate
  Body: {format, project_name, standard, locale, findings, mappings, coverage}
  Returns: binary file (Content-Disposition: attachment)

GET  /models     → configured endpoints per task (key redacted)
GET  /health     → liveness
GET  /ready      → readiness + dependency check
```

---

## Model as a Service

Each task uses an independently configurable LLM endpoint.

| Task | Default model | Purpose |
|------|--------------|---------|
| `PARSE` | `gpt-4o` | Structure raw PDF/DOC/DOCX text into clauses |
| `EXTRACT` | `gpt-4o` | ISO clause extraction with context awareness |
| `TRANSLATE` | `gpt-4o` | Faithful EN↔HE translation |
| `GENERATE` | `gpt-4o-mini` | Report narrative (cheaper model is fine) |

### Configuration (per deployment flavor)

```bash
# OpenShift / OpenShift AI (on-prem vLLM)
EXTRACT_MODEL_URL=http://mistral-7b-predictor.iso-platform.svc.cluster.local/v1
EXTRACT_MODEL_NAME=mistral-7b-instruct

# Kubernetes / Ollama (on-cluster open-source)
EXTRACT_MODEL_URL=http://ollama.iso-platform.svc.cluster.local:11434/v1
EXTRACT_MODEL_NAME=mistral

# OpenAI (default / cloud)
EXTRACT_MODEL_URL=https://api.openai.com/v1
EXTRACT_MODEL_NAME=gpt-4o
```

All four task vars (`PARSE_MODEL_*`, `EXTRACT_MODEL_*`, `TRANSLATE_MODEL_*`, `GENERATE_MODEL_*`)
can be set independently. Any missing value falls back to `LLM_API_KEY` / `OPENAI_API_KEY`.

---

## Two Deployment Flavors

### Flavor A — Red Hat OpenShift Stack

| Component | Technology |
|-----------|------------|
| Container orchestration | OpenShift (OCP 4.x) |
| Image builds | `BuildConfig` (binary + Git strategies) |
| Ingress | OpenShift `Route` (TLS edge termination) |
| LLM serving | OpenShift AI (`ServingRuntime` + `InferenceService` CRDs) |
| Object storage | Optional: ODF / Noobaa for large file storage |
| Manifests | `deploy/openshift/` |

```bash
# Deploy model config
oc apply -f deploy/openshift/base/model-config.yaml

# Build & deploy doc-agent from local source
oc start-build iso-docgen --from-dir=services/docgen --wait --follow
oc rollout restart deployment/iso-docgen -n iso-platform

# (Optional) Deploy OpenShift AI model
oc apply -f deploy/openshift/model-serving/
```

### Flavor B — Kubernetes + Open Source

| Component | Technology |
|-----------|------------|
| Container orchestration | Kubernetes 1.28+ |
| Image builds | Podman / Docker / Kaniko |
| Ingress | Nginx Ingress Controller |
| LLM serving | Ollama (on-cluster) or external API |
| Object storage | MinIO or any S3-compatible |
| Manifests | `deploy/kubernetes/` |

```bash
# Deploy model config + doc-agent
kubectl apply -f deploy/kubernetes/base/

# (Optional) Deploy Ollama for on-cluster models
kubectl apply -f deploy/kubernetes/ollama/
kubectl exec -n iso-platform deploy/ollama -- ollama pull mistral
# Then update deploy/kubernetes/base/model-config.yaml URLs to Ollama
kubectl apply -f deploy/kubernetes/base/model-config.yaml
kubectl rollout restart deployment/doc-agent -n iso-platform
```

---

## Document Flow: Upload → Index → Validate

```
Admin uploads ISO9001-EN.pdf
          │
          ▼
POST /admin/corpus/iso/upload (iso-api)
          │
          ├─ INSERT corpus_documents (status=processing)
          │
          ▼
POST http://iso-docgen:8080/parse (doc-agent)
          │
          ├─ PyMuPDF → raw text (reading-order)
          ├─ GPT-4o (EXTRACT task) → [{clause_id, title, body}]
          └─ Returns JSON
          │
          ▼
iso-api receives clauses
          │
          ├─ INSERT corpus_files (original bytes stored)
          ├─ INSERT iso_clause_text (viewer store)
          ├─ INSERT rag_documents  (chunked, metadata-tagged)
          └─ UPDATE corpus_documents (status=ready, metadata=report)
          │
          ▼
Validation (iso-api, inline)
          │
          ├─ Sample 20 clauses
          ├─ Fetch RAG chunks for each
          ├─ Check key phrases present
          └─ Store validation{rag_hit_rate, phrase_hit_rate, passed}
          │
          ▼
Response to admin UI:
  {clauses_imported, rag_chunks, parse_method,
   validation{rag_hit_rate, phrase_hit_rate, passed},
   file_id}
```

## Document Flow: Generate Report

```
Admin/user requests Excel report
          │
          ▼
GET /projects/{id}/exports (iso-api — future: POST /admin/corpus/generate)
          │
          ▼
POST http://iso-docgen:8080/generate
          Body: {format:"excel", findings:[...], mappings:[...], coverage:[...]}
          │
          ├─ xlsxwriter → .xlsx bytes
          └─ Returns binary (Content-Disposition: attachment)
          │
          ▼
User downloads Excel file with:
  Sheet 1: Summary
  Sheet 2: Findings
  Sheet 3: Clause Mappings
  Sheet 4: Coverage Matrix
```

---

## Database Schema (key tables)

| Table | Purpose |
|-------|---------|
| `corpus_documents` | Upload records; `metadata` JSONB holds full pipeline result |
| `corpus_files` | Original binary content (`file_data BYTEA`); downloadable |
| `iso_clause_text` | Structured viewer store per standard/language/clause |
| `rag_documents` | Chunked text (1 200 chars, 200 overlap) for RAG search |

---

## Adding a New Agent

1. Create `services/my-agent/` with `app/main.py`, `requirements.txt`, `Containerfile`
2. Add `deploy/openshift/base/my-agent.yaml` (Deployment + Service + Route)
3. Add `deploy/kubernetes/base/my-agent.yaml` (Deployment + Service + Ingress)
4. Add model config keys to `deploy/*/base/model-config.yaml`
5. Add the service name to `app/config.py` in iso-api if it needs to call it
6. Build: `oc start-build my-agent --from-dir=services/my-agent --wait`

---

## Switching Models

```bash
# Example: switch EXTRACT to Mistral on OpenShift AI
oc patch configmap doc-agent-model-config -n iso-platform --type=merge -p '{
  "data": {
    "EXTRACT_MODEL_URL": "http://mistral-7b-predictor.iso-platform.svc.cluster.local/v1",
    "EXTRACT_MODEL_NAME": "mistral-7b-instruct"
  }
}'
oc rollout restart deployment/iso-docgen -n iso-platform
```

---

_See also: [PARSING_ARCHITECTURE.md](./PARSING_ARCHITECTURE.md) | [CLUSTER_DEPLOY.md](./CLUSTER_DEPLOY.md)_
