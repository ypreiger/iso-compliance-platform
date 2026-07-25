# Observability

## Single Grafana dashboard

The platform maintains **one** Grafana dashboard for day-to-day operations:

| Field | Value |
|-------|--------|
| **Title** | `MaaS Token Metrics Dashboard (with User/Model Filters)` |
| **UID** | `maas-token-metrics` |
| **GitOps** | `gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml` |
| **CR** | `GrafanaDashboard/maas-token-metrics` in namespace `grafana` |
| **URL** | https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com |

Search Grafana for that exact title (or open by UID `maas-token-metrics`).

### What it shows

1. **MaaS tokens** (Kuadrant/Limitador `authorized_hits`)
   - Filters: **User**, **Model**, Grafana time range
   - Totals for the selected range, rates by user/model, top users/models
   - Detailed table: tokens per user × model × tier for the selected range

2. **CPU & memory** for selected namespaces
   - Namespace and pod CPU (`container_cpu_usage_seconds_total`)
   - Namespace and pod memory working set (`container_memory_working_set_bytes`)

3. **Network**
   - Receive/transmit bytes by namespace and pod
   - (`container_network_receive_bytes_total` / `container_network_transmit_bytes_total`)

### Namespace filter

Default focus: `iso-platform`, `llm`.  
Also available: `kuadrant-system`, `maas-api`, `grafana`.

### Datasource

Grafana datasource **Prometheus** (`uid: 5b4d84cc-548e-4c40-b6b1-fe98a25ede58`) → OpenShift Thanos querier, which exposes both cluster resource metrics and user-workload MaaS metrics.

## What was removed

Older overlapping dashboards are **no longer** shipped by this repo’s GitOps overlay:

- `LLM Observability - ISO Platform` (`llm-observability`)
- `MaaS Token Metrics … + Whisper STT` (`maas-lab-whisper`)

Whisper STT metrics remain available via Prometheus if needed; they are not part of the single ops dashboard.

An upstream Kuadrant sample dashboard may still exist in the shared `grafana` Argo app (`MaaS Token Metrics (upstream / Kuadrant)`). It is **not** managed by this repository; use `maas-token-metrics` as the source of truth.

## Deploy / sync

```bash
# After merge to main
oc -n openshift-gitops patch application llm-ai-platform \
  --type merge -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{}}}' \
  2>/dev/null || argocd app sync llm-ai-platform

# Or apply the CR directly (GitOps will reconcile)
oc apply -f gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml
```

## Related ServiceMonitors

`gitops/overlays/ocp-sandbox3159/llm-ai/llm-servicemonitors.yaml` scrapes LLM inference services for latency/GPU metrics. Those series can be added to this dashboard later if needed; token + resource + network coverage is the current requirement.

## BGE-M3 via MaaS

BGE-M3 is exposed on the MaaS gateway (same pattern as Whisper):

| Item | Value |
|------|--------|
| HTTPRoute | `llm/bge-m3-maas-route` |
| Path | `/llm/bge-m3/v1` → Service `bge-m3:8080` |
| App config | `LLM_EMBED_URL=…/llm/bge-m3` |
| Token metrics | `authorized_hits{model="bge-m3", …}` (user-workload Prometheus) |
| Pod metrics | `bge_m3_requests_total`, `bge_m3_tokens_total`, `bge_m3_request_latency_seconds` via ServiceMonitor `bge-m3-metrics` |

Smoke test:

```bash
TOKEN=$(oc create token default -n iso-platform --audience=maas-default-gateway-sa --duration=10m)
curl -sk -H "Authorization: Bearer $TOKEN" \
  https://maas.apps.ocp.7hrxw.sandbox880.opentlc.com/llm/bge-m3/v1/models
curl -sk -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":"hello","model":"bge-m3"}' \
  https://maas.apps.ocp.7hrxw.sandbox880.opentlc.com/llm/bge-m3/v1/embeddings
```
