#!/usr/bin/env bash
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
JOB="${ISO_RAG_JOB_NAME:-iso-rag-populate}"
log() { printf '[layer-04] %s\n' "$*"; }
fail() { printf '[layer-04] FAIL: %s\n' "$*" >&2; exit 1; }

command -v oc &>/dev/null || { log "SKIP (no oc)"; exit 0; }
oc whoami &>/dev/null || { log "SKIP (not logged in)"; exit 0; }

if ! oc get job "${JOB}" -n "${NS}" &>/dev/null; then
  fail "job ${JOB} not found"
fi

oc wait job/"${JOB}" -n "${NS}" --for=condition=complete --timeout=1800s || {
  oc logs "job/${JOB}" -n "${NS}" --all-containers=true --tail=80 || true
  fail "RAG populate job did not complete"
}

# Optional DB check when psql available in cluster
if oc get deploy iso-postgres -n "${NS}" &>/dev/null; then
  count="$(oc exec deploy/iso-postgres -n "${NS}" -- bash -c \
    'PGPASSWORD="$POSTGRESQL_PASSWORD" psql -U "$POSTGRESQL_USER" -d "$POSTGRESQL_DATABASE" -tAc "SELECT COUNT(*) FROM rag_documents;"' 2>/dev/null || echo 0)"
  if [[ "${count}" =~ ^[0-9]+$ ]] && [[ "${count}" -gt 0 ]]; then
    log "rag_documents rows: ${count}"
  else
    log "WARN: rag_documents empty or table missing (schema may apply on first API start)"
  fi
fi

log "OK"
