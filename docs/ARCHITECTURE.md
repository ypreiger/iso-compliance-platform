# ISO Compliance AI Platform — Architecture

## System Overview

![General architecture overview](./architecture-overview.png)

The platform uses `iso-api-orchestrator` as the single workflow coordinator:
- `iso-web` calls orchestrator APIs for projects, corpus, mapping, and retrieval.
- `iso-doc-parse-rag` handles upload parsing (`/parse`) for PDF/DOC/DOCX ingestion.
- `iso-doc-gen` handles export generation (`/generate`) independently.
- MaaS routes all model traffic and integrates with TrustyAI/guardrails.
- ArgoCD reconciles manifests; images are built in CI and pushed to registry.

## Services

| Service | Path | Role |
|---------|------|------|
| `iso-api-orchestrator` | `apps/iso-api/` | FastAPI orchestrator — projects, findings, corpus, RAG |
| `iso-web` | `apps/iso-web/` | React SPA — viewer, admin, compliance UI |
| `iso-doc-parse-rag` | `services/docgen/` | Parse + clause extraction agent (`/parse`) |
| `iso-doc-gen` | `services/docgen/` | Generation/export agent (`/generate`) |
| `playground` | `gitops/layers/03-application/playground.yaml` | Unified AI chat, all models |

## Agent Architecture

`iso-api-orchestrator` pipeline:
1. Store original upload in `corpus_files` (BYTEA).
2. Call `iso-doc-parse-rag /parse` for structured clause extraction.
3. Persist normalized clauses to `iso_clause_text`.
4. Build retrieval chunks in `rag_documents`.
5. Run validation (`rag_hit_rate`, phrase checks) and attach report metadata.
6. Route export requests to `iso-doc-gen /generate`.

## Model as a Service (MaaS) — Per-Task Configuration

Each task uses an independently configurable model:

| Task | Env var prefix | Default | Purpose |
|------|---------------|---------|---------|
| Document parsing | `PARSE_MODEL_*` | qwen3-4b-instruct | PDF/DOC → clauses |
| ISO extraction | `EXTRACT_MODEL_*` | qwen3-4b-instruct | Structure raw text |
| Translation | `TRANSLATE_MODEL_*` | qwen3-4b-instruct | EN↔HE |
| Report generation | `GENERATE_MODEL_*` | qwen3-4b-instruct | Narrative text |

Configure in `gitops/overlays/ocp-sandbox3159/cluster-config.yaml` (`iso-app-config`).

## Two Deployment Flavors

### Flavor A — Red Hat OpenShift

| Component | Technology |
|-----------|------------|
| Orchestration | OpenShift 4.x |
| Image builds | External CI build + registry push |
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

Switch between flavors by adjusting model endpoints and routing manifests for each environment.

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
    03-application/       iso-api-orchestrator, iso-web, doc agents, playground
    04-rag-population/    seed data job
  overlays/
    ocp-sandbox3159/      cluster-specific: images, ConfigMaps, ArgoCD apps
      llm-ai/             TrustyAI + GuardrailsOrchestrator + RBAC → llm namespace
      apps/               ArgoCD Application CRs
deploy/
  openshift/              OpenShift-specific YAML (Routes, AI serving)
  kubernetes/             Pure K8s YAML (Ingress, Ollama)
```
