#!/usr/bin/env bash
# Bootstrap ISO platform on OpenShift (preserves claude-playground + MaaS).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NS="${ISO_APP_NAMESPACE:-iso-platform}"
GITOPS_NS="${ISO_GITOPS_NAMESPACE:-openshift-gitops}"
CLUSTER_DOMAIN="${ISO_CLUSTER_DOMAIN:-ocp.8mkwb.sandbox3159.opentlc.com}"

log() { printf '[bootstrap] %s\n' "$*"; }
fail() { printf '[bootstrap] ERROR: %s\n' "$*" >&2; exit 1; }

oc whoami &>/dev/null || fail "oc login required"

log "Ensuring namespace ${NS}"
oc get ns "${NS}" &>/dev/null || oc create ns "${NS}"

log "Syncing iso-secrets (DB + OpenAI same as playground)"
PG_PASS="$(oc get secret postgresql -n "${NS}" -o jsonpath='{.data.database-password}' 2>/dev/null | base64 -d || echo iso-secure-password)"
OPENAI_KEY="$(oc get secret openai-api-key -n "${NS}" -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d || true)"
JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"

oc create secret generic iso-secrets -n "${NS}" \
  --from-literal=DATABASE_PASSWORD="${PG_PASS}" \
  --from-literal=LLM_API_KEY="${OPENAI_KEY:-REPLACE_ME}" \
  --from-literal=JWT_SECRET="${JWT_SECRET}" \
  --from-literal=GOOGLE_CLIENT_SECRET="" \
  --from-literal=GIT_USERNAME="" \
  --from-literal=GIT_PASSWORD="" \
  --dry-run=client -o yaml | oc apply -f -

log "Applying GitOps overlay (catalog DB, redis, apps, builds)"
oc apply -k "${REPO_ROOT}/gitops/overlays/ocp-sandbox3159"

log "Registering Argo CD Application"
oc apply -f "${REPO_ROOT}/gitops/overlays/ocp-sandbox3159/application.yaml"

build_local() {
  local bc="$1" dir="$2"
  log "Build ${bc} from ${dir} (binary)"
  oc patch "bc/${bc}" -n "${NS}" --type=merge \
    -p='{"spec":{"source":{"type":"Binary","git":null,"contextDir":null}}}' 2>/dev/null || true
  oc start-build "bc/${bc}" --from-dir="${REPO_ROOT}/${dir}" --wait -n "${NS}" || fail "build ${bc} failed"
}

build_local iso-api apps/iso-api
build_local iso-web apps/iso-web
build_local iso-docgen services/docgen
log "Build rag-iso from repo root (bundled RAG corpus)"
oc patch bc/rag-iso -n "${NS}" --type=merge \
  -p='{"spec":{"source":{"type":"Binary","git":null,"contextDir":null},"strategy":{"dockerStrategy":{"dockerfilePath":"services/rag-iso/Containerfile"}}}}' 2>/dev/null || true
oc start-build bc/rag-iso --from-dir="${REPO_ROOT}" --wait -n "${NS}" || fail "build rag-iso failed"

log "Waiting for rollouts"
oc rollout status deploy/iso-api -n "${NS}" --timeout=300s || true
oc rollout status deploy/iso-web -n "${NS}" --timeout=300s || true
oc rollout status deploy/iso-docgen -n "${NS}" --timeout=300s || true

log "Verify playground still up"
curl -sf "https://claude-playground-${NS}.apps.${CLUSTER_DOMAIN}/health" | grep -q healthy || log "WARN: playground health check"

log "Verify iso-api"
curl -sf "https://iso-api-${NS}.apps.${CLUSTER_DOMAIN}/health" | grep -q ok || log "WARN: iso-api not ready yet"

log "Run verification scripts"
bash "${SCRIPT_DIR}/verify-layer-01.sh" || true
bash "${SCRIPT_DIR}/verify-layer-02.sh" || true
bash "${SCRIPT_DIR}/verify-layer-03.sh" || true

log "Bootstrap complete"
log "  Playground: https://claude-playground-${NS}.apps.${CLUSTER_DOMAIN}"
log "  ISO Web:    https://iso-web-${NS}.apps.${CLUSTER_DOMAIN}"
log "  ISO API:    https://iso-api-${NS}.apps.${CLUSTER_DOMAIN}"
log "  MaaS:       https://maas.apps.${CLUSTER_DOMAIN}/maas-api/v1/models"
