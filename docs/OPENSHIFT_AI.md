# OpenShift AI 3.5 GA (upgrade from Early Access)

This cluster previously ran **Red Hat OpenShift AI 3.5.0-ea.1** on the legacy
`beta` channel. Catalog GA is **3.5.0** on `stable-3.x` (default), `stable-3.5`,
and `eus-3.5`.

GitOps source of truth: `gitops/layers/00-openshift-ai/`  
Argo CD Application: `iso-00-openshift-ai`

## Current target

| Item | Value |
|------|--------|
| Operator package | `rhods-operator` |
| Channel | `stable-3.x` (latest 3.x GA, currently 3.5.0) |
| Install plan | Automatic |
| OpenShift | 4.20 (sandbox) |
| GPU | NVIDIA L40S worker (`nvidia.com/gpu.present=true`) |

## Why the cutover is not a normal OLM upgrade

Early Access CSVs (`rhods-operator.3.5.0-ea.1`) do **not** `replace` / `skipRange`
into `rhods-operator.3.5.0`. After switching the Subscription channel, OLM reports
`AtLatestKnown` on the EA CSV. The sandbox cutover is:

1. Point the Subscription at `stable-3.x` and remove `startingCSV`.
2. Delete the EA `ClusterServiceVersion` (CRDs and CRs remain).
3. OLM installs `rhods-operator.3.5.0`.

Red Hat does not support EA→GA as a production upgrade path; this sandbox
follows that operational pattern because the environment was installed from
`beta` by the RHPDS lab bootstrap (`openshift-ai-operator` Application).

The lab Applications `openshift-ai` and `openshift-ai-operator` (from
`rhpds/private-llmaas-multitenant`) still exist. `openshift-ai` auto-sync /
self-heal is **disabled** and ignore-differences cover DSC / DSCI / dashboard
so this repo can own those CRs.

## Enablement map

### DataScienceCluster (`default-dsc`)

| Component | State | Why |
|-----------|--------|-----|
| `dashboard` | Managed | OpenShift AI UI |
| `aigateway` | Managed | AI Gateway, batch gateway, MaaS |
| `aigateway.batchGateway` | Managed | Batch inference gateway |
| `aigateway.modelsAsAService` | **Removed** | Conflicts with existing Kuadrant MaaS on `maas-default-gateway` (playground 401). Keep the lab `maas-api` stack. |
| `kserve` | Managed | Model serving / `LLMInferenceService` |
| `kserve.nim` | Managed | NVIDIA NIM integration |
| `kserve.modelsAsService` | Removed | Deprecated; cannot re-enable. Do **not** turn on `aigateway.modelsAsAService` on this sandbox (shared `maas-default-gateway`). |
| `kserve.wva` | Managed | Workload Variant Autoscaler (llm-d) |
| `kserve.modelCache` | Managed | Local model cache on GPU nodes (50Gi) |
| `ogx` | Managed | **Agent orchestration** (replaces Llama Stack) |
| `mcplifecycleoperator` | Managed | MCP server lifecycle for agents |
| `llamastackoperator` | Removed | Renamed to OGX in 3.5 |
| `aipipelines` | Managed | Pipelines; required for AutoRAG |
| `feastoperator` | Managed | Feature Store |
| `mlflowoperator` | Managed | Experiment / prompt registry |
| `modelregistry` | Managed | Model Registry (`rhoai-model-registries`) |
| `ray` | Managed | Distributed workloads |
| `sparkoperator` | Managed | Spark workloads |
| `trainer` | Managed | Kubeflow Trainer |
| `trainingoperator` | Managed | Training jobs |
| `trustyai` | Managed | EvalHub, guardrails, LMEval (`permitOnline: allow`) |
| `workbenches` | Managed | Jupyter / workbenches |
| `kueue` | **Unmanaged** | 3.5 rejects `Managed`; RHBOK operator owns Kueue |

### Companion operators (not part of the RHOAI CSV)

| Operator | Channel | Namespace | Operand CR |
|----------|---------|-----------|------------|
| Red Hat build of Kueue | `stable-v1.4` | `openshift-kueue-operator` | `Kueue/cluster` (`kueue.openshift.io`) |
| Leader Worker Set | `stable-v1.0` | `openshift-lws-operator` | `LeaderWorkerSetOperator/cluster` |
| JobSet | `stable-v1.0` | `openshift-jobset-operator` | `JobSetOperator/cluster` |
| Cluster Observability | `stable` | `openshift-cluster-observability-operator` | (DSCI metrics stack) |
| OpenTelemetry | `stable` | `openshift-opentelemetry-operator` | (DSCI traces) |
| Tempo | `stable` | `openshift-tempo-operator` | (DSCI traces backend) |

LWS (OwnNamespace OperatorGroup) is required for Wide Expert Parallelism with
`LLMInferenceService`. JobSet is required by Kubeflow Trainer and by Kueue's
`JobSet` integration. DSCI metrics/traces need Cluster Observability,
OpenTelemetry, and Tempo operators.

Kueue frameworks enable every supported job type except `JaxJob` (RHBOK 1.4 maps
it to an empty framework string and the controller refuses to start).

`llamastackoperator` is `Removed` in spec (OGX replaces it). A leftover Llama Stack
operator Deployment from the EA install may remain until the operator finishes cleanup.

### OdhDashboardConfig (`odh-dashboard-config`)

Enabled (true) unless noted. `disable*` flags are **false** so the matching UI is shown.

| Flag | Purpose |
|------|---------|
| `genAiStudio` | Gen AI studio + playground (needs OGX) |
| `autorag` | AutoRAG optimization UI |
| `automl` | AutoML pipelines |
| `agentsCatalog` / `agentOps` / `agentConfigManagement` | Agent catalog, ops, save/load |
| `aiAssetCustomEndpoints` | Custom playground endpoints |
| `genAiStudioConfig.aiAssetCustomEndpoints.externalProviders` | External LLM providers |
| `promptManagement` | MLflow prompt library in playground |
| `mcpCatalog` / `mcpRegistry` | MCP server catalog and registry |
| `toolCalling` | Tool calling in model catalog |
| `guardrails` / `genAiTracing` | Guardrails and playground tracing |
| `modelAsService` | MaaS tab |
| `vLLMDeploymentOnMaaS` | vLLM-on-MaaS deploy path |
| `llmGatewayField` | Gateway picker in deploy wizard |
| `externalVectorStores` | Vector stores for RAG / playground |
| `deploymentWizardYAMLViewer` | YAML preview in deploy wizard |
| `disableLMEval=false` | EvalHub |
| `disableKueue=false` | Kueue hardware profiles |
| `disableLLMd=false` | Distributed inference with llm-d |
| `disableFeatureStore=false` | Feature Store nav |
| `observabilityDashboard` | Observe & monitor |
| `projectRBAC` | Project Roles tab |
| `trainingJobs` | Training jobs nav |

All 3.5 dashboard CRD flags listed above are set in
`gitops/layers/00-openshift-ai/dsc/odh-dashboard-config.yaml`.

### DSCInitialization monitoring

`default-dsci` keeps `applicationsNamespace: redhat-ods-applications` and
`monitoring.namespace: redhat-ods-monitoring` (immutable). Metrics PVC 20Gi /
7d retention and traces (Tempo PV 10Gi, sample ratio 0.2) are enabled so the
built-in observability stack can start.

## Apply / verify

```bash
# After merge to main, register (or refresh) the Argo app
oc apply -f gitops/overlays/ocp-sandbox3159/apps/iso-00-openshift-ai.yaml

# Direct apply (cluster-admin)
oc apply -k gitops/layers/00-openshift-ai

# Verify
./scripts/verify-openshift-ai.sh
```

Do **not** re-enable self-heal on the lab `openshift-ai` Application or it will
fight `default-dsc`.

## Sandbox coexistence with lab MaaS

This cluster already fronts models through Kuadrant on `maas-default-gateway`
(AuthPolicy `gateway-auth-policy`, SA audience `maas-default-gateway-sa`).
OpenShift AI 3.5 `aigateway.modelsAsAService=Managed` installs a second stack
(`maas-controller`, AuthPolicy `maas-gateway-auth`, TokenRateLimitPolicy
`gateway-default-deny` with limit 0) on that same Gateway. Symptoms:

- Playground `/chat` → `401` (API-key / default-audience TokenReview)
- Then `429 Too Many Requests` (deny-all token rate limit)

Keep `modelsAsAService: Removed`. If leftovers return, delete
`tokenratelimitpolicies.kuadrant.io/gateway-default-deny` in `openshift-ingress`
and `configs.maas.opendatahub.io/default`, and scale
`deployment/maas-controller` in `redhat-ods-applications` to 0.

The lab Kuadrant operator CSV caps the manager at 300Mi. Under AuthConfig load
it OOM-kills (exit 137) and never re-enforces `gateway-auth-policy`. Raise it:

```bash
oc patch sub rhcl-operator -n kuadrant-system --type merge -p \
  '{"spec":{"config":{"resources":{"limits":{"cpu":"500m","memory":"1Gi"},"requests":{"cpu":"200m","memory":"512Mi"}}}}}'
```

The lab Application `rhcl-operator` may revert that Subscription config on
self-heal; re-apply if the manager starts crash-looping again.

## References

- [OpenShift AI 3.5 install / DSC components](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install)
- [Update channels](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/understanding-update-channels_install)
- [Dashboard configuration options](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard)
- [Activating OGX](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_ogx/activating-the-ogx-operator_rag)
- [Working with AutoRAG](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_autorag/index)
- [Kueue Unmanaged](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue)
- [WVA / llm-d autoscaling](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/deploy_models_using_distributed_inference_with_llm-d/autoscaling-llmd-model-deployments)
