# Red Hat OpenShift AI 3.5 demo (GA + Technology Preview)

Connected demo project: **`rhoai-demo`**. Dashboard:
https://rh-ai.apps.ocp.7hrxw.sandbox880.opentlc.com/

This overlay does not turn on bundled Models-as-a-Service
(`aigateway.modelsAsAService` stays **Removed**). The lab Kuadrant MaaS on
`maas-default-gateway` remains the gateway for gpt-oss-20b, BGE-M3, Whisper,
and the ISO playground.

## What you can demo

Select project **RHOAI 3.5 demo** unless noted.

| UI area | What is wired | Notes |
|---------|----------------|-------|
| **Projects** | Data Science project `rhoai-demo` | Full project (not model-serving-only) |
| **Connections** | S3 MinIO, URI to gpt-oss-20b (in-cluster + MaaS), BGE-M3, Whisper | Verify connection is a TP |
| **Pipelines** | DSPA `dspa` Ready | Sample pipeline enabled; AutoRAG/AutoML need this |
| **AutoRAG** (TP) | Pipeline server + `s3://rhoai-demo/autorag/docs` | Create an experiment pointing at that prefix |
| **AutoML** (TP) | Same pipeline server | Create from the AutoML tile |
| **Gen AI Studio / Playground** (TP) | OGXServer `ogx` (`rh`) → gpt-oss-20b + BGE-M3 | Also: lab Llama Stack playgrounds in `wksp-user1` / `wksp-user2` |
| **MCP catalog** (TP) | MCPServer `kubernetes` in this project; Kubernetes + Slack already in `lls-demo` | Catalog CM `gen-ai-aa-mcp-servers` |
| **MLflow / prompts** (TP) | Cluster MLflow in `redhat-ods-applications` | Global prompt namespace `rhoai-demo` |
| **Feature Store** (TP) | FeatureStore `iso-features` Ready | Feast project `iso_features` |
| **Evaluations / EvalHub** (TP) | Cluster `eval-hub-ui`; project CR `evalhub` | 3.5.1 has no namespaced EvalHub operand controller |
| **Workbenches** | Notebook `demo-workbench` (CPU) | Do not request the L40S — gpt-oss-20b owns it |
| **Model registry** | `rhoai-demo` in `rhoai-model-registries` Available | Plus default registry |
| **Model catalog / serving / MaaS** | llm ns: gpt-oss-20b, BGE-M3, Whisper, qwen3-guardrails | Bundled MaaS stays off |
| **Hardware profiles** | `default-profile`, `nvidia-l40s` | Node scheduling + GPU taint |
| **Distributed workloads / Kueue** | ClusterQueue + LocalQueue `default` | Training, Ray, Spark operators Managed |
| **Observe & monitor** | DSCI metrics/traces, TrustyAI in `llm` | Grafana MaaS dashboard |
| **Guardrails** | `GuardrailsOrchestrator` `qwen3-guardrails` | Wired into OGX `FMS_ORCHESTRATOR_URL` |
| **ISO app + playground** | `iso-platform` | Separate from the RHOAI dashboard demo project |

## GitOps

| Path | Role |
|------|------|
| `gitops/layers/00-openshift-ai/` | DSC, dashboard flags, GPU hardware profile, Kueue ClusterQueue |
| `gitops/overlays/ocp-sandbox3159/rhoai-demo/` | Demo project operands |
| `gitops/overlays/ocp-sandbox3159/rhoai-model-registry/` | Extra ModelRegistry instance |
| `gitops/overlays/ocp-sandbox3159/apps/rhoai-demo-app.yaml` | Argo CD Application |
| `gitops/overlays/ocp-sandbox3159/apps/rhoai-demo-registry-app.yaml` | Argo CD Application |

```bash
oc apply -f gitops/overlays/ocp-sandbox3159/apps/rhoai-demo-app.yaml
oc apply -f gitops/overlays/ocp-sandbox3159/apps/rhoai-demo-registry-app.yaml
./scripts/verify-openshift-ai.sh
./scripts/verify-rhoai-demo.sh
```

## AutoRAG experiment (UI)

1. Open **RHOAI 3.5 demo** → **AutoRAG**.
2. Object storage connection: **Demo object storage**.
3. Documents prefix: `autorag/docs/` (ISO 9001 / 14001 overviews already uploaded).
4. Evaluation file: `autorag/eval.jsonl`.
5. Generator: gpt-oss-20b URI connection. Embeddings: BGE-M3 URI connection.

## Known sandbox limits

- Single NVIDIA L40S. gpt-oss-20b is the GPU inference workload. Leave Qwen3 replicas at 0.
- Do **not** set `aigateway.modelsAsAService=Managed` (playground 401/429).
- Rotate the OpenAI key in MaaS if gpt-4o* chat returns 401 (pre-existing).
- EvalHub project CR is visible; job pods are created from the Evaluations UI, not from a missing operand controller.
- Dashboard `clusterDomains` may be cleared by the dashboard operator; re-apply `odh-dashboard-config` if in-cluster URI assets disappear from Gen AI Studio.

## References

- [OpenShift AI 3.5 TP features](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes)
- [Deploying an OGX server](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_ogx/deploying-ogx-server_rag)
- [Working with AutoRAG](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_autorag/index)
- Platform flags: [OPENSHIFT_AI.md](OPENSHIFT_AI.md)
