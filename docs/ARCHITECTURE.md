# ISO Compliance AI Platform — Architecture

## System Overview

```
Browser
  ├── ISO Compliance App (iso-web → iso-api)
  │     ├── Projects, Findings, Clause Mapping
  │     ├── ISO Standards Viewer (EN/HE bilingual)
  │     └── Admin: Upload → doc-agent → parse → RAG index
  │
  └── AI Playground
        ├── Qwen3 4B Instruct — RHOAI MaaS (on-prem GPU)
        ├── GPT-4o / GPT-4o-mini / GPT-3.5-turbo (OpenAI)
        └── TrustyAI observability sidebar
```

## Services

| Service | Path | Role |
|---------|------|------|
| `iso-api` | `apps/iso-api/` | FastAPI orchestrator — projects, findings, corpus, RAG |
| `iso-web` | `apps/iso-web/` | React SPA — viewer, admin, compliance UI |
| `iso-docgen` | `services/docgen/` | **Doc-agent**: parse PDF/DOC/DOCX/Excel + generate reports |
| `playground` | `gitops/layers/03-application/playground.yaml` | Unified AI chat, all models |

## Agent Architecture

```
Upload PDF/DOC/DOCX
      │
      ▼ POST /parse
┌─────────────────┐        ┌──────────────────────────────────┐
│   iso-docgen    │───────▶│  Model as a Service               │
│   (doc-agent)   │        │  PARSE_MODEL   gpt-4o             │
│                 │        │  EXTRACT_MODEL gpt-4o             │
│  /parse         │        │  TRANSLATE_MODEL gpt-4o           │
│  /generate/xlsx │        │  GENERATE_MODEL gpt-4o-mini       │
│  /generate/docx │        └──────────────────────────────────┘
│  /generate/pdf  │
│  /models        │
└─────────────────┘
      │ structured clauses
      ▼
iso-api pipeline:
  1. Store original file → corpus_files (BYTEA)
  2. Extract text — PyMuPDF / antiword / python-docx
  3. LLM clause extraction → [{clause_id, title, body}]
  4. Index → iso_clause_text + rag_documents
  5. Validate → RAG hit rate + phrase match score
```

## Model as a Service (MaaS) — Per-Task Configuration

Each task uses an independently configurable model:

| Task | Env var prefix | Default | Purpose |
|------|---------------|---------|---------|
| Document parsing | `PARSE_MODEL_*` | gpt-4o | PDF/DOC → clauses |
| ISO extraction | `EXTRACT_MODEL_*` | gpt-4o | Structure raw text |
| Translation | `TRANSLATE_MODEL_*` | gpt-4o | EN↔HE |
| Report generation | `GENERATE_MODEL_*` | gpt-4o-mini | Narrative text |

Configure in `deploy/openshift/base/model-config.yaml` (OpenShift) or `deploy/kubernetes/base/model-config.yaml` (plain K8s).

## Two Deployment Flavors

### Flavor A — Red Hat OpenShift

| Component | Technology |
|-----------|------------|
| Orchestration | OpenShift 4.x |
| Image builds | `BuildConfig` (binary + Git) |
| Ingress | OpenShift `Route` (TLS edge) |
| LLM inference | RHOAI `LLMInferenceService` (vLLM) |
| LLM access control | Kuadrant + Authorino (MaaS tiers) |
| Observability | TrustyAI `TrustyAIService` + `GuardrailsOrchestrator` |
| GitOps | OpenShift GitOps (ArgoCD) |
| Manifests | `deploy/openshift/` |

### Flavor B — Kubernetes + Open Source

| Component | Technology |
|-----------|------------|
| Orchestration | Kubernetes 1.28+ |
| Image builds | Podman / Docker / Kaniko |
| Ingress | Nginx Ingress Controller |
| LLM inference | Ollama (on-cluster) or external OpenAI |
| Observability | Optional: bring-your-own |
| GitOps | ArgoCD community edition |
| Manifests | `deploy/kubernetes/` |

Switch between flavors: edit `deploy/*/base/model-config.yaml` — same app code, different endpoints.

## Database

PostgreSQL with tables:

| Table | Purpose |
|-------|---------|
| `iso_clause_text` | Structured viewer store (standard / clause / language) |
| `rag_documents` | Chunked text for RAG search (1 200 chars, 200 overlap) |
| `corpus_files` | Original uploaded binary files (BYTEA) |
| `corpus_documents` | Upload records + pipeline result in metadata JSONB |
| `projects` | Compliance projects |
| `findings` | Audit findings per project |
| `finding_clause_mappings` | Finding ↔ clause mappings |

## RHOAI & TrustyAI

```
Qwen3 4B Instruct (LLMInferenceService in llm namespace)
      │
      │ Bearer SA token (audience: maas-default-gateway-sa)
      ▼
MaaS Gateway (Kuadrant + Authorino)
      │ SubjectAccessReview: can SA "post" llminferenceservices?
      ▼
vLLM (port 8000, HTTPS internally)

TrustyAI (TrustyAIService in llm namespace)
      → logs all inferences
      → drift detection, fairness metrics

GuardrailsOrchestrator (qwen3-guardrails in llm namespace)
      → HAP (hate/abuse/profanity) detection
      → Note: in RHOAI ≤ 3.x, fms-guardrails-orchestr8r uses NLP/gRPC protocol
        (LLMInferenceService exposes REST/OpenAI — protocol mismatch causes
        orchestrator pod to crash. App-level topic guardrails remain active.
        Will be resolved when RHOAI autoConfig supports LLMInferenceService.)
```

## GitOps Structure

```
gitops/
  layers/
    01-platform-infra/    namespace, RHOAI config, RBAC
    02-app-infra-catalog/ PostgreSQL, Redis, PVC
    03-application/       iso-api, iso-web, iso-docgen, playground
    04-rag-population/    seed data job
  overlays/
    ocp-sandbox3159/      cluster-specific: images, ConfigMaps, ArgoCD apps
      llm-ai/             TrustyAI + GuardrailsOrchestrator + RBAC → llm namespace
      apps/               ArgoCD Application CRs
deploy/
  openshift/              OpenShift-specific YAML (Routes, BuildConfigs, AI serving)
  kubernetes/             Pure K8s YAML (Ingress, Ollama)
```
