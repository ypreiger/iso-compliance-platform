#!/usr/bin/env bash
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
log() { printf '[layer-01] %s\n' "$*"; }
fail() { printf '[layer-01] FAIL: %s\n' "$*" >&2; exit 1; }

command -v oc &>/dev/null || { log "SKIP (no oc)"; exit 0; }
oc whoami &>/dev/null || { log "SKIP (not logged in)"; exit 0; }

phase="$(oc get ns "${NS}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
[[ "${phase}" == "Active" ]] || fail "namespace ${NS} not Active (got: ${phase:-missing})"

oc get configmap iso-rhoai-endpoints -n "${NS}" &>/dev/null || fail "iso-rhoai-endpoints ConfigMap missing"
oc get sa iso-platform -n "${NS}" &>/dev/null || fail "iso-platform ServiceAccount missing"

log "OK"
