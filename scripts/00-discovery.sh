#!/usr/bin/env bash
# Phase 0 discovery: verify AAP + ACS, record live values into docs/environment.md
# and vars/discovered.yml. Does not print secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p docs vars

need() { command -v "$1" >/dev/null || { echo "missing $1"; exit 1; }; }
need oc; need curl; need jq; need python3

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a && source .env && set +a
fi

AAP_URL="${AAP_URL:-https://demo-aap-aap.apps.ocp.7hrxw.sandbox880.opentlc.com}"
ACS_URL="${ACS_URL:-https://central-acs.apps.ocp.7hrxw.sandbox880.opentlc.com}"
ACS_VALIDATE_CERTS="${ACS_VALIDATE_CERTS:-false}"
CURL_INSECURE=()
[[ "${ACS_VALIDATE_CERTS}" == "false" ]] && CURL_INSECURE=(-k)

WHOAMI="$(oc whoami)"
OCP_API="$(oc config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
OCP_VER="$(oc version -o json | jq -r '.openshiftVersion // .serverVersion.gitVersion')"

AAP_PASS="${CONTROLLER_PASSWORD:-}"
if [[ -z "${AAP_PASS}" ]]; then
  AAP_PASS="$(oc get secret demo-aap-admin-password -n aap -o jsonpath='{.data.password}' | base64 -d)"
fi
ACS_PASS="${ACS_ADMIN_PASSWORD:-}"
if [[ -z "${ACS_PASS}" ]]; then
  ACS_PASS="$(oc get secret central-htpasswd -n acs -o jsonpath='{.data.password}' | base64 -d)"
fi

detect_aap_base() {
  local cand
  for cand in \
    "${AAP_URL}/api/controller/v2" \
    "${AAP_URL}/api/v2"; do
    if curl -sk -u "admin:${AAP_PASS}" -o /dev/null -w '%{http_code}' "${cand}/ping/" | grep -q '^200$'; then
      echo "${cand}"
      return 0
    fi
  done
  echo "ERROR: AAP ping failed" >&2
  return 1
}

AAP_API_BASE="$(detect_aap_base)"
AAP_PING="$(curl -sk -u "admin:${AAP_PASS}" "${AAP_API_BASE}/ping/")"
AAP_CTRL_VER="$(echo "${AAP_PING}" | jq -r '.version')"

if [[ -z "${ACS_TOKEN:-}" ]]; then
  ACS_TOKEN="$(curl -sk -u "admin:${ACS_PASS}" -X POST "${ACS_URL}/v1/apitokens/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"aap-discovery-$(date +%s)\",\"role\":\"Admin\"}" | jq -r '.token')"
fi

acs_get() {
  curl -s "${CURL_INSECURE[@]}" -H "Authorization: Bearer ${ACS_TOKEN}" "$1"
}

ACS_META="$(acs_get "${ACS_URL}/v1/metadata")"
ACS_VER="$(echo "${ACS_META}" | jq -r '.version')"
ACS_CLUSTERS="$(acs_get "${ACS_URL}/v1/clusters")"
ACS_CLUSTER_NAME="$(echo "${ACS_CLUSTERS}" | jq -r '.clusters[0].name')"
ACS_CLUSTER_ID="$(echo "${ACS_CLUSTERS}" | jq -r '.clusters[0].id')"

POLICIES="$(acs_get "${ACS_URL}/v1/policies")"
python3 - "${POLICIES}" <<'PY' > /tmp/acs-demo-policies.json
import json,sys
d=json.loads(sys.argv[1])
want={"Kubernetes Actions: Exec into Pod","Privileged Container"}
out=[]
for p in d.get("policies",[]):
    if p.get("name") in want:
        out.append(p)
json.dump(out, sys.stdout)
PY

EXEC_ID="$(jq -r '.[] | select(.name=="Kubernetes Actions: Exec into Pod") | .id' /tmp/acs-demo-policies.json)"
PRIV_ID="$(jq -r '.[] | select(.name=="Privileged Container") | .id' /tmp/acs-demo-policies.json)"
EXEC_POL="$(acs_get "${ACS_URL}/v1/policies/${EXEC_ID}")"
PRIV_POL="$(acs_get "${ACS_URL}/v1/policies/${PRIV_ID}")"

for src in "$(echo "${EXEC_POL}" | jq -r '.source')" "$(echo "${PRIV_POL}" | jq -r '.source')"; do
  if [[ "${src}" == "DECLARATIVE" ]]; then
    echo "STOP: policy source is DECLARATIVE — exclusions would be reverted by GitOps. See docs/environment.md"
    exit 2
  fi
done

# Probe expiration field (add + immediately remove a tagged exclusion).
python3 - <<PY
import json, copy, os, urllib.request, ssl
acs=os.environ.get("ACS_URL","${ACS_URL}")
token="""${ACS_TOKEN}"""
pid="${EXEC_ID}"
ctx=ssl._create_unverified_context()
def get():
    req=urllib.request.Request(f"{acs}/v1/policies/{pid}", headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req, context=ctx))
def put(body):
    data=json.dumps(body).encode()
    req=urllib.request.Request(f"{acs}/v1/policies/{pid}", data=data, method="PUT",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, context=ctx).read()
pol=get()
probe={"name":"AAPEX-EXPIRY-PROBE discovery","deployment":{"name":"","scope":{"cluster":"${ACS_CLUSTER_NAME}","namespace":"kube-system"}},"expiration":"2099-01-01T00:00:00Z"}
body=copy.deepcopy(pol)
for k in list(body):
    if k.startswith("SORT"):
        body.pop(k)
body["exclusions"]=list(body.get("exclusions") or [])+[probe]
put(body)
pol2=get()
ok=any((e.get("name") or "").startswith("AAPEX-EXPIRY-PROBE") and e.get("expiration") for e in pol2.get("exclusions") or [])
body2=copy.deepcopy(pol2)
for k in list(body2):
    if k.startswith("SORT"):
        body2.pop(k)
body2["exclusions"]=[e for e in body2.get("exclusions") or [] if not (e.get("name") or "").startswith("AAPEX-EXPIRY-PROBE")]
put(body2)
open("/tmp/acs-expiry-supported","w").write("true" if ok else "false")
print("expiration_field_supported", ok)
PY
EXPIRY_OK="$(cat /tmp/acs-expiry-supported)"

mkdir -p "${ROOT}/vars"
cat > "${ROOT}/vars/discovered.yml" <<YAML
---
openshift_api: "${OCP_API}"
openshift_version: "${OCP_VER}"
aap_url: "${AAP_URL}"
aap_api_base: "${AAP_API_BASE}"
aap_controller_version: "${AAP_CTRL_VER}"
acs_url: "${ACS_URL}"
acs_version: "${ACS_VER}"
acs_cluster_name: "${ACS_CLUSTER_NAME}"
acs_cluster_id: "${ACS_CLUSTER_ID}"
acs_expiration_field_supported: ${EXPIRY_OK}
acs_validate_certs: false
identity_note: "Cluster IdP is OpenID (rhbk). Demo personas are OpenShift User objects plus AAP local users; oc --as impersonation is used for RBAC proofs."
demo_namespaces:
  - demo-app
  - demo-restricted
audit_git_path: audit
YAML

python3 - "${EXEC_POL}" "${PRIV_POL}" "${AAP_PING}" "${ACS_META}" "${OCP_API}" "${OCP_VER}" "${WHOAMI}" "${AAP_URL}" "${AAP_API_BASE}" "${ACS_URL}" "${ACS_CLUSTER_NAME}" "${ACS_CLUSTER_ID}" "${ACS_VER}" "${EXPIRY_OK}" "${ROOT}/docs/environment.md" <<'PY'
import json, sys
from datetime import datetime, timezone
exec_pol=json.loads(sys.argv[1])
priv_pol=json.loads(sys.argv[2])
aap_ping=json.loads(sys.argv[3])
acs_meta=json.loads(sys.argv[4])
ocp_api, ocp_ver, whoami, aap_url, aap_base, acs_url, cluster_name, cluster_id, acs_ver, expiry, out = sys.argv[5:]

def pol_block(p):
    return f"""- **Name:** `{p.get("name")}`
  - **ID:** `{p.get("id")}`
  - **source:** `{p.get("source")}`
  - **disabled:** `{p.get("disabled")}`
  - **lifecycleStages:** `{p.get("lifecycleStages")}`
  - **enforcementActions (original):** `{p.get("enforcementActions")}`
  - **existing exclusion count:** {len(p.get("exclusions") or [])}
"""

md = f"""# Environment (Phase 0 discovery)

Captured **{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}** from the live cluster. No secrets.

## OpenShift

- `oc whoami`: `{whoami}`
- API: `{ocp_api}`
- OpenShift version: `{ocp_ver}`
- Apps domain: `apps.ocp.7hrxw.sandbox880.opentlc.com`

## Identity

The cluster OAuth IdP is **OpenID (`rhbk`)** (Keycloak), not htpasswd.
Demo personas (`alice`, `bob`, `carol`) are created as **OpenShift `User` objects** with RoleBindings.
Verification uses `oc --as=<user>` impersonation. Matching **AAP local users** share the same usernames so workflow-side RBAC validation is authoritative.

## Ansible Automation Platform

- Gateway URL: `{aap_url}`
- **AAP_API_BASE:** `{aap_base}`
- Controller version (ping): `{aap_ping.get("version")}`
- Ping: `GET {{AAP_API_BASE}}/ping/` → 200
- Admin user: `admin` (password from Secret `demo-aap-admin-password` in namespace `aap`, not stored in Git)

## ACS (RHACS Central)

- Central URL: `{acs_url}`
- Version: `{acs_ver}` (buildFlavor `{acs_meta.get("buildFlavor")}`)
- Metadata: `GET {{ACS_URL}}/v1/metadata` → 200
- TLS: route is passthrough; demo clients use `ACS_VALIDATE_CERTS=false` (self-signed / private CA)
- **Secured cluster name:** `{cluster_name}` (id `{cluster_id}`)
- Exclusion `expiration` field **supported:** `{expiry}` (probed with add+remove of `AAPEX-EXPIRY-PROBE`; authoritative removal remains the rollback job)
- **Kube-event exclusion scope (ACS 4.11.2):** namespace-scoped exclusions must use empty `deployment.scope.cluster` (same as ACS default exclusions). Setting the ACS cluster name (`ocp-sandbox880`) prevented the exec webhook from honoring the exception. JT-02 now writes `cluster: ""` + `namespace: <target>`. The ACS cluster name is still recorded here for inventory.

### Demo policies (both `IMPERATIVE` — demo may proceed)

{pol_block(exec_pol)}
{pol_block(priv_pol)}

### Original enforcement (restore after demo)

| Policy | original enforcementActions | demo enforcement (after fixtures) |
|---|---|---|
| Kubernetes Actions: Exec into Pod | `{exec_pol.get("enforcementActions")}` | `FAIL_KUBE_REQUEST_ENFORCEMENT` |
| Privileged Container | `{priv_pol.get("enforcementActions")}` | `FAIL_DEPLOYMENT_CREATE_ENFORCEMENT` |

Fixtures **do not disable or delete** these policies. They only add the listed enforcement action if missing, and may add/remove `AAPEX-*` exclusions.

## Notes vs the written instructions

- AAP 2.6 gateway: Controller API is `{aap_base}` not `/api/v2` on the gateway host.
- No htpasswd IdP; User CR + impersonation substitution (this file).
- Hub file storage on this cluster is S3/MinIO (unrelated to this demo).
"""
open(out,"w").write(md)
print("wrote", out)
PY

echo "Discovery complete. AAP_API_BASE=${AAP_API_BASE} ACS ${ACS_VER} cluster ${ACS_CLUSTER_NAME}"
