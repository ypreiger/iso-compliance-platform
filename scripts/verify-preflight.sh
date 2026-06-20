#!/usr/bin/env bash
set -euo pipefail

ISO_GITOPS_NAMESPACE="${ISO_GITOPS_NAMESPACE:-openshift-gitops}"

log() { printf '[preflight] %s\n' "$*"; }
fail() { printf '[preflight] FAIL: %s\n' "$*" >&2; exit 1; }

command -v oc &>/dev/null || fail "oc not in PATH"
oc whoami &>/dev/null || fail "oc login required"

log "user=$(oc whoami) server=$(oc whoami --show-server)"

oc get crd applications.argoproj.io &>/dev/null || \
  fail "Argo CD Application CRD missing — install OpenShift GitOps"

if ! oc get ns "${ISO_GITOPS_NAMESPACE}" &>/dev/null; then
  fail "namespace ${ISO_GITOPS_NAMESPACE} not found"
fi

log "OK"
