# ISO Compliance AI Platform

AI-powered ISO compliance management platform built on Red Hat OpenShift AI.

## Quick Links

| | URL |
|---|---|
| **AI Playground** | https://playground-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com |
| **ISO Compliance App** | https://iso-web-iso-platform.apps.ocp.7hrxw.sandbox880.opentlc.com |
| **RHOAI Dashboard** | https://rhods-dashboard-redhat-ods-applications.apps.ocp.7hrxw.sandbox880.opentlc.com |
| **Grafana** (single ops dashboard) | https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com — search **MaaS Token Metrics Dashboard (with User/Model Filters)** |
| **ArgoCD** | https://openshift-gitops-server-openshift-gitops.apps.ocp.7hrxw.sandbox880.opentlc.com |
| **MaaS Gateway** | https://maas.apps.ocp.7hrxw.sandbox880.opentlc.com |

## Documentation

| Doc | What it covers |
|-----|---------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, agent topology, two deployment flavors |
| [DEPLOY.md](docs/DEPLOY.md) | Installation, GitOps, cluster bootstrap |
| [RHOAI_MAAS_GUARDRAILS.md](docs/RHOAI_MAAS_GUARDRAILS.md) | Qwen3 + MaaS + TrustyAI setup |
| [DEMO_PRESENTATION.md](docs/DEMO_PRESENTATION.md) | **Customer presentation flow** (start here for demos) |
| [AUTH.md](docs/AUTH.md) | Google OAuth, user roles |
| [OBSERVABILITY.md](docs/OBSERVABILITY.md) | Single Grafana dashboard: tokens, CPU/RAM, network |

## Services

```
iso-web      → React SPA (nginx)
iso-api-orchestrator → FastAPI orchestrator
iso-doc-parse-rag    → Document parsing + RAG extraction agent (PDF/DOC/DOCX/Excel)
iso-doc-gen          → Document generation/export agent
playground   → Unified AI chat (Qwen3 + GPT-4o + GPT-4o-mini + GPT-3.5-turbo)
```

## Models

| Model | Provider | Tier | Notes |
|-------|----------|------|-------|
| **GPT-oss-20b** | RHOAI vLLM (on-prem L40 GPU) | Enterprise | 21B MoE (3.6B active), 128K context, Apache 2.0, Reasoning |
| **BGE-M3** | RHOAI vLLM (on-prem CPU) | Enterprise | Multilingual embeddings (EN/HE), 1024-dim, 568M params |
| **Qwen3-4B-Instruct** | RHOAI vLLM (on-prem L40 GPU) | Enterprise | 131K context, 4B params, Red Hat certified |
| **GPT-4o** | OpenAI (via MaaS proxy) | Premium | External, highest quality |
| **GPT-4o-mini** | OpenAI (via MaaS proxy) | Cost-effective | External, fast |
| **GPT-3.5-turbo** | OpenAI (via MaaS proxy) | Cost-effective | External, legacy |

## Two Deployment Flavors

- **`deploy/openshift/`** — Red Hat OpenShift (Routes, RHOAI, Kuadrant, ArgoCD-managed manifests)
- **`deploy/kubernetes/`** — Pure Kubernetes (Ingress, Ollama, standard k8s)

## Database Migrations

Migrations run automatically via GitOps PostSync hooks in layer 02-app-infra.

### sort_order Scale Migration (2026-06)
ISO clause `sort_order` migrated from 3-digit (401) to 9-digit base-100 encoding (401000000)
to support hierarchical sorting (4 < 4.1 < 4.2 < 5).

**Migration Job:** `gitops/layers/02-app-infra/migrate-sort-order-job.yaml`  
**Idempotent:** Safe to re-run; only updates rows with `sort_order < 1000000`  
**Rollback:** Automated rollback available via GitOps revert
