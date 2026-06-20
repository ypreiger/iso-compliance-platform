#!/usr/bin/env bash
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
log() { printf '[layer-02] %s\n' "$*"; }
fail() { printf '[layer-02] FAIL: %s\n' "$*" >&2; exit 1; }

command -v oc &>/dev/null || { log "SKIP (no oc)"; exit 0; }
oc whoami &>/dev/null || { log "SKIP (not logged in)"; exit 0; }

wait_ready() {
  local kind="$1" name="$2" timeout="${3:-300}"
  oc wait "${kind}/${name}" -n "${NS}" --for=condition=Available --timeout="${timeout}s" 2>/dev/null || \
    oc wait "${kind}/${name}" -n "${NS}" --for=condition=Ready --timeout="${timeout}s"
}

wait_ready deploy iso-postgres 600
wait_ready deploy iso-redis 120

bound="$(oc get pvc iso-postgres-data -n "${NS}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
[[ "${bound}" == "Bound" ]] || fail "iso-postgres-data PVC not Bound"

bound="$(oc get pvc iso-rag-data -n "${NS}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
[[ "${bound}" == "Bound" ]] || fail "iso-rag-data PVC not Bound"

log "OK"
