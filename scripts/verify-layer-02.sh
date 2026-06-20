#!/usr/bin/env bash
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
log() { printf '[layer-02] %s\n' "$*"; }
fail() { printf '[layer-02] FAIL: %s\n' "$*" >&2; exit 1; }

command -v oc &>/dev/null || { log "SKIP (no oc)"; exit 0; }
oc whoami &>/dev/null || { log "SKIP (not logged in)"; exit 0; }

wait_ready() {
  oc wait deploy/"$1" -n "${NS}" --for=condition=Available --timeout="${1:+600}s" 2>/dev/null || \
    oc wait deploy/"$1" -n "${NS}" --for=condition=Available --timeout=600s
}

if oc get deploy iso-postgres -n "${NS}" &>/dev/null; then
  wait_ready iso-postgres
elif oc get dc postgresql -n "${NS}" &>/dev/null; then
  oc get pods -n "${NS}" -l deploymentconfig=postgresql --no-headers | grep -q Running || fail "catalog postgresql not Running"
  log "catalog postgresql Running"
else
  fail "no postgres (iso-postgres or catalog postgresql)"
fi

wait_ready iso-redis

bound="$(oc get pvc iso-rag-data -n "${NS}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
[[ "${bound}" == "Bound" ]] || fail "iso-rag-data PVC not Bound"

log "OK"
