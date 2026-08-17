#!/usr/bin/env python3
"""Remove only exclusions whose name starts with AAPEX- on allowlisted policies."""
from __future__ import annotations

import copy
import json
import os
import ssl
import urllib.request

ACS = os.environ["ACS_URL"].rstrip("/")
TOKEN = os.environ["ACS_TOKEN"]
CTX = ssl._create_unverified_context() if os.environ.get("ACS_VALIDATE_CERTS", "true").lower() == "false" else None
POLICY_IDS = [
    "8ab0f199-4904-4808-9461-3501da1d1b77",
    "fe9de18b-86db-44d5-a7c4-74173ccffe2e",
]


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
for pid in POLICY_IDS:
    pol = req("GET", f"/v1/policies/{pid}")
    ex = pol.get("exclusions") or []
    keep = [e for e in ex if not str(e.get("name") or "").startswith("AAPEX-")]
    if len(keep) == len(ex):
        print(f"{pol['name']}: no AAPEX exclusions")
        continue
    body = copy.deepcopy(pol)
    for k in list(body):
        if k.startswith("SORT"):
            body.pop(k)
    body["exclusions"] = keep
    req("PUT", f"/v1/policies/{pid}", body)
    print(f"{pol['name']}: removed {len(ex) - len(keep)} AAPEX exclusions")
    changed = True
print("changed=true" if changed else "changed=false")
