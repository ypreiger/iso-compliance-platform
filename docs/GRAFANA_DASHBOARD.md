# Grafana dashboard

This document is the full reference for the platform’s **single** Grafana operations dashboard: tokens per user / model, vLLM prefix & KV cache, namespace CPU/RAM, and network. Every deployable artifact lives in this GitHub repository.

| | |
|---|---|
| **Live URL** | https://grafana-route-grafana.apps.ocp.7hrxw.sandbox880.opentlc.com/d/maas-token-metrics |
| **Title** | `MaaS Token Metrics Dashboard (with User/Model Filters)` |
| **UID** | `maas-token-metrics` |
| **Cluster CR** | `GrafanaDashboard/maas-token-metrics` in namespace `grafana` |
| **Argo CD app** | `llm-ai-platform` |

---

## Artifacts on GitHub (source of truth)

All links point at `main` on [ypreiger/iso-compliance-platform](https://github.com/ypreiger/iso-compliance-platform).

| Artifact | What it is | GitHub |
|----------|------------|--------|
| **Dashboard JSON** (portable export) | Full Grafana dashboard definition (panels, variables, PromQL) | [`docs/grafana/maas-token-metrics.json`](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/maas-token-metrics.json) |
| **GrafanaDashboard CR (YAML)** | OpenShift / Grafana Operator manifest (embeds the same JSON under `spec.json`) | [`gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml) |
| **Kustomize include** | Wires the CR into the `llm-ai` overlay | [`gitops/overlays/ocp-sandbox3159/llm-ai/kustomization.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/kustomization.yaml) |
| **App ServiceMonitors** | Scrapes `/metrics` from iso-api / docgen | [`gitops/layers/03-application/iso-app-model-servicemonitors.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/layers/03-application/iso-app-model-servicemonitors.yaml) |
| **LLM ServiceMonitors** | Scrapes vLLM / BGE-M3 `/metrics` in `llm` | [`gitops/overlays/ocp-sandbox3159/llm-ai/llm-servicemonitors.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/llm-servicemonitors.yaml) |
| **BGE-M3 MaaS HTTPRoute** | Puts embeddings on the gateway so Limitador emits `authorized_hits` | [`gitops/overlays/ocp-sandbox3159/llm-ai/bge-m3-external-model.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/bge-m3-external-model.yaml) |
| **App metrics emitter (iso-api)** | Prometheus counters/histograms for every chat/embed call | [`apps/iso-api/app/observability/model_metrics.py`](https://github.com/ypreiger/iso-compliance-platform/blob/main/apps/iso-api/app/observability/model_metrics.py) |
| **App metrics emitter (docgen)** | Same series from the docgen / parse agents | [`services/docgen/app/model_metrics.py`](https://github.com/ypreiger/iso-compliance-platform/blob/main/services/docgen/app/model_metrics.py) |
| **Folder index** | Short pointer to JSON + this guide | [`docs/grafana/README.md`](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/README.md) |

**JSON vs YAML**

- Edit / review panels in the standalone JSON: [`docs/grafana/maas-token-metrics.json`](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/maas-token-metrics.json).
- Deploy via the Grafana Operator CR: [`maas-token-metrics-dashboard.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml) (`spec.json` must stay in sync with the JSON file).
- After changing either side, re-sync both (see [Keep JSON and YAML in sync](#keep-json-and-yaml-in-sync)).

---

## What the dashboard shows

Scroll order on the live board:

### 1. MaaS tokens (user / model / time range)

| Panel group | Purpose |
|-------------|---------|
| Stats | Total tokens (range), active users, active models, lifetime counter |
| Time series | Token rate by **user**, token rate by **model** |
| Bar gauges | Top users / top models for the selected range |
| Table | Detailed tokens per **user × model × tier** |

**Data sources (merged in PromQL)**

| Source | Metric | Labels used | When it increments |
|--------|--------|-------------|--------------------|
| MaaS gateway (Kuadrant / Limitador) | `authorized_hits` | `user`, `model`, `tier` | Every authorized request through `https://maas.apps…/llm/<model>/v1` (includes SaaS externals such as `gpt-4o`) |
| Application (in-cluster) | `iso_app_model_tokens_total` | `user`, `model`, `token_type`, `task`, `service` | iso-api / docgen model calls (chat, translate, **BGE-M3** embed) even when not via MaaS |

App series are joined with `label_replace(..., "user", "iso-api", …)` and `tier="application"` so they appear next to gateway rows in the same table.

### 2. External / MaaS model tokens & cache (vLLM)

Visible for **vLLM-backed** in-cluster models (for example `gpt-oss-20b`):

| Panel | Metric(s) |
|-------|-----------|
| Prompt tokens (range) | `vllm:prompt_tokens_total` (or `kserve_vllm:prompt_tokens_total`) |
| Generation tokens (range) | `vllm:generation_tokens_total` |
| Prefix cache hit rate | `prefix_cache_hits_total / prefix_cache_queries_total` |
| KV cache usage % | `vllm:kv_cache_usage_perc` |
| Rates by model | Same series, `sum/max by (model_name)` |

Filter with the dashboard **Model** variable (`model_name=~"$model"`).

**Limits**

- Gateway **token** counts cover all MaaS routes (including hosted SaaS).
- **Prefix / KV cache** panels exist only for models that expose vLLM Prometheus metrics in this cluster. SaaS APIs (for example OpenAI `gpt-4o`) do not publish those series here.

### 3. Namespace CPU & memory

`container_cpu_*` / `container_memory_working_set_bytes` filtered by the **Namespace** variable (`iso-platform`, `llm`, …).

### 4. Network

`container_network_receive_bytes_total` / `container_network_transmit_bytes_total` by namespace and pod.

---

## Dashboard variables (filters)

Defined in the JSON under `templating.list` ([file](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/maas-token-metrics.json)):

| Variable | Label | Query / values | Effect |
|----------|-------|----------------|--------|
| `user` | User | `label_values({__name__=~"authorized_hits\|iso_app_model_tokens_total"}, user)` | Restricts token panels |
| `model` | Model | `label_values({__name__=~"authorized_hits\|iso_app_model_tokens_total",model!=""}, model)` | Restricts token + vLLM panels (`model` / `model_name`) |
| `namespace` | Namespace | `iso-platform`, `llm`, `kuadrant-system`, `maas-api`, `grafana` | Restricts CPU / memory / network |

**Recommended UI settings**

- Refresh: **30s** (not 5s — aggressive refresh can hang Grafana’s SQLite backend).
- Time range: `now-24h` default; widen for historical token totals.
- Example: **Model = bge-m3**, **User = iso-api** to isolate application embeddings.

---

## Datasource

Panels target the cluster Thanos / Prometheus datasource:

| Field | Value |
|-------|--------|
| Grafana datasource UID | `5b4d84cc-548e-4c40-b6b1-fe98a25ede58` |
| Typical backing | OpenShift user-workload Prometheus + Thanos querier |

If you import the JSON into another Grafana, remap this UID to your Prometheus datasource before saving.

---

## How metrics reach Prometheus

```text
┌──────────────────────────────┐     scrape /metrics      ┌─────────────────────────────┐
│ MaaS HTTPRoute → Limitador   │ ───────────────────────► │ authorized_hits             │
│ (kuadrant-system)            │   PodMonitor / SM        │ {user, model, tier}         │
└──────────────────────────────┘                          └──────────────┬──────────────┘
                                                                         │
┌──────────────────────────────┐     scrape /metrics      ┌──────────────▼──────────────┐
│ iso-api / iso-docgen         │ ───────────────────────► │ iso_app_model_*             │
│ ServiceMonitors (iso-platform)│                         │ {user, model, task, …}      │
└──────────────────────────────┘                          │                             │
                                                          │   Grafana PromQL merge      │
┌──────────────────────────────┐     scrape /metrics      │                             │
│ vLLM / BGE pods (llm)        │ ───────────────────────► │ vllm:*  +  bge_m3_*         │
│ llm-servicemonitors.yaml     │                          │ prefix_cache_*, kv_cache_*  │
└──────────────────────────────┘                          └─────────────────────────────┘
```

### 1. MaaS gateway tokens (`authorized_hits`)

Emitted by **Limitador** when a request is authorized on a MaaS `HTTPRoute` (TokenRateLimit / Auth policies).

| Item | Detail |
|------|--------|
| Scrape | Cluster `PodMonitor` / `ServiceMonitor` in `kuadrant-system` (for example `kuadrant-limitador-monitor`, `limitador-metrics`) — managed with Kuadrant / MaaS, not duplicated in this repo |
| Series | `authorized_hits{user, model, tier, limitador_namespace, …}` |
| How to get a model on the board | Expose it via MaaS `HTTPRoute` on `maas-default-gateway` (example: [bge-m3-external-model.yaml](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/bge-m3-external-model.yaml)) and call `https://maas.apps.<cluster>/llm/<model>/v1/...` with a valid SA / user token |

### 2. Application model metrics (`iso_app_model_*`)

| Item | Detail |
|------|--------|
| Emitters | [`apps/iso-api/app/observability/model_metrics.py`](https://github.com/ypreiger/iso-compliance-platform/blob/main/apps/iso-api/app/observability/model_metrics.py), [`services/docgen/app/model_metrics.py`](https://github.com/ypreiger/iso-compliance-platform/blob/main/services/docgen/app/model_metrics.py) |
| HTTP path | `GET /metrics` on each service |
| Scrape YAML | [`iso-app-model-servicemonitors.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/layers/03-application/iso-app-model-servicemonitors.yaml) |
| Targets | `iso-api-orchestrator`, `iso-doc-parse-rag`, `iso-doc-gen` |
| Series | `iso_app_model_requests_total`, `iso_app_model_tokens_total{token_type=prompt\|completion\|total}`, `iso_app_model_latency_seconds_*` |
| User label | Default `iso-api` via env `ISO_APP_METRICS_USER` |

### 3. vLLM / embedding engine metrics

| Item | Detail |
|------|--------|
| Scrape YAML | [`llm-servicemonitors.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/llm-servicemonitors.yaml) |
| Targets | `gpt-oss-20b`, `qwen3-4b-instruct` (HTTPS `/metrics`), `bge-m3` (HTTP `/metrics`) |
| Cache-related series | `vllm:prefix_cache_hits_total`, `vllm:prefix_cache_queries_total`, `vllm:kv_cache_usage_perc` (also `kserve_vllm:*` aliases) |
| Token series | `vllm:prompt_tokens_total`, `vllm:generation_tokens_total` |

### Verify scrape (cluster)

```bash
# User-workload Prometheus should list these names
oc exec -n openshift-user-workload-monitoring prometheus-user-workload-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=authorized_hits' | head -c 400

oc exec -n openshift-user-workload-monitoring prometheus-user-workload-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=iso_app_model_tokens_total' | head -c 400

oc exec -n openshift-user-workload-monitoring prometheus-user-workload-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=vllm:prefix_cache_hits_total' | head -c 400
```

---

## Configure / change the dashboard

### Option A — GitOps (preferred)

1. Edit the portable JSON: [`docs/grafana/maas-token-metrics.json`](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/maas-token-metrics.json).
2. Copy the JSON into `spec.json` of [`maas-token-metrics-dashboard.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml) (4-space indent under `json: |-`), **or** run the sync helper below.
3. Commit + push to `main`.
4. Sync Argo:

```bash
oc -n openshift-gitops annotate application llm-ai-platform \
  argocd.argoproj.io/refresh=hard --overwrite
# optional immediate apply
oc apply -f gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml
```

5. Confirm operator sync:

```bash
oc get grafanadashboard maas-token-metrics -n grafana \
  -o jsonpath='{.status.conditions[0].message}{"\n"}{.status.lastResync}{"\n"}'
```

6. Hard-refresh the browser on the live URL (avoid stale cached dashboard JSON).

### Option B — Grafana UI then export back to Git

1. Edit panels in the UI.
2. **Share → Export → Save to file**.
3. Replace [`docs/grafana/maas-token-metrics.json`](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/maas-token-metrics.json).
4. Sync into the YAML CR and push (Option A steps 2–5) so GitOps does not overwrite your UI edits on the next sync.

### Keep JSON and YAML in sync

```bash
# YAML (CR) → docs/grafana JSON export
python3 - <<'PY'
import json, re
from pathlib import Path
yaml = Path("gitops/overlays/ocp-sandbox3159/llm-ai/maas-token-metrics-dashboard.yaml").read_text()
m = re.search(r"json: \|-\n((?:    .*\n)+)", yaml)
raw = "\n".join(line[4:] for line in m.group(1).splitlines())
Path("docs/grafana/maas-token-metrics.json").write_text(json.dumps(json.loads(raw), indent=2) + "\n")
print("updated docs/grafana/maas-token-metrics.json")
PY
```

Bump `"version"` inside the JSON when publishing intentional panel changes so Grafana Operator replaces the stored dashboard.

### Import JSON into another Grafana

1. Download [`maas-token-metrics.json`](https://github.com/ypreiger/iso-compliance-platform/blob/main/docs/grafana/maas-token-metrics.json) (Raw).
2. Grafana → **Dashboards → New → Import**.
3. Remap datasource UID `5b4d84cc-548e-4c40-b6b1-fe98a25ede58` to your Prometheus/Thanos datasource.
4. Ensure the metrics in [How metrics reach Prometheus](#how-metrics-reach-prometheus) are scraped in that cluster.

---

## Exposing a new model so it appears on the dashboard

### Tokens via MaaS (user / model)

1. Deploy the model Service in `llm` (or appropriate namespace).
2. Add an `HTTPRoute` parented to `maas-default-gateway` with path `/llm/<model-id>/v1` (mirror [bge-m3-external-model.yaml](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/bge-m3-external-model.yaml)).
3. Ensure Kuadrant Auth + TokenRateLimit policies attach (platform MaaS defaults).
4. Call the gateway with a Bearer token; Limitador increments `authorized_hits{model="<model-id>", user="..."}`.
5. Refresh Grafana; select the new model in the **Model** filter.

### Cache / vLLM engine panels

1. Model must run vLLM (or KServe vLLM) with `/metrics` enabled.
2. Add a `ServiceMonitor` entry in [`llm-servicemonitors.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/overlays/ocp-sandbox3159/llm-ai/llm-servicemonitors.yaml).
3. Confirm `vllm:prefix_cache_*` and `vllm:kv_cache_usage_perc` appear in user-workload Prometheus.
4. Use **Model** filter matching `model_name` (for example `gpt-oss-20b`).

### Application-only tokens (no MaaS)

1. Instrument calls with `track_model_call` / `record_model_call` in iso-api or docgen.
2. Keep ServiceMonitors in [`iso-app-model-servicemonitors.yaml`](https://github.com/ypreiger/iso-compliance-platform/blob/main/gitops/layers/03-application/iso-app-model-servicemonitors.yaml).
3. Series show as `user=iso-api` (or `ISO_APP_METRICS_USER`) in the merged token panels.

---

## Operational tips

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| 503 / blank timeouts | Grafana pod hung (often `refresh=5s`) | Force-delete Grafana pod; set refresh to **30s** |
| Dashboard missing new panels | Argo on old revision / browser cache | Hard-refresh Argo `llm-ai-platform`; hard-refresh browser |
| No `authorized_hits` for a model | Traffic not via MaaS HTTPRoute | Use `/llm/<model>/v1` on the gateway, not only in-cluster Service URL |
| Cache row empty | Not a vLLM model, or SM missing | Check `llm-servicemonitors.yaml` + Prometheus series |
| BGE missing from token table | Only in-cluster embed, or no MaaS calls | Filter **User = iso-api** / **Model = bge-m3**; optional MaaS route for gateway hits |

---

## Related docs

- Short summary: [`docs/OBSERVABILITY.md`](./OBSERVABILITY.md)
- RAG / BGE wiring: [`docs/RAG_VECTOR_EMBEDDINGS.md`](./RAG_VECTOR_EMBEDDINGS.md)
- MaaS / guardrails: [`docs/RHOAI_MAAS_GUARDRAILS.md`](./RHOAI_MAAS_GUARDRAILS.md)
- Deploy / GitOps apps: [`docs/DEPLOY.md`](./DEPLOY.md)
