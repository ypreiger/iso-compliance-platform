# GitOps — one-click deployment (OpenShift)

Only **predefined infrastructure**: an **OpenShift cluster** with **OpenShift GitOps** (Argo CD). Everything else is deployed from this repository in **four ordered layers**.

## Layers

| Wave | Argo Application | Purpose |
|------|------------------|---------|
| **1** | `iso-01-platform-infra` | Namespaces, platform RBAC, RHOAI/MaaS **placeholders** (ConfigMaps documenting cluster endpoints) |
| **2** | `iso-02-app-infra` | PostgreSQL, Redis, PVCs, shared ConfigMaps/Secret **examples**, LLM gateway env |
| **3** | `iso-03-application` | `iso-api`, `iso-web`, Services, Routes |
| **4** | `iso-04-rag-population` | Job: clone repo → ingest `RAG/` → PostgreSQL metadata + object store path |

Each layer has:

- `gitops/layers/NN-*/` — manifests
- `scripts/verify-layer-NN.sh` — automated checks
- `docs/GITOPS.md` (this file) — runbook section

## One-click deploy

```bash
# Prerequisites: oc login, OpenShift GitOps installed (openshift-gitops namespace)
export ISO_CLUSTER_DOMAIN='apps.<your-cluster>'   # optional override
export ISO_GITOPS_NAMESPACE='openshift-gitops'

./scripts/deploy-all.sh
```

Options:

```bash
./scripts/deploy-all.sh --verify-only    # CI / preflight
./scripts/deploy-all.sh --layer 2        # stop after app-infra
./scripts/deploy-all.sh --skip-rag       # layers 1–3 only
```

Credentials (when ready):

```bash
cp gitops/layers/02-app-infra/secrets/iso-secrets.example.yaml \
   gitops/layers/02-app-infra/secrets/iso-secrets.yaml
# edit LLM_API_KEY, DATABASE_URL, GIT credentials for private clone
oc apply -f gitops/layers/02-app-infra/secrets/iso-secrets.yaml -n iso-platform
```

**Do not commit** `iso-secrets.yaml` (gitignored pattern).

## App of Apps

Root Application `iso-compliance-platform` in `openshift-gitops` points at `gitops/root/` and syncs all layer Applications with sync waves.

## Private GitHub + RAG LFS

Large PDFs under `RAG/` use **Git LFS**. Before clone/populate Job:

```bash
git lfs install
git lfs pull
```

Register Argo CD repo credentials:

```bash
export GITHUB_TOKEN='ghp_...'
./scripts/register-argocd-repo.sh
```

## Verification matrix

| Layer | Script | Pass criteria |
|-------|--------|---------------|
| 0 (preflight) | `scripts/verify-preflight.sh` | `oc whoami`, GitOps CR exists |
| 1 | `scripts/verify-layer-01.sh` | Namespace `iso-platform` Active |
| 2 | `scripts/verify-layer-02.sh` | Postgres + Redis pods Ready, PVC Bound |
| 3 | `scripts/verify-layer-03.sh` | Routes return HTTP 200 `/health` |
| 4 | `scripts/verify-layer-04.sh` | RAG Job Complete; corpus rows in DB |

Full suite: `./scripts/verify-all.sh`

## k8s-litellm flavor

Same four layers under `infra/k8s-litellm/gitops/` (maintained parity). OpenShift path is **primary** under `gitops/layers/`.
