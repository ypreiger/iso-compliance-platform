# ISO Compliance Platform

Plan and build an ISO certification assistant for **ISO 9001**, **ISO 14001**, **ISO 45001**, and **ISO 13485**.

## Deployment flavors (same repo)

| Flavor | Status | LLM gateway | Target |
|--------|--------|-------------|--------|
| **`openshift-rhoai`** | **Primary — implement & test first** | RHOAI **MaaS** (OpenAI-compatible `/v1`) | OpenShift + OpenShift AI |
| **`k8s-litellm`** | **Maintained in parallel** | **LiteLLM** proxy (OpenAI-compatible) | Generic Kubernetes |

Application code is **flavor-agnostic**: it speaks OpenAI-compatible APIs only. Platform manifests live under `infra/`.

## Repository layout

```
iso-compliance-platform/
├── README.md
├── docs/
│   ├── PRD.md                 # Product requirements
│   ├── ARCHITECTURE.md        # Components, data flow, dual-flavor LLM
│   ├── UI.md                  # Screens: corpus uploads, instructions, supervisor
│   └── DEPLOYMENT.md          # OpenShift/RHOAI vs K8s/LiteLLM runbooks
├── infra/
│   ├── openshift-rhoai/       # GitOps, RHOAI MaaS, routes, secrets patterns
│   └── k8s-litellm/         # K8s manifests, LiteLLM, ingress
├── apps/
│   ├── iso-api/               # BFF: auth, projects, mapping, ISO text, admin
│   └── iso-web/               # React SPA (EN/HE UI, RTL/LTR, all screens)
├── services/
│   ├── rag-iso/               # RAG ingest Job
│   └── docgen/                # Excel/DOCX export service
├── gitops/                    # 4-layer one-click deploy
├── RAG/                       # Seed corpus (Standards, Samples, Templates)
├── scripts/                   # deploy-all, verify-*, dry-run-local.sh
└── docker-compose.yml         # Local dry-run stack
```

## Languages

- **UI / logic:** English
- **Samples, templates, customer exports:** Hebrew (RTL DOCX/XLSX)

## Quick links

- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [User interface plan](docs/UI.md)
- [Deployment flavors](docs/DEPLOYMENT.md)
- [GitOps one-click deploy](docs/GITOPS.md)
- [Microservices map](docs/MICROSERVICES.md)
- [Authentication (Google + admins)](docs/AUTH.md)

## One-click deploy (OpenShift)

Assumes only a cluster with **OpenShift GitOps** is preinstalled:

```bash
./scripts/dry-run-local.sh   # pytest + API smoke + web build (no OpenShift)
oc login …
./scripts/deploy-all.sh
```

Four GitOps layers: platform infra → app infra → application → RAG population (`RAG/` seed corpus).

## Mock UI (browser preview)

Open **`mock-ui/index.html`** in your browser — no build or cluster needed. See [mock-ui/README.md](mock-ui/README.md).

## Reference (patterns only)
(https://github.com/ypreiger/ragu-builder) repo uses **Open WebUI → openai-gateway → MaaS → LLMInferenceService**. This product reuses the **gateway abstraction** idea but owns its own namespace, models, and compliance workflow.
