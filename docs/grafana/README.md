# Grafana artifacts

Portable dashboard export and pointers for the platform observability board.

| File | Description |
|------|-------------|
| [`maas-token-metrics.json`](./maas-token-metrics.json) | Full Grafana dashboard JSON (UID `maas-token-metrics`) |
| [`../GRAFANA_DASHBOARD.md`](../GRAFANA_DASHBOARD.md) | **Complete guide**: tokens per user/model, cache, Prometheus scrape, GitOps |

**Deployed CR (embeds the same JSON):**  
[`gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml`](../../gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml)

**Live:** https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com/d/maas-token-metrics
