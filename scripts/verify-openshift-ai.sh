#!/usr/bin/env bash
# Verify OpenShift AI 3.5 GA (or later 3.x) and enabled platform features.
set -euo pipefail

NS_OP="${RHOAI_OPERATOR_NS:-redhat-ods-operator}"
fail=0
ok() { printf 'PASS  %s\n' "$*"; }
bad() { printf 'FAIL  %s\n' "$*"; fail=1; }
info() { printf 'INFO  %s\n' "$*"; }

oc whoami &>/dev/null || { echo "ERROR: oc login required"; exit 1; }

csv_line="$(oc get csv -n "${NS_OP}" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.version}{"\t"}{.status.phase}{"\n"}{end}' | grep '^rhods-operator' | tail -1 || true)"
csv_name="$(echo "${csv_line}" | awk '{print $1}')"
csv_ver="$(echo "${csv_line}" | awk '{print $2}')"
csv_phase="$(echo "${csv_line}" | awk '{print $3}')"
info "CSV ${csv_name} version=${csv_ver} phase=${csv_phase}"

if [[ -z "${csv_ver}" ]]; then
  bad "rhods-operator CSV not found in ${NS_OP}"
elif [[ "${csv_ver}" == *ea* || "${csv_ver}" == *EA* ]]; then
  bad "OpenShift AI is still Early Access (${csv_ver}); expected GA (3.5.0+)"
elif [[ "${csv_phase}" != "Succeeded" ]]; then
  bad "CSV phase is ${csv_phase}, expected Succeeded"
else
  ok "OpenShift AI operator ${csv_ver} Succeeded"
fi

chan="$(oc get subscription rhods-operator -n "${NS_OP}" -o jsonpath='{.spec.channel}' 2>/dev/null || true)"
info "Subscription channel=${chan}"
if [[ "${chan}" == "stable-3.x" || "${chan}" == "stable-3.5" || "${chan}" == "eus-3.5" ]]; then
  ok "Update channel is ${chan}"
else
  bad "Update channel is '${chan}' (want stable-3.x / stable-3.5 / eus-3.5)"
fi

dsc_json="$(oc get datasciencecluster default-dsc -o json 2>/dev/null || echo '{}')"
python3 - "${dsc_json}" <<'PY' || fail=1
import json, os, sys
dsc = json.loads(sys.argv[1] or "{}")
spec = (dsc.get("spec") or {}).get("components") or {}
status = (dsc.get("status") or {}).get("components") or {}
want = {
    "aigateway": "Managed",
    "aipipelines": "Managed",
    "dashboard": "Managed",
    "feastoperator": "Managed",
    "kserve": "Managed",
    "mcplifecycleoperator": "Managed",
    "mlflowoperator": "Managed",
    "modelregistry": "Managed",
    "ogx": "Managed",
    "ray": "Managed",
    "sparkoperator": "Managed",
    "trainer": "Managed",
    "trainingoperator": "Managed",
    "trustyai": "Managed",
    "workbenches": "Managed",
}
# kueue must be Unmanaged in 3.5; llamastack Removed in favor of OGX
want_special = {"kueue": "Unmanaged", "llamastackoperator": "Removed"}
ok = True
for name, expected in {**want, **want_special}.items():
    got = (spec.get(name) or {}).get("managementState")
    if got != expected:
        print(f"FAIL  DSC {name}.managementState={got} (want {expected})")
        ok = False
    else:
        print(f"PASS  DSC {name}={got}")
kserve = spec.get("kserve") or {}
for nested, expected in (("modelsAsService", "Removed"), ("wva", "Managed"), ("nim", "Managed"), ("modelCache", "Managed")):
    got = (kserve.get(nested) or {}).get("managementState")
    if got != expected:
        print(f"FAIL  DSC kserve.{nested}={got} (want {expected})")
        ok = False
    else:
        print(f"PASS  DSC kserve.{nested}={got}")
aigw = spec.get("aigateway") or {}
got = (aigw.get("modelsAsAService") or {}).get("managementState")
if got != "Removed":
    print(f"FAIL  DSC aigateway.modelsAsAService={got} (want Removed — conflicts with Kuadrant MaaS)")
    ok = False
else:
    print("PASS  DSC aigateway.modelsAsAService=Removed")
conds = (dsc.get("status") or {}).get("conditions") or []
ready = next((c for c in conds if c.get("type") == "Ready"), None)
if ready and ready.get("status") == "True":
    print("PASS  DataScienceCluster Ready=True")
else:
    print(f"FAIL  DataScienceCluster Ready={ready}")
    ok = False
sys.exit(0 if ok else 1)
PY

dash="$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o json 2>/dev/null || echo '{}')"
python3 - "${dash}" <<'PY' || fail=1
import json, sys
d = json.loads(sys.argv[1] or "{}")
cfg = (d.get("spec") or {}).get("dashboardConfig") or {}
want_true = ["genAiStudio", "autorag", "automl", "modelAsService", "mcpCatalog", "mcpRegistry", "guardrails", "promptManagement", "agentsCatalog", "agentOps", "agentConfigManagement"]
want_false = ["disableLMEval", "disableKueue", "disablePipelines", "disableFeatureStore", "disableLLMd"]
ok = True
for k in want_true:
    if cfg.get(k) is not True:
        print(f"FAIL  dashboardConfig.{k}={cfg.get(k)} (want true)")
        ok = False
    else:
        print(f"PASS  dashboardConfig.{k}=true")
for k in want_false:
    if cfg.get(k) is not False:
        print(f"FAIL  dashboardConfig.{k}={cfg.get(k)} (want false)")
        ok = False
    else:
        print(f"PASS  dashboardConfig.{k}=false")
sys.exit(0 if ok else 1)
PY

csv_in_ns() {
  local ns="$1" needle="$2"
  local names
  names="$(oc get csv -n "${ns}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)"
  grep -qi "${needle}" <<<"${names}"
}

if csv_in_ns openshift-kueue-operator kueue-operator; then
  ok "Kueue operator CSV present"
else
  bad "Kueue operator CSV missing"
fi
if oc get kueues.kueue.openshift.io cluster &>/dev/null; then
  ok "Kueue CR cluster exists"
else
  bad "Kueue CR cluster missing"
fi
if csv_in_ns openshift-lws-operator leader-worker-set; then
  ok "Leader Worker Set operator CSV present"
else
  bad "Leader Worker Set operator CSV missing"
fi
if oc get leaderworkersetoperators.operator.openshift.io cluster &>/dev/null; then
  ok "LeaderWorkerSetOperator cluster exists"
else
  bad "LeaderWorkerSetOperator cluster missing"
fi
if csv_in_ns openshift-jobset-operator jobset-operator; then
  ok "JobSet operator CSV present"
else
  bad "JobSet operator CSV missing"
fi
if oc get jobsetoperators.operator.openshift.io cluster &>/dev/null; then
  ok "JobSetOperator cluster exists"
else
  bad "JobSetOperator cluster missing"
fi
if csv_in_ns openshift-cluster-observability-operator cluster-observability-operator; then
  ok "Cluster Observability operator CSV present"
else
  bad "Cluster Observability operator CSV missing"
fi
if csv_in_ns openshift-opentelemetry-operator opentelemetry-operator; then
  ok "OpenTelemetry operator CSV present"
else
  bad "OpenTelemetry operator CSV missing"
fi
if csv_in_ns openshift-tempo-operator tempo-operator; then
  ok "Tempo operator CSV present"
else
  bad "Tempo operator CSV missing"
fi

# OGX operator pod (agent orchestration)
if oc get pods -n redhat-ods-applications -l app.kubernetes.io/name=ogx-k8s-operator --no-headers 2>/dev/null | grep -q Running; then
  ok "OGX operator pod Running"
else
  info "OGX operator pod not Running yet (may still be rolling)"
fi

# Lab Kuadrant MaaS must stay in front of the playground (not 3.5 bundled MaaS).
enforced="$(oc get authpolicy gateway-auth-policy -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type=="Enforced")].status}' 2>/dev/null || true)"
if [[ "${enforced}" == "True" ]]; then
  ok "AuthPolicy gateway-auth-policy Enforced"
else
  bad "AuthPolicy gateway-auth-policy Enforced=${enforced:-missing} (playground MaaS auth)"
fi
if oc get tokenratelimitpolicy gateway-default-deny -n openshift-ingress &>/dev/null; then
  bad "TokenRateLimitPolicy gateway-default-deny present (3.5 MaaS deny-all; playground 429)"
else
  ok "No leftover gateway-default-deny TokenRateLimitPolicy"
fi
kready="$(oc get deploy kuadrant-operator-controller-manager -n kuadrant-system -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
if [[ "${kready}" == "1" ]]; then
  ok "Kuadrant operator manager Ready"
else
  bad "Kuadrant operator manager readyReplicas=${kready:-0} (needs ~1Gi memory)"
fi

exit "${fail}"
