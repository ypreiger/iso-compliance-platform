# Cluster deploy — sandbox `ocp.8mkwb.sandbox3159`

This runbook matches the live **RHOAI 3.5 + MaaS** sandbox where **claude-playground** already uses **OpenAI** (`openai-api-key` secret). The ISO platform reuses the same LLM credentials and keeps playground untouched.

## Prerequisites

| Item | Status on sandbox |
|------|-------------------|
| OpenShift GitOps (`openshift-gitops`) | Installed |
| RHOAI / MaaS | `https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com` |
| Namespace `iso-platform` | Created by overlay |
| PostgreSQL (Software Catalog) | Service `postgresql`, DB/user `iso` |
| `openai-api-key` secret | Same as playground |

## One-command bootstrap

```bash
oc login https://api.ocp.8mkwb.sandbox3159.opentlc.com:6443
cd iso-compliance-platform
./scripts/bootstrap-openshift-cluster.sh
```

Bootstrap:

1. Syncs `iso-secrets` from catalog DB password + OpenAI key  
2. Applies `gitops/overlays/ocp-sandbox3159`  
3. Registers Argo CD Application `iso-compliance-platform`  
4. Builds images locally (binary `oc start-build`) — required until the private GitHub repo is registered in Argo CD  
5. Runs layer 01–03 verification  

## GitOps overlay

Path: `gitops/overlays/ocp-sandbox3159/`

| File | Purpose |
|------|---------|
| `cluster-config.yaml` | DB host `postgresql`, OpenAI + MaaS URLs, admin emails, dev auth |
| `kustomization.yaml` | Layers 01–04 + catalog DB overlay + BuildConfigs |
| `application.yaml` | Single Argo CD app (automated sync) |
| `buildconfigs.yaml` | Image build definitions |

Layer **02** uses `02-app-infra-catalog` (Redis + PVC only) because PostgreSQL comes from the **OpenShift Software Catalog**.

## URLs

| Service | URL |
|---------|-----|
| Playground (unchanged) | https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| ISO Web | https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| ISO API | https://iso-api-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com |
| MaaS models | https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com/maas-api/v1/models |

## LLM wiring

- **Primary (playground parity):** `LLM_GATEWAY_URL=https://api.openai.com/v1` + `LLM_API_KEY` from `openai-api-key`  
- **On-cluster (optional):** `MAAS_BASE_URL` + `MAAS_MODEL_LOCAL=qwen3-4b-instruct`  

Mapping/report flows use OpenAI models (`gpt-4-turbo`, `gpt-4`) unless you switch env in `cluster-config.yaml`.

## Auth

- **Dev mode** (`AUTH_DEV_MODE=1`): POST `/auth/dev-login` with admin email  
- **Production:** set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `iso-secrets` and rebuild `iso-web` with `VITE_GOOGLE_CLIENT_ID`

Admins: `yaakovpreiger@gmail.com`, `valeria.preiger@gmail.com`

## RAG population (layer 04)

The `rag-iso` image **bundles** `RAG/` at build time (private GitHub clone is not required in-cluster).

```bash
oc delete job iso-rag-populate -n iso-platform --ignore-not-found
oc apply -f gitops/layers/04-rag-population/rag-populate-job.yaml -n iso-platform
./scripts/verify-layer-04.sh
```

## Argo CD (private repo)

Until the repo is registered, Argo shows `Unknown` sync — cluster state is applied via `oc apply -k` + bootstrap builds.

```bash
export GITHUB_TOKEN='ghp_...'
./scripts/register-argocd-repo.sh
argocd app sync iso-compliance-platform   # or wait for auto-sync
```

## Verification

```bash
./scripts/verify-all.sh
```

Manual smoke:

```bash
curl -sf https://claude-playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/health
curl -sf https://iso-api-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/health
curl -sf https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/api/health
```

## Rebuild a single service

```bash
oc patch bc/iso-api -n iso-platform --type=merge \
  -p '{"spec":{"source":{"type":"Binary","git":null,"contextDir":null}}}'
oc start-build bc/iso-api --from-dir=apps/iso-api --wait -n iso-platform
oc rollout restart deploy/iso-api -n iso-platform
```

For `rag-iso`, build from **repo root** (includes `RAG/`):

```bash
oc start-build bc/rag-iso --from-dir=. --wait -n iso-platform
```
