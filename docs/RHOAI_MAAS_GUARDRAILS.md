# RHOAI MaaS + Qwen3 + TrustyAI Guardrails Setup

> Playground operational behavior (tabs, STT, file analysis, guardrail modes, Whisper selection) is documented canonically in [`PLAYGROUND.md`](./PLAYGROUND.md).
> This document focuses on MaaS / TrustyAI / Guardrails platform setup only.

## Architecture

```
Browser → Playground (iso-platform)
                │  Bearer <SA token>
                ▼
    MaaS Gateway (maas.apps.../llm/qwen3-4b-instruct/v1)
                │
                ▼
    GuardrailsOrchestrator (llm namespace)
      ┌─── Input detector (HAP: hate/abuse/profanity)
      │
      ▼
    vLLM / Qwen3 4B Instruct 2507  (llm namespace, GPU)
      │
      ▼
    ┌─── Output detector
    │
    ▼
    Response → client

    TrustyAI Service (llm namespace)
      → logs all inferences
      → computes fairness metrics (SPD, DIR)
      → detects data drift
      → visible in RHOAI Dashboard → Trusty AI tab
```

---

## Components

### Qwen3 4B Instruct 2507
- **CRD**: `LLMInferenceService` (llm namespace)
- **Image**: `registry.redhat.io/rhaiis/vllm-cuda-rhel9:3.2.5`
- **Model**: `oci://quay.io/jharmison/models:qwen--qwen3-4b-instruct-2507-modelcar`
- **Context**: 131 072 tokens
- **GPU**: 1× NVIDIA L40 (gpu-memory-utilization=0.95)
- **MaaS URL**: `https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com/llm/qwen3-4b-instruct/v1`
- **Auth**: Bearer token (any OpenShift SA token — `system:authenticated` = free tier)

### MaaS Gateway
- Managed by ArgoCD app `models-as-a-service`
- Source: `https://github.com/opendatahub-io/models-as-a-service.git`
- Tier mapping (ConfigMap `tier-to-group-mapping` in `maas-api`):
  - `free` → `system:authenticated` (all SAs)
  - `premium` → `tier-premium-users`
  - `enterprise` → `enterprise-group`, `admin-group`

### TrustyAI Service
- **CRD**: `TrustyAIService` (llm namespace)
- **Storage**: PVC 1Gi (inference logs in CSV)
- **Metrics schedule**: every 5 seconds
- **Visible**: RHOAI Dashboard → Project `llm` → Trusty AI

### GuardrailsOrchestrator
- **CRD**: `GuardrailsOrchestrator` (llm namespace)
- **autoConfig**: auto-discovers `qwen3-4b-instruct` LLMInferenceService
- **Built-in detectors**: HAP (hate, abuse, profanity)
- **Gateway**: enabled — sidecar gateway at port 8090
- **Guardrailed endpoint** (internal): `http://qwen3-guardrails-guardrails-gateway.llm.svc.cluster.local:8090`

### AI Playground
- Runtime behavior and options: see [`PLAYGROUND.md`](./PLAYGROUND.md)
- This file only tracks platform prerequisites for MaaS/TrustyAI/Guardrails

---

## GitOps Structure

```
gitops/
  overlays/
    ocp-sandbox3159/
      llm-ai/                        ← NEW: deployed to llm namespace
        kustomization.yaml
        namespace-labels.yaml        ← opendatahub.io/dashboard: "true"
        trustyai-service.yaml        ← TrustyAIService CR
        guardrails-orchestrator.yaml ← GuardrailsOrchestrator CR
        rbac.yaml                    ← SA for playground MaaS access
      apps/
        llm-ai-app.yaml              ← ArgoCD Application CR
      cluster-config.yaml            ← QWEN3_MODEL_URL, GUARDRAILS_ENDPOINT added
  layers/
    03-application/
      playground.yaml                ← NEW: Playground deployment + ConfigMap + Route
```

### ArgoCD Applications

| App | Source path | Namespace | Status |
|-----|------------|-----------|--------|
| `iso-compliance-platform` | `gitops/overlays/ocp-sandbox3159` | iso-platform | Synced |
| `llm-ai-platform` | `gitops/overlays/ocp-sandbox3159/llm-ai` | llm | Synced after bootstrap |

---

## Deployment / Bootstrap Steps

### First-time setup (run once)
```bash
# 1. Apply the llm-ai ArgoCD Application
oc apply -f gitops/overlays/ocp-sandbox3159/apps/llm-ai-app.yaml -n openshift-gitops

# 2. Sync both apps
oc -n openshift-gitops patch application iso-compliance-platform \
  --type merge -p '{"operation":{"sync":{}}}'
oc -n openshift-gitops patch application llm-ai-platform \
  --type merge -p '{"operation":{"sync":{}}}'
```

### After GuardrailsOrchestrator is Ready, update the endpoint:
```bash
# Find the guardrails gateway service name
oc get svc -n llm | grep guardrails

# Update cluster-config (in gitops) with the internal guardrails endpoint
# GUARDRAILS_ENDPOINT: "http://qwen3-guardrails-guardrails-gateway.llm.svc.cluster.local:8090"
# Then commit + push → ArgoCD auto-syncs
```

---

## RHOAI Dashboard

URL: `https://rhods-dashboard-redhat-ods-applications.apps.ocp.8mkwb.sandbox3159.opentlc.com`

After the `llm-ai-platform` ArgoCD app syncs:
- **Projects**: `llm` namespace appears as a DataScienceProject
- **Model Serving**: `Qwen3 4B Instruct 2507` appears with its MaaS URL + "Try" playground
- **Trusty AI**: TrustyAI metrics and drift charts visible
- **Guardrails**: GuardrailsOrchestrator status visible under Trusty AI section

---

## Testing

```bash
# Get a token
TOKEN=$(oc create token default -n iso-platform)

# Test Qwen3 via MaaS
curl -sk https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com/llm/qwen3-4b-instruct/v1/models \
  -H "Authorization: Bearer $TOKEN"

# Test chat completion
curl -sk https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com/llm/qwen3-4b-instruct/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-4b-instruct","messages":[{"role":"user","content":"What is ISO 9001?"}],"max_tokens":100}'

# Test playground health
curl -sk https://playground-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com/health
```

---

## Switching Models

To change which model a task uses (doc agents, playground, etc.):
```bash
# Example: switch playground to use guardrails endpoint
oc patch configmap iso-app-config -n iso-platform --type=merge -p '{
  "data": {
    "GUARDRAILS_ENDPOINT": "http://qwen3-guardrails-guardrails-gateway.llm.svc.cluster.local:8090"
  }
}'
oc rollout restart deployment/playground -n iso-platform

# Example: switch EXTRACT to Qwen3 (saves OpenAI cost)
oc patch configmap iso-app-config -n iso-platform --type=merge -p '{
  "data": {
    "EXTRACT_MODEL_URL": "https://maas.apps.ocp.8mkwb.sandbox3159.opentlc.com/llm/qwen3-4b-instruct/v1",
    "EXTRACT_MODEL_NAME": "qwen3-4b-instruct"
  }
}'
oc rollout restart deployment/iso-doc-parse-rag -n iso-platform
```

---

_See also: [ARCHITECTURE.md](./ARCHITECTURE.md) | [PLAYGROUND.md](./PLAYGROUND.md)_
