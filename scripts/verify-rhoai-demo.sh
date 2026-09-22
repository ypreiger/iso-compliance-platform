#!/usr/bin/env bash
# Verify the rhoai-demo project and connected RHOAI 3.5 GA/TP surfaces.
set -euo pipefail

NS="${RHOAI_DEMO_NS:-rhoai-demo}"
fail=0
ok() { printf 'PASS  %s\n' "$*"; }
bad() { printf 'FAIL  %s\n' "$*"; fail=1; }
info() { printf 'INFO  %s\n' "$*"; }

oc whoami &>/dev/null || { echo "ERROR: oc login required"; exit 1; }

ns_dash="$(oc get ns "${NS}" -o jsonpath='{.metadata.labels.opendatahub\.io/dashboard}' 2>/dev/null || true)"
if [[ "${ns_dash}" == "true" ]]; then
  ok "Namespace ${NS} is a Data Science project"
else
  bad "Namespace ${NS} missing opendatahub.io/dashboard=true"
fi

dspa_ready="$(oc get dspa dspa -n "${NS}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
if [[ "${dspa_ready}" == "True" ]]; then
  ok "DSPA dspa Ready"
else
  bad "DSPA dspa Ready=${dspa_ready:-missing}"
fi

ogx_health="$(oc get ogxserver ogx -n "${NS}" -o jsonpath='{.status.conditions[?(@.type=="HealthCheck")].status}' 2>/dev/null || true)"
ogx_deploy="$(oc get ogxserver ogx -n "${NS}" -o jsonpath='{.status.conditions[?(@.type=="DeploymentReady")].status}' 2>/dev/null || true)"
if [[ "${ogx_health}" == "True" || "${ogx_deploy}" == "True" ]]; then
  ok "OGXServer ogx healthy (HealthCheck=${ogx_health} DeploymentReady=${ogx_deploy})"
else
  bad "OGXServer ogx not ready (HealthCheck=${ogx_health} DeploymentReady=${ogx_deploy})"
fi

ml_avail="$(oc get mlflow mlflow -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || true)"
if [[ "${ml_avail}" == "True" ]]; then
  ok "MLflow Available"
else
  bad "MLflow Available=${ml_avail:-missing}"
fi

fs_phase="$(oc get featurestore iso-features -n "${NS}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
if [[ "${fs_phase}" == "Ready" ]]; then
  ok "FeatureStore iso-features Ready"
else
  bad "FeatureStore iso-features phase=${fs_phase:-missing}"
fi

nb_ready="$(oc get notebook demo-workbench -n "${NS}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
if [[ "${nb_ready}" == "1" ]]; then
  ok "Workbench demo-workbench Ready"
else
  bad "Workbench demo-workbench readyReplicas=${nb_ready:-0}"
fi

mcp_ready="$(oc get mcpserver kubernetes -n "${NS}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
if [[ "${mcp_ready}" == "True" ]]; then
  ok "MCPServer kubernetes Ready"
else
  info "MCPServer kubernetes Ready=${mcp_ready:-missing} (catalog still lists lls-demo Kubernetes/Slack)"
fi

mr_avail="$(oc get modelregistry.modelregistry.opendatahub.io rhoai-demo -n rhoai-model-registries -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || true)"
if [[ "${mr_avail}" == "True" ]]; then
  ok "ModelRegistry rhoai-demo Available"
else
  bad "ModelRegistry rhoai-demo Available=${mr_avail:-missing}"
fi

if oc get evalhub evalhub -n "${NS}" &>/dev/null; then
  ok "EvalHub CR present in ${NS}"
else
  bad "EvalHub CR missing in ${NS}"
fi
if oc get deploy eval-hub-ui -n redhat-ods-applications &>/dev/null; then
  ok "eval-hub-ui Deployment present"
else
  bad "eval-hub-ui Deployment missing"
fi

if oc get hardwareprofile nvidia-l40s -n redhat-ods-applications &>/dev/null; then
  ok "HardwareProfile nvidia-l40s present"
else
  bad "HardwareProfile nvidia-l40s missing"
fi

lq="$(oc get localqueue default -n "${NS}" -o jsonpath='{.spec.clusterQueue}' 2>/dev/null || true)"
if [[ "${lq}" == "default" ]]; then
  ok "LocalQueue default → ClusterQueue default"
else
  bad "LocalQueue default missing or clusterQueue=${lq}"
fi

if oc get secret pipeline-bucket -n "${NS}" &>/dev/null \
  && oc get secret gpt-oss-20b-endpoint -n "${NS}" &>/dev/null \
  && oc get secret bge-m3-endpoint -n "${NS}" &>/dev/null; then
  ok "Dashboard connections (S3 + gpt-oss-20b + BGE-M3) present"
else
  bad "Missing dashboard connection secrets"
fi

pg="$(oc get deploy postgres -n "${NS}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
if [[ "${pg}" == "1" ]]; then
  ok "OGX Postgres Ready"
else
  bad "OGX Postgres readyReplicas=${pg:-0}"
fi

minio="$(oc get deploy minio -n "${NS}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
if [[ "${minio}" == "1" ]]; then
  ok "Demo MinIO Ready"
else
  bad "Demo MinIO readyReplicas=${minio:-0}"
fi

gpu="$(oc get llminferenceservice gpt-oss-20b -n llm -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
if [[ "${gpu}" == "True" ]]; then
  ok "LLMInferenceService gpt-oss-20b Ready"
else
  info "LLMInferenceService gpt-oss-20b Ready=${gpu:-missing}"
fi

if oc get deploy rhods-dashboard -n redhat-ods-applications -o jsonpath='{.status.readyReplicas}' 2>/dev/null | grep -q '[1-9]'; then
  ok "rhods-dashboard Ready"
else
  bad "rhods-dashboard not Ready"
fi

autorag="$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.autorag}' 2>/dev/null || true)"
studio="$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiStudio}' 2>/dev/null || true)"
if [[ "${autorag}" == "true" && "${studio}" == "true" ]]; then
  ok "Dashboard AutoRAG + Gen AI Studio flags on"
else
  bad "Dashboard autorag=${autorag} genAiStudio=${studio}"
fi

exit "${fail}"
