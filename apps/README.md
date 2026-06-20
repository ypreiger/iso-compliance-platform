# Application services (Phase 1)

Flavor-agnostic services deployed via `infra/openshift-rhoai/app/` or `infra/k8s-litellm/app/`.

| Service | Role |
|---------|------|
| `iso-api` | REST/BFF, workflow orchestration |
| `iso-web` | Consultant + supervisor UI (EN/HE) |
| `iso-worker` | Async jobs: RAG index, mapping, export |

## Status

Not implemented — architecture and PRD in `docs/`.
