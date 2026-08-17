#!/usr/bin/env python3
"""Idempotently add demo enforcement actions. Never disable or delete policies."""
from __future__ import annotations

import copy
import json
import os
import ssl
import sys
import urllib.request

ACS = os.environ["ACS_URL"].rstrip("/")
TOKEN = os.environ["ACS_TOKEN"]
CTX = ssl._create_unverified_context() if os.environ.get("ACS_VALIDATE_CERTS", "true").lower() == "false" else None

ACTIONS = {
    "8ab0f199-4904-4808-9461-3501da1d1b77": "FAIL_KUBE_REQUEST_ENFORCEMENT",
    "fe9de18b-86db-44d5-a7c4-74173ccffe2e": "FAIL_DEPLOYMENT_CREATE_ENFORCEMENT",
}


def req(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        f"{ACS}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, context=CTX) as resp:
        return json.load(resp)


changed = False
for pid, action in ACTIONS.items():
    pol = req("GET", f"/v1/policies/{pid}")
    current = list(pol.get("enforcementActions") or [])
    if action in current:
        print(f"{pol['name']}: already has {action}")
        continue
    body = copy.deepcopy(pol)
    for k in list(body):
        if k.startswith("SORT"):
            body.pop(k)
    body["enforcementActions"] = current + [action]
    req("PUT", f"/v1/policies/{pid}", body)
    again = req("GET", f"/v1/policies/{pid}")
    if action not in (again.get("enforcementActions") or []):
        print(f"FAIL read-back {pol['name']}", file=sys.stderr)
        sys.exit(1)
    print(f"{pol['name']}: added {action}")
    changed = True
print("changed=true" if changed else "changed=false")
