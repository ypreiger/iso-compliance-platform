#!/usr/bin/env bash
# Apply Google Sign-In (GIS) client ID for any Gmail / Google account login.
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
ISO_WEB_URL="${ISO_WEB_URL:-https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com}"
JS_ORIGIN="${ISO_WEB_URL}"
ADMIN_EMAILS="${ADMIN_EMAILS:-yaakov.preiger@think-21.com,yaakovpreiger@gmail.com,valeria.preiger@gmail.com}"

: "${GOOGLE_CLIENT_ID:?Set GOOGLE_CLIENT_ID to a *.apps.googleusercontent.com Web client ID}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"

log() { printf '[google-signin] %s\n' "$*"; }

oc whoami &>/dev/null || { echo "oc login required" >&2; exit 1; }

log "Patching iso-app-config (GOOGLE_CLIENT_ID, disable SAML)"
oc patch configmap iso-app-config -n "${NS}" --type=merge -p "$(cat <<EOF
{
  "data": {
    "AUTH_DEV_MODE": "0",
    "ADMIN_EMAILS": "${ADMIN_EMAILS}",
    "ISO_WEB_URL": "${ISO_WEB_URL}",
    "GOOGLE_CLIENT_ID": "${GOOGLE_CLIENT_ID}",
    "SAML_IDP_ENTITY_ID": "",
    "SAML_IDP_SSO_URL": ""
  }
}
EOF
)"

if [[ -n "${GOOGLE_CLIENT_SECRET}" ]]; then
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
fi

oc rollout restart deploy/iso-api-orchestrator deploy/iso-web -n "${NS}"
oc rollout status deploy/iso-api-orchestrator -n "${NS}" --timeout=300s

log "Register this Authorized JavaScript origin in GCP Console (APIs & Services → Credentials → OAuth client):"
log "  ${JS_ORIGIN}"
curl -sf "${ISO_WEB_URL}/api/auth/config" | grep -q "\"google_enabled\":true"
log "google_enabled=true (client_id=${GOOGLE_CLIENT_ID})"
