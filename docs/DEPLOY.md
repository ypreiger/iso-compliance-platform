# Deployment Guide

## Prerequisites

- OpenShift 4.14+ (or Kubernetes 1.28+)
- Red Hat OpenShift AI operator installed
- `oc` / `kubectl` CLI, `git`
- GitHub repo: `https://github.com/ypreiger/iso-compliance-platform`

---

## Bootstrap (first time)

```bash
# 1. Clone repo
git clone https://github.com/ypreiger/iso-compliance-platform.git
cd iso-compliance-platform

# 2. Create secrets (run once, not in git)
oc create secret generic openai-api-key \
  --from-literal=OPENAI_API_KEY=sk-... -n iso-platform

# 3. Apply the ArgoCD Application for the ISO platform
oc apply -f gitops/overlays/ocp-sandbox3159/apps/llm-ai-app.yaml -n openshift-gitops

# 4. Register the GitHub repo in ArgoCD (needed for private/HTTPS repos)
oc create secret generic iso-compliance-gitops-repo \
  --from-literal=type=git \
  --from-literal=url=https://github.com/ypreiger/iso-compliance-platform.git \
  --from-literal=username=<github-user> \
  --from-literal=password=<github-pat> \
  -n openshift-gitops
oc label secret iso-compliance-gitops-repo \
  argocd.argoproj.io/secret-type=repository -n openshift-gitops
```

---

## GitOps (day-2 operations)

Everything is managed by ArgoCD. Make a change → push to `main` → ArgoCD syncs automatically.

### ArgoCD Applications

| App | Source path | Namespace |
|-----|------------|-----------|
| `iso-compliance-platform` | `gitops/overlays/ocp-sandbox3159` | iso-platform |
| `llm-ai-platform` | `gitops/overlays/ocp-sandbox3159/llm-ai` | llm |

### Force sync

```bash
oc -n openshift-gitops annotate application iso-compliance-platform \
  argocd.argoproj.io/refresh=normal --overwrite
oc -n openshift-gitops annotate application llm-ai-platform \
  argocd.argoproj.io/refresh=normal --overwrite
```

---

## Building Images

The iso-api, iso-web, and iso-docgen images are built on-cluster via OpenShift BuildConfig.

```bash
# Build from local source (fast iteration)
cd apps/iso-api
oc start-build iso-api --from-dir=. --wait --follow

cd apps/iso-web
oc start-build iso-web --from-dir=. --wait --follow

cd services/docgen
oc start-build iso-docgen --from-dir=. --wait --follow

# Restart after build
oc rollout restart deployment/iso-api deployment/iso-web deployment/iso-docgen -n iso-platform
```

---

## Configuration

### Platform ConfigMap (`iso-app-config`)

Key settings in `gitops/overlays/ocp-sandbox3159/cluster-config.yaml`:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_HOST` | `postgresql` | in-cluster |
| `LLM_GATEWAY_URL` | OpenAI or RHOAI MaaS URL | |
| `MAAS_BASE_URL` | `https://maas.apps...` | Qwen3 endpoint base |
| `QWEN3_MODEL_URL` | full `/v1` endpoint | |
| `RHOAI_DASHBOARD_URL` | dashboard URL | |

### Playground models (`playground-models-config`)

`gitops/overlays/ocp-sandbox3159/playground-models-config.yaml` — edit `MODELS_CONFIG` JSON to add/remove models. No code change required.

### Doc-agent model tasks (`doc-agent-model-config`)

`deploy/openshift/base/model-config.yaml` — controls which LLM is used per task (PARSE/EXTRACT/TRANSLATE/GENERATE). Change to Ollama or OpenShift AI vLLM by editing `*_MODEL_URL`.

---

## Secrets Reference

| Secret name | Namespace | Keys | Purpose |
|-------------|-----------|------|---------|
| `openai-api-key` | iso-platform | `OPENAI_API_KEY` | OpenAI access |
| `iso-secrets` | iso-platform | `LLM_API_KEY`, `DATABASE_PASSWORD`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Core app secrets |
| `iso-compliance-gitops-repo` | openshift-gitops | `url`, `username`, `password` | ArgoCD GitHub access |

---

## RHOAI Setup

See [RHOAI_MAAS_GUARDRAILS.md](./RHOAI_MAAS_GUARDRAILS.md) for full MaaS + TrustyAI setup.

Quick reference:
```bash
# Apply TrustyAI + Guardrails to llm namespace
oc apply -f gitops/overlays/ocp-sandbox3159/llm-ai/ -n llm

# Apply playground models ConfigMap
oc apply -f gitops/overlays/ocp-sandbox3159/playground-models-config.yaml -n iso-platform

# Switch to Qwen3 for EXTRACT task (saves OpenAI cost)
oc patch configmap doc-agent-model-config -n iso-platform --type=merge -p '{
  "data": {
    "EXTRACT_MODEL_URL": "https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com/llm/qwen3-4b-instruct/v1",
    "EXTRACT_MODEL_NAME": "qwen3-4b-instruct"
  }
}'
oc rollout restart deployment/iso-docgen -n iso-platform
```

---

## Kubernetes (open-source) flavor

```bash
kubectl apply -f deploy/kubernetes/base/
# Optional: Ollama for on-cluster models
kubectl apply -f deploy/kubernetes/ollama/
kubectl exec -n iso-platform deploy/ollama -- ollama pull mistral
# Update model config to use Ollama
kubectl patch configmap doc-agent-model-config -n iso-platform --type=merge -p '{
  "data": {
    "EXTRACT_MODEL_URL": "http://ollama.iso-platform.svc.cluster.local:11434/v1",
    "EXTRACT_MODEL_NAME": "mistral"
  }
}'
```
