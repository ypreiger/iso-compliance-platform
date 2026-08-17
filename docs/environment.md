# Environment (Phase 0 discovery)

Captured **2026-08-17T18:58:41Z** from the live cluster. No secrets.

## OpenShift

- `oc whoami`: `admin`
- API: `https://api.ocp.7hrxw.sandbox880.opentlc.com:6443`
- OpenShift version: `4.20.0`
- Apps domain: `apps.ocp.7hrxw.sandbox880.opentlc.com`

## Identity

The cluster OAuth IdP is **OpenID (`rhbk`)** (Keycloak), not htpasswd.
Demo personas (`alice`, `bob`, `carol`) are created as **OpenShift `User` objects** with RoleBindings.
Verification uses `oc --as=<user>` impersonation. Matching **AAP local users** share the same usernames so workflow-side RBAC validation is authoritative.

## Ansible Automation Platform

- Gateway URL: `https://demo-aap-aap.apps.ocp.7hrxw.sandbox880.opentlc.com`
- **AAP_API_BASE:** `https://demo-aap-aap.apps.ocp.7hrxw.sandbox880.opentlc.com/api/controller/v2`
- Controller version (ping): `4.7.15`
- Ping: `GET {AAP_API_BASE}/ping/` → 200
- Admin user: `admin` (password from Secret `demo-aap-admin-password` in namespace `aap`, not stored in Git)

## ACS (RHACS Central)

- Central URL: `https://central-acs.apps.ocp.7hrxw.sandbox880.opentlc.com`
- Version: `4.11.2` (buildFlavor `release`)
- Metadata: `GET {ACS_URL}/v1/metadata` → 200
- TLS: route is passthrough; demo clients use `ACS_VALIDATE_CERTS=false` (self-signed / private CA)
- **Secured cluster name:** `ocp-sandbox880` (id `51f83691-a189-449d-aa81-9e3ffc9abded`)
- Exclusion `expiration` field **supported:** `true` (probed with add+remove of `AAPEX-EXPIRY-PROBE`; authoritative removal remains the rollback job)
- **Kube-event exclusion matching (ACS 4.11.2):** namespace-scoped exclusions must use empty `deployment.scope.cluster`. Setting `cluster: ocp-sandbox880` did not unblock `oc exec`. JT-02 writes `cluster: ""` + target namespace.

After fixtures, enforcement was enabled (original `[]` preserved in the table above for restore):
- Exec into Pod: `FAIL_KUBE_REQUEST_ENFORCEMENT` (verified: `oc exec` denied by webhook `k8sevents.stackrox.io`)
- Privileged Container: `FAIL_DEPLOYMENT_CREATE_ENFORCEMENT` (admission create path is enabled on SecuredCluster; PSS also warns)

### Demo policies (both `IMPERATIVE` — demo may proceed)

- **Name:** `Kubernetes Actions: Exec into Pod`
  - **ID:** `8ab0f199-4904-4808-9461-3501da1d1b77`
  - **source:** `IMPERATIVE`
  - **disabled:** `False`
  - **lifecycleStages:** `['RUNTIME']`
  - **enforcementActions (original):** `[]`
  - **existing exclusion count:** 4

- **Name:** `Privileged Container`
  - **ID:** `fe9de18b-86db-44d5-a7c4-74173ccffe2e`
  - **source:** `IMPERATIVE`
  - **disabled:** `False`
  - **lifecycleStages:** `['DEPLOY']`
  - **enforcementActions (original):** `[]`
  - **existing exclusion count:** 26


### Original enforcement (restore after demo)

| Policy | original enforcementActions | demo enforcement (after fixtures) |
|---|---|---|
| Kubernetes Actions: Exec into Pod | `[]` | `FAIL_KUBE_REQUEST_ENFORCEMENT` |
| Privileged Container | `[]` | `FAIL_DEPLOYMENT_CREATE_ENFORCEMENT` |

Fixtures **do not disable or delete** these policies. They only add the listed enforcement action if missing, and may add/remove `AAPEX-*` exclusions.

## Notes vs the written instructions

- AAP 2.6 gateway: Controller API is `https://demo-aap-aap.apps.ocp.7hrxw.sandbox880.opentlc.com/api/controller/v2` not `/api/v2` on the gateway host.
- No htpasswd IdP; User CR + impersonation substitution (this file).
- Hub file storage on this cluster is S3/MinIO (unrelated to this demo).
