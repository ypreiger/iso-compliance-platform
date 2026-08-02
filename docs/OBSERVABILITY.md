# Observability

The platform uses **one** Grafana operations dashboard. Full configuration, Prometheus scrape paths, PromQL sources, and GitHub links to YAML/JSON are in:

➡️ **[Grafana dashboard](./GRAFANA_DASHBOARD.md)**  
➡️ **Dashboard JSON:** [`docs/grafana/maas-token-metrics.json`](./grafana/maas-token-metrics.json)

## Quick reference

| Field | Value |
|-------|--------|
| **Title** | `MaaS Token Metrics Dashboard (with User/Model Filters)` |
| **UID** | `maas-token-metrics` |
| **Live URL** | https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com/d/maas-token-metrics |
| **GitOps CR** | [`gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml`](../gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml) |
| **JSON export** | [`docs/grafana/maas-token-metrics.json`](./grafana/maas-token-metrics.json) |

### Sections on the board

1. **Tokens per user / model** — MaaS `authorized_hits` + app `iso_app_model_tokens_total`
2. **vLLM cache** — prefix cache hit rate + KV cache usage % (in-cluster models)
3. **CPU & memory** by namespace / pod
4. **Network** rx/tx by namespace / pod

Use refresh **30s**. Details, scrape setup, and how to expose new models: [GRAFANA_DASHBOARD.md](./GRAFANA_DASHBOARD.md).
