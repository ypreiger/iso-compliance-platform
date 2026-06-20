#!/usr/bin/env bash
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
log() { printf '[layer-03] %s\n' "$*"; }
fail() { printf '[layer-03] FAIL: %s\n' "$*" >&2; exit 1; }

command -v oc &>/dev/null || { log "SKIP (no oc)"; exit 0; }
oc whoami &>/dev/null || { log "SKIP (not logged in)"; exit 0; }

wait_ready() {
  oc wait deploy/"$1" -n "${NS}" --for=condition=Available --timeout=600s
}

wait_ready iso-api
wait_ready iso-web

api_host="$(oc get route iso-api -n "${NS}" -o jsonpath='{.spec.host}' 2>/dev/null || true)"
web_host="$(oc get route iso-web -n "${NS}" -o jsonpath='{.spec.host}' 2>/dev/null || true)"

if [[ -n "${api_host}" ]]; then
  code="$(curl -sk -o /dev/null -w '%{http_code}' "https://${api_host}/health" || echo 000)"
  [[ "${code}" == "200" ]] || fail "iso-api /health returned ${code}"
fi

if [[ -n "${web_host}" ]]; then
  code="$(curl -sk -o /dev/null -w '%{http_code}' "https://${web_host}/" || echo 000)"
  [[ "${code}" == "200" ]] || fail "iso-web returned ${code}"
fi

log "OK"
