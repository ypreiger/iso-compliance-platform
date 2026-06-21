# ISO Compliance AI Platform

AI-powered ISO compliance management platform built on Red Hat OpenShift AI.

## Quick Links

| | URL |
|---|---|
| **AI Playground** | https://playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| **ISO Compliance App** | https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| **RHOAI Dashboard** | https://rhods-dashboard-redhat-ods-applications.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| **ArgoCD** | https://openshift-gitops-server-openshift-gitops.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| **MaaS Gateway** | https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com |

## Documentation

| Doc | What it covers |
|-----|---------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, agent topology, two deployment flavors |
| [DEPLOY.md](docs/DEPLOY.md) | Installation, GitOps, cluster bootstrap |
| [RHOAI_MAAS_GUARDRAILS.md](docs/RHOAI_MAAS_GUARDRAILS.md) | Qwen3 + MaaS + TrustyAI setup |
| [DEMO_PRESENTATION.md](docs/DEMO_PRESENTATION.md) | **Customer presentation flow** (start here for demos) |
| [AUTH.md](docs/AUTH.md) | Google OAuth, user roles |

## Services

```
iso-web      → React SPA (nginx)
iso-api      → FastAPI orchestrator
iso-docgen   → Document parsing + generation agent (PDF/DOC/DOCX/Excel)
playground   → Unified AI chat (Qwen3 + GPT-4o + GPT-4o-mini + GPT-3.5-turbo)
```

## Models

| Model | Provider | Tier | Notes |
|-------|----------|------|-------|
| Qwen3 4B Instruct 2507 | RHOAI MaaS (on-prem GPU) | Enterprise | 131k context, L40 GPU |
| GPT-4o | OpenAI | — | External |
| GPT-4o Mini | OpenAI | — | External |
| GPT-3.5 Turbo | OpenAI | — | External |

## Two Deployment Flavors

- **`deploy/openshift/`** — Red Hat OpenShift (Routes, BuildConfig, RHOAI, Kuadrant)
- **`deploy/kubernetes/`** — Pure Kubernetes (Ingress, Ollama, standard k8s)

## Database Migrations

Migrations run automatically via GitOps PostSync hooks in layer 02-app-infra.

### sort_order Scale Migration (2026-06)
ISO clause `sort_order` migrated from 3-digit (401) to 9-digit base-100 encoding (401000000)
to support hierarchical sorting (4 < 4.1 < 4.2 < 5).

**Migration Job:** `gitops/layers/02-app-infra/migrate-sort-order-job.yaml`  
**Idempotent:** Safe to re-run; only updates rows with `sort_order < 1000000`  
**Rollback:** Automated rollback available via GitOps revert
