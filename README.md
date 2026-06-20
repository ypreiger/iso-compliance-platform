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
├── apps/                      # iso-web, iso-api, workers (Phase 1)
└── services/                  # (Phase 1) RAG ISO, document generation
```

## Languages

- **UI / logic:** English
- **Samples, templates, customer exports:** Hebrew (RTL DOCX/XLSX)

## Quick links

- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [User interface plan](docs/UI.md)
- [Deployment flavors](docs/DEPLOYMENT.md)

## Reference (patterns only)

The [ragu-builder](https://github.com/ypreiger/ragu-builder) repo uses **Open WebUI → openai-gateway → MaaS → LLMInferenceService**. This product reuses the **gateway abstraction** idea but owns its own namespace, models, and compliance workflow.
