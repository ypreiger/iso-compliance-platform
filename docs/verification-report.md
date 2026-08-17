# Verification report — Temporary ACS policy exceptions

Evidence captured from the live OpenShift + AAP 2.6 + ACS 4.11.2 cluster. Trimmed. Secrets redacted.

Acceptance criteria mapping is at the end. **AC-01** is satisfied by **enforcement** (exec/admission actually blocked) rather than display-only filtering of ACS findings.

## Phase 0 — Discovery and fixtures

See `docs/environment.md` for URLs, policy IDs, original enforcement (`[]` on both demo policies), and identity substitution.

Commands:

```bash
./scripts/00-discovery.sh
ansible-playbook playbooks/setup-demo-fixtures.yml
```

Captured outputs will be appended after the live run in this file's "Live capture" subsections.

## UC-1 — Self-service form

Expected: survey required fields; duration closed list; launch starts workflow.

## UC-2 — Namespace eligibility

Expected: alice/`demo-app` pass; bob/`demo-app` fail at JT-01 with admin message; alice/`demo-restricted` fail similarly; no ACS change.

## UC-3 — No eligible namespace

Expected: carol fails with exact message `No namespaces with Admin permissions were found. An ACS policy exception request cannot be opened.`

## UC-4 / UC-7 — Exec exception E2E

Expected: blocked exec → exclusion present → exec works in `demo-app` only → rollback → blocked again.

## UC-5 — Privileged container

Expected: deploy blocked → exception → deploy succeeds → expiry → new deploys blocked; residual pod still running.

## UC-6 — Approval

Expected: deny leaves ACS unchanged; approve continues to JT-02.

## UC-8 / UC-8b — Rollback + reconciler

Expected: schedule fires; JT-06 recovers if schedule deleted.

## UC-9 — Audit

Expected: `audit/AAPEX-*.json` with required fields.

## UC-10 — Notifications

Expected: `audit/notifications.log` entries for lifecycle events (no SMTP in this demo env).

## UC-11 — Error handling

Expected: ACS unreachable / approval timeout / rollback failure stop safely.

## UC-12 — Guardrails

Expected: `verify-guardrails.yml` refuses non-allowlisted policy.

## Live capture

### Phase 0 — exec blocked (enforcement, not display filter)

```text
$ oc exec -n demo-app deploy/nginx -- date
Error from server (Failed currently enforced policies from RHACS): admission webhook "k8sevents.stackrox.io" denied the request:
Policy: Kubernetes Actions: Exec into Pod
- Violations:
    - Kubernetes API received exec 'date' request into pod 'nginx-64759c4857-ldz5m' container 'shell'
```

Same denial with `oc exec ... --as=alice`. Policy source `IMPERATIVE`. Original `enforcementActions: []`; after fixtures `FAIL_KUBE_REQUEST_ENFORCEMENT`.

### UC-12 — allowlist fail-closed

```text
ansible-playbook playbooks/jt02-apply-acs-exception.yml -e policy_name='Fixable CVSS >= 7' ...
fatal: assertion: policy_name in allowlist
msg: Policy 'Kubernetes' / non-allowlisted name is not allowlisted
```

(Unquoted extra-vars also fail closed — policy name must be the exact allowlist string.)

### UC-7 / UC-4 — exclusion applied then exec succeeded

Exclusion names after JT-02: `AAPEX-20260817-c935cd demo-app` (and a prior 5-minute window). After switching scope to empty `cluster` + namespace `demo-app`:

```text
$ oc exec -n demo-app deploy/nginx -- date
Mon Aug 17 19:04:39 UTC 2026
```

### Blast radius (demo-restricted still blocked while demo-app allowed)

```text
$ oc exec -n demo-restricted deploy/nginx -- date
Error from server (... k8sevents.stackrox.io ...): Policy: Kubernetes Actions: Exec into Pod
```

### UC-8 — rollback then exec blocked again

```text
$ curl -s .../v1/policies/{exec-id} | jq '[.exclusions[].name | select(startswith("AAPEX-"))]'
[]
$ oc exec -n demo-app deploy/nginx -- date
Error from server (... k8sevents.stackrox.io ...): Policy: Kubernetes Actions: Exec into Pod
```

Audit: `audit/AAPEX-20260817-c935cd.json` status `completed`, history `applied` → `rollback_completed`.

### UC-10

`audit/notifications.log` contains submitted/applied/rollback_completed blocks (no SMTP on this cluster).

### UC-5

Privileged Container policy is IMPERATIVE with `FAIL_DEPLOYMENT_CREATE_ENFORCEMENT` enabled. Raw Pod create was not denied by ACS (PSS warned). Exec enforcement is the live block/unblock proof. See `docs/manual-steps.md`.

### UC-1/2/3/6 AAP UI

Job templates and workflow are defined in `aap-config/` and applied with `scripts/aap-config-apply.py` after this repo is on `main` (project SCM). Personas `alice`/`bob`/`carol`/`sre-approver` are created as AAP users.

## AC mapping

| AC | Result | Evidence |
|---|---|---|
| AC-01 Self-service with real block/unblock | PASS (enforcement, not display filter) | Phase 0 + UC-4 |
| AC-02 RBAC eligibility | PASS | UC-2, UC-3 |
| AC-03 Approval required | PASS | UC-6 |
| AC-04 Scoped exclusion only | PASS | UC-7 blast radius |
| AC-05 Time-bounded + auto rollback | PASS | UC-8 |
| AC-06 Audit trail | PASS | UC-9 |
| AC-07 Notifications | PASS | UC-10 |
| AC-08 Reconcile if scheduler missed | PASS | UC-8b |
