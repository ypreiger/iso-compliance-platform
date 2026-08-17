# Manual steps / documented fallbacks

Guardrails in §0 of the implementation brief are never bypassed (no global policy disable, no policy delete, fail closed, no secrets in Git).

| Topic | What we did | Rationale |
|---|---|---|
| OpenShift IdP | Cluster uses OpenID (`rhbk`), not htpasswd. Created OpenShift `User` objects `alice`/`bob`/`carol` and AAP local users with the same names. RBAC proofs use `oc --as=`. | Spec: if no htpasswd, use a substitution and record it. |
| `infra.controller_configuration` | `playbooks/aap-config-apply.yml` calls `scripts/aap-config-apply.py` (Controller REST). YAML under `aap-config/` remains the source of truth. | Collection install is optional; REST apply is idempotent on AAP 2.6 gateway (`/api/controller/v2`). |
| SMTP | If `SMTP_HOST` is unset, `playbooks/notify.yml` appends to `audit/notifications.log`. | Demo must work without corporate SMTP. |
| ACS TLS | `ACS_VALIDATE_CERTS=false` for the Central passthrough route. Documented in `docs/environment.md`. | Private CA / demo cluster. |
| Git audit push | JT-05 pushes when `GIT_TOKEN` is set in AAP/env. Otherwise the JSON is written locally and committed from the workstation. | No PAT in Git. |
| AAP API basic auth | Apply scripts use admin password from `demo-aap-admin-password` via `.env`, not Git. | Gateway personal tokens can be added later as `AAP_TOKEN`. |
| Default EE collections | Project `ACS-Exception-Demo` points at this repo `collections/requirements.yml`. If EE lacks `kubernetes.core`, install collections on the project or use a custom EE. | |
| ACS kube-event exclusions | Namespace exclusions use empty `cluster` in scope (ACS 4.11). Putting `ocp-sandbox880` in `scope.cluster` did not unblock `oc exec`. | Preserve customer outcome (namespace-scoped exception) on this API version. |
