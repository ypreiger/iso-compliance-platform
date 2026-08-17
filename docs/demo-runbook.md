# Demo runbook — Temporary ACS policy exceptions (20 minutes)

Prerequisites: `.env` populated (never commit), `oc` logged in as cluster-admin, AAP + ACS already installed.

Quickstart:

```bash
./scripts/00-discovery.sh
python3 -m pip install ansible-core kubernetes pyyaml
ansible-galaxy collection install -r collections/requirements.yml
ansible-playbook playbooks/setup-demo-fixtures.yml
python3 scripts/aap-config-apply.py
ansible-playbook playbooks/demo-reset.yml   # clean slate; run twice to prove idempotency
```

AAP gateway: see `docs/environment.md`. Personas: AAP users `alice` / `bob` / `carol` (Execute) and `sre-approver` (Approve via team `SRE-Approvers`).

## Act 0 (2 min) — the problem

1. Open ACS → Policy **Kubernetes Actions: Exec into Pod** — enforcement includes `FAIL_KUBE_REQUEST_ENFORCEMENT`.
2. Show the nginx/sleep pod in `demo-app`.
3. `oc exec -n demo-app deploy/nginx -- date` (or `deploy/nginx` name from fixtures) is **blocked**.
4. Same exec into a system pod may still work if excluded; the demo pod is not.

## Act 1 (8 min) — UC-4 terminal access E2E (5-minute window)

Incident story: production issue in `demo-app`; namespace admin needs `oc exec` to collect logs.

1. Login to AAP as **alice**. Launch **WF-Temporary-ACS-Policy-Exception**.
2. Show the form: closed duration list `5/10/15/30/60`, mandatory justification, allowlisted policies only. *"The form is convenience; the workflow is the control."*
3. Optionally show **bob** launching the same namespace — JT-01 fails before approval (`rejected_rbac`).
4. As **sre-approver**, open Approvals (`#/workflow_approvals`). Context includes namespace, policy, duration, justification. Approve.
5. ACS policy exclusions show `AAPEX-<date>-<hex> demo-app` scoped to cluster `ocp-sandbox880` + namespace `demo-app` only.
6. `oc exec` in `demo-app` **succeeds**. In `demo-restricted` it remains **blocked** (blast radius).
7. Wait for expiry (5 min). Schedule `AAPEX-rollback-<id>` fires; exclusion gone; exec blocked again.
8. Show `audit/<request_id>.json` and `git log --oneline -- audit/`.

## Act 2 (4 min) — UC-5 privileged container

1. `oc apply -f demo/privileged-deploy.yaml` → admission **blocked**.
2. Run the workflow with policy **Privileged Container**, 10 minutes, approve.
3. Re-apply → pod runs.
4. After expiry, a **new** apply is blocked; the pod started during the window is still running. JT-03 residual report lists it. Optionally delete the pod as SRE follow-up.

## Act 3 (3 min) — safety story

1. **carol** launches the workflow → exact message: `No namespaces with Admin permissions were found. An ACS policy exception request cannot be opened.`
2. Run `ansible-playbook playbooks/verify-guardrails.yml` — allowlist refusal for `Fixable CVSS >= 7`.
3. Apply an exception, delete its rollback schedule, wait ≤5 min for **JT-06** to remove the orphan/expired exclusion (AC-08).

## Act 4 (3 min) — audit and notifications

1. `audit/` JSON fields: requester, approver, window, justification, ticket, history[].
2. `audit/notifications.log` (or SMTP if configured) for submitted/approved/applied/removed.

## Reset (repeatable)

```bash
ansible-playbook playbooks/demo-reset.yml
ansible-playbook playbooks/demo-reset.yml   # second run: changed=false / no-op exclusions
```

Does not delete ACS policies. Restores by stripping `AAPEX-*` exclusions only. Demo enforcement stays on unless you set `RESTORE_ENFORCEMENT=1` (see `docs/manual-steps.md`).
