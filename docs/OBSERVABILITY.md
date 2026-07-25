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

### What it shows

1. **Tokens by user / model** (selected Grafana time range)
   - **MaaS gateway**: Kuadrant/Limitador `authorized_hits`
   - **Application calls** (in-cluster): `iso_app_model_tokens_total` — includes **BGE-M3** on ISO upload / translate / auto-mapping (`user=iso-api`)
   - Filters: **User**, **Model**
   - Panels **Top models by tokens** and **Detailed metrics** merge both sources so `bge-m3` appears alongside MaaS models

2. **CPU & memory** for selected namespaces  
3. **Network** rx/tx by namespace and pod  

### How BGE-M3 shows up

| Source | Metric | User label | When |
|--------|--------|------------|------|
| Admin ISO upload / translate (RAG index) | `iso_app_model_tokens_total{model="bge-m3",task="embed_index"}` | `iso-api` | Always (in-cluster) |
| Auto mapping (query embed) | `…{task="embed_query"}` | `iso-api` | When vector RAG runs |
| Traffic via MaaS `/llm/bge-m3/v1` | `authorized_hits{model="bge-m3"}` | SA name | Only if called through gateway |

In the dashboard: set **Model = bge-m3** and/or **User = iso-api** (or All).

### Application scrape targets

`gitops/layers/03-application/iso-app-model-servicemonitors.yaml` scrapes `/metrics` on:

- `iso-api-orchestrator`
- `iso-doc-parse-rag`
- `iso-doc-gen`

Series: `iso_app_model_requests_total`, `iso_app_model_tokens_total`, `iso_app_model_latency_seconds_*`.

### Deploy / sync

```bash
oc -n openshift-gitops annotate application llm-ai-platform \
  argocd.argoproj.io/refresh=hard --overwrite
```
