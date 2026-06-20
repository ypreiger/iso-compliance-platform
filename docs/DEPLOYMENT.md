# Deployment — dual flavor

## Summary

| | **openshift-rhoai** (primary) | **k8s-litellm** (maintained) |
|---|-------------------------------|------------------------------|
| Orchestration | OpenShift + GitOps (Argo CD) | Kubernetes (+ optional GitOps) |
| LLM gateway | RHOAI **MaaS** | **LiteLLM** |
| API shape | OpenAI `/v1` | OpenAI `/v1` |
| First test target | **Yes** | Parity smoke tests |

## openshift-rhoai (implement first)

### Prerequisites

- OpenShift 4.x cluster
- **OpenShift AI 3.4+** with **MaaS** / Connectivity Link
- GPU nodes (optional, for self-hosted models)
- Namespace e.g. `iso-platform`

### Bootstrap order

1. Install/verify RHOAI operator and `DataScienceCluster`
2. Configure **MaaS** gateway route (cluster `maas.apps.<domain>` or dedicated)
3. Register models:
   - Self-hosted: `LLMInferenceService` (vLLM / llm-d)
   - External (optional): `ExternalModel` CRs
4. Create **MaaSAuthPolicy** + API keys for `iso-api` service account
5. Deploy `infra/openshift-rhoai/` (namespace, secrets, app, optional passthrough gateway)
6. Set application env:
   ```bash
   LLM_GATEWAY_URL=https://<maas-or-iso-gateway>/v1
   LLM_API_KEY=<maas-token>
   ```

### Optional passthrough gateway

Same pattern as ragu-builder `openai-gateway`: nginx passthrough to MaaS origin so the app never holds raw MaaS URLs in multiple places. See `infra/openshift-rhoai/gateway/README.md`.

### Verification

```bash
curl -sk "$LLM_GATEWAY_URL/models" -H "Authorization: Bearer $LLM_API_KEY"
# chat/completions smoke test with model alias iso-mapper
```

## k8s-litellm (maintained parity)

### Prerequisites

- Any Kubernetes 1.28+
- LiteLLM deployment (see `infra/k8s-litellm/litellm/`)
- Ingress or Gateway API for `/v1`

### Bootstrap order

1. Deploy LiteLLM with `config.yaml` defining aliases: `iso-mapper`, `iso-report`, `iso-embed`
2. Point backends to your vLLM service or external provider keys (Kubernetes secrets)
3. Deploy app manifests from `infra/k8s-litellm/app/` with **same env var names** as OpenShift flavor
4. Run contract test suite (shared) against `$LLM_GATEWAY_URL`

### LiteLLM config sketch

```yaml
model_list:
  - model_name: iso-mapper
    litellm_params:
      model: openai/gpt-4o   # or vLLM openai base
      api_base: os.environ/VLLM_BASE
  - model_name: iso-embed
    litellm_params:
      model: openai/text-embedding-3-small
```

## Shared application env (both flavors)

| Variable | Description |
|----------|-------------|
| `LLM_GATEWAY_URL` | OpenAI-compatible base, must end with `/v1` |
| `LLM_API_KEY` | Gateway-issued bearer token |
| `LLM_MODEL_MAPPING` | Model alias for finding ↔ clause mapping |
| `LLM_MODEL_REPORT` | Model alias for DOCX narrative |
| `LLM_MODEL_EMBED` | Embedding model alias |
| `DATABASE_URL` | PostgreSQL |
| `OBJECT_STORAGE_*` | S3-compatible bucket for uploads/exports |

## CI recommendation

- **Flavor matrix job:** deploy manifests dry-run + run OpenAI contract tests against mock gateway
- **Nightly:** optional live test against dev OpenShift MaaS and dev LiteLLM

## DNS (GoDaddy / public access)

Use GoDaddy (or registrar) for DNS only:

- `iso.<domain>` → OpenShift Route or K8s Ingress
- LLM traffic stays **internal** to cluster; only the app API/UI is public
