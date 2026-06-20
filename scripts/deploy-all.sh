#!/usr/bin/env bash
# One-click GitOps deploy: register App-of-Apps and sync layers 1–4.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ISO_GITOPS_NAMESPACE="${ISO_GITOPS_NAMESPACE:-openshift-gitops}"
ISO_APP_NAMESPACE="${ISO_APP_NAMESPACE:-iso-platform}"
MAX_LAYER=4
SKIP_RAG=0
VERIFY_ONLY=0
DRY_RUN=()

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

  --verify-only     Run verification scripts only (no oc apply)
  --layer N         Stop after layer N (1–4)
  --skip-rag        Deploy layers 1–3 only
  --dry-run         oc apply --dry-run=client
  -h, --help        This help

Environment:
  ISO_GITOPS_NAMESPACE   (default: openshift-gitops)
  ISO_APP_NAMESPACE      (default: iso-platform)
  ISO_CLUSTER_DOMAIN     Optional; patches LLM/route placeholders
EOF
}

while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --verify-only) VERIFY_ONLY=1 ;;
    --skip-rag) SKIP_RAG=1; MAX_LAYER=3 ;;
    --layer)
      shift
      MAX_LAYER="${1:?--layer requires number}"
      ;;
    --dry-run) DRY_RUN=(--dry-run=client) ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

log() { printf '[deploy-all] %s\n' "$*"; }
fail() { printf '[deploy-all] ERROR: %s\n' "$*" >&2; exit 1; }

require_oc() {
  command -v oc &>/dev/null || fail "oc not in PATH"
  oc whoami &>/dev/null || fail "not logged in — run oc login first"
}

run_verify() {
  local script="$1"
  [[ -x "${SCRIPT_DIR}/${script}" ]] || fail "missing ${script}"
  bash "${SCRIPT_DIR}/${script}"
}

if [[ "${VERIFY_ONLY}" -eq 1 ]]; then
  run_verify verify-preflight.sh
  run_verify verify-layer-01.sh
  [[ "${MAX_LAYER}" -ge 2 ]] && run_verify verify-layer-02.sh
  [[ "${MAX_LAYER}" -ge 3 ]] && run_verify verify-layer-03.sh
  [[ "${MAX_LAYER}" -ge 4 && "${SKIP_RAG}" -eq 0 ]] && run_verify verify-layer-04.sh
  log "verify-only: OK"
  exit 0
fi

require_oc
run_verify verify-preflight.sh

log "Registering App-of-Apps in ${ISO_GITOPS_NAMESPACE} ..."
oc apply "${DRY_RUN[@]}" -f "${REPO_ROOT}/gitops/root/application.yaml"

apply_layer() {
  local n="$1"
  local path
  path="$(find "${REPO_ROOT}/gitops/layers" -maxdepth 1 -type d -name "$(printf '%02d' "${n}")-*" | head -1)"
  [[ -n "${path}" ]] || fail "layer ${n} directory not found"
  log "Applying layer ${n}: ${path}"
  oc apply "${DRY_RUN[@]}" -k "${path}"
}

if [[ ${#DRY_RUN[@]} -eq 0 ]]; then
  for layer in 1 2 3; do
    [[ "${layer}" -le "${MAX_LAYER}" ]] || break
    apply_layer "${layer}"
    run_verify "verify-layer-0${layer}.sh" || log "WARN: layer ${layer} verify not yet green (Argo may still be syncing)"
  done
  if [[ "${MAX_LAYER}" -ge 4 && "${SKIP_RAG}" -eq 0 ]]; then
    apply_layer 4
    run_verify verify-layer-04.sh || log "WARN: RAG job may still be running"
  fi
else
  for layer in 1 2 3 4; do
    [[ "${layer}" -le "${MAX_LAYER}" ]] || break
    [[ "${layer}" -eq 4 && "${SKIP_RAG}" -eq 1 ]] && break
    apply_layer "${layer}"
  done
fi

log "Done. Argo CD will reconcile child Applications from gitops/root/."
log "Full verify: ./scripts/verify-all.sh"
