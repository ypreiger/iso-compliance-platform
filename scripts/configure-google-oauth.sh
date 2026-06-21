#!/usr/bin/env bash
# Apply Google OAuth credentials to the cluster (secret never committed).
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
REDIRECT_URI="${ISO_WEB_URL:-https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com}/auth/callback"
GCP_PROJECT="${GOOGLE_OAUTH_GCP_PROJECT:-iso-compliance-platform}"
OAUTH_CLIENT="${GOOGLE_OAUTH_CLIENT_NAME:-iso-compliance-web}"
CRED_NAME="${GOOGLE_OAUTH_CRED_NAME:-iso-web-cred}"

: "${GOOGLE_CLIENT_ID:=$(gcloud iam oauth-clients describe "${OAUTH_CLIENT}" --project="${GCP_PROJECT}" --location=global --format='value(clientId)')}"
: "${GOOGLE_CLIENT_SECRET:=$(gcloud iam oauth-clients credentials describe "${CRED_NAME}" --oauth-client="${OAUTH_CLIENT}" --project="${GCP_PROJECT}" --location=global --format='value(clientSecret)')}"

log() { printf '[google-oauth] %s\n' "$*"; }

oc whoami &>/dev/null || { echo "oc login required" >&2; exit 1; }

log "Patching iso-app-config (client id + AUTH_DEV_MODE=0)"
oc patch configmap iso-app-config -n "${NS}" --type=merge \
  -p "{\"data\":{\"GOOGLE_CLIENT_ID\":\"${GOOGLE_CLIENT_ID}\",\"AUTH_DEV_MODE\":\"0\",\"ISO_WEB_URL\":\"${ISO_WEB_URL:-https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com}\"}}"

PG_PASS="$(oc get secret postgresql -n "${NS}" -o jsonpath='{.data.database-password}' 2>/dev/null | base64 -d || true)"
OPENAI_KEY="$(oc get secret openai-api-key -n "${NS}" -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d || true)"
JWT="$(oc get secret iso-secrets -n "${NS}" -o jsonpath='{.data.JWT_SECRET}' 2>/dev/null | base64 -d || openssl rand -hex 32)"

oc create secret generic iso-secrets -n "${NS}" \
  --from-literal=DATABASE_PASSWORD="${PG_PASS:-iso-secure-password}" \
  --from-literal=LLM_API_KEY="${OPENAI_KEY:-REPLACE_ME}" \
  --from-literal=JWT_SECRET="${JWT}" \
  --from-literal=GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET}" \
  --from-literal=GIT_USERNAME="" \
  --from-literal=GIT_PASSWORD="" \
  --dry-run=client -o yaml | oc apply -f -

oc rollout restart deploy/iso-api-orchestrator -n "${NS}"
oc rollout status deploy/iso-api-orchestrator -n "${NS}" --timeout=120s

log "Redirect URI (must match GCP OAuth client): ${REDIRECT_URI}"
curl -sf "https://iso-api-orchestrator-${NS}.apps.${ISO_CLUSTER_DOMAIN:-ocp.8mkwb.sandbox3159.opentlc.com}/auth/config" | grep -q '"google_enabled":true'
log "google_enabled=true"
