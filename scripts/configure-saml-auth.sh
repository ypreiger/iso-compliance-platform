#!/usr/bin/env bash
# Apply Google Workspace SAML settings to the OpenShift cluster.
set -euo pipefail

NS="${ISO_APP_NAMESPACE:-iso-platform}"
ISO_WEB_URL="${ISO_WEB_URL:-https://iso-web-iso-platform.apps.ocp.8mkwb.sandbox3159.opentlc.com}"
SAML_IDP_ENTITY_ID="${SAML_IDP_ENTITY_ID:-https://accounts.google.com/o/saml2?idpid=C03huz8l6}"
SAML_IDP_SSO_URL="${SAML_IDP_SSO_URL:-https://accounts.google.com/o/saml2/idp?idpid=C03huz8l6}"
SAML_SP_ENTITY_ID="${SAML_SP_ENTITY_ID:-${ISO_WEB_URL}/api/auth/saml/metadata}"
SAML_SP_ACS_URL="${SAML_SP_ACS_URL:-${ISO_WEB_URL}/api/auth/saml/acs}"
ADMIN_EMAILS="${ADMIN_EMAILS:-yaakov.preiger@think-21.com,yaakovpreiger@gmail.com,valeria.preiger@gmail.com}"

if [[ -z "${SAML_IDP_X509_CERT:-}" ]]; then
  SAML_IDP_X509_CERT="$(cat <<'EOF'
-----BEGIN CERTIFICATE-----
MIIDdDCCAlygAwIBAgIGAZ7mwj+9MA0GCSqGSIb3DQEBCwUAMHsxFDASBgNVBAoTC0dvb2dsZSBJ
bmMuMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3MQ8wDQYDVQQDEwZHb29nbGUxGDAWBgNVBAsTD0dv
b2dsZSBGb3IgV29yazELMAkGA1UEBhMCVVMxEzARBgNVBAgTCkNhbGlmb3JuaWEwHhcNMjYwNjIw
MjAzOTEwWhcNMzEwNjE5MjAzOTEwWjB7MRQwEgYDVQQKEwtHb29nbGUgSW5jLjEWMBQGA1UEBxMN
TW91bnRhaW4gVmlldzEPMA0GA1UEAxMGR29vZ2xlMRgwFgYDVQQLEw9Hb29nbGUgRm9yIFdvcmsx
CzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A
MIIBCgKCAQEArvzmCa7hXMlDjYzcqraEgu+h9/8snzmvWWObsg1i8U8iqOqrOvKusYSDUMyu+TNp
Z0VQ8qoowAeuJS3tvOMQE3M2lDpRs89R5oQ8qKmQRRiLfRr4KM8/hpE9vnEuje4iaY6A9kqWrL8o
dPYjlzP3+enavmS15IPbTVLuHAltiPragTwc06MVxBN49YQdtw/S8Vvp1Tutg0SMn4+204B+gTRy
FjAD0ryX1NLrXs/9eRNGDVDuS/8OSY+IKHiJJ1h3Q8I/7JbO+IcRuhYfr9P60439onnRBv+onuW6
wXk2+Nc8bU2HtWzg1jyATMYU0FDOweW9ykpDM4zPqK5lRjm4FQIDAQABMA0GCSqGSIb3DQEBCwUA
A4IBAQBXG1nvEbXDZDp3EbySR+dQEIAfXHH5PbktBIMp50Wwz6jATZIe7dJzDBNS4fVfqBrDD9L9
g/n5oVAcN/dKJHRiDBCHkiH/O0t1Zp6wompPNXuEdYQAL1ZrZEuBXvWcF012EJL4JACHU1AZ+7cQ
8Vr+x3D9IxCexzAUdjDJnH7PKITSVLy5y6jQKlLpOf3964W9sj1oL0KrNGw1/o7lpwnbhAon3CcC
8bqTBa2tse+k2QfuOyvlNj1WnxcCO6B683PCIyyPKbuR+E5T6JZsj6BVOsojaaMZsvARbcg9Q3S+
uER+eZrALNEwSZVZK+5QAiMjlocoPiY5iN7NRO2GG2eO
-----END CERTIFICATE-----
EOF
)"
fi

log() { printf '[saml-auth] %s\n' "$*"; }

oc whoami &>/dev/null || { echo "oc login required" >&2; exit 1; }

log "Patching iso-app-config (SAML IdP + SP URLs)"
oc patch configmap iso-app-config -n "${NS}" --type=merge -p "$(cat <<EOF
{
  "data": {
    "AUTH_DEV_MODE": "0",
    "ADMIN_EMAILS": "${ADMIN_EMAILS}",
    "ISO_WEB_URL": "${ISO_WEB_URL}",
    "SAML_IDP_ENTITY_ID": "${SAML_IDP_ENTITY_ID}",
    "SAML_IDP_SSO_URL": "${SAML_IDP_SSO_URL}",
    "SAML_SP_ENTITY_ID": "${SAML_SP_ENTITY_ID}",
    "SAML_SP_ACS_URL": "${SAML_SP_ACS_URL}",
    "GOOGLE_CLIENT_ID": ""
  }
}
EOF
)"

PG_PASS="$(oc get secret postgresql -n "${NS}" -o jsonpath='{.data.database-password}' 2>/dev/null | base64 -d || true)"
OPENAI_KEY="$(oc get secret openai-api-key -n "${NS}" -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d || true)"
JWT="$(oc get secret iso-secrets -n "${NS}" -o jsonpath='{.data.JWT_SECRET}' 2>/dev/null | base64 -d || openssl rand -hex 32)"

oc create secret generic iso-secrets -n "${NS}" \
  --from-literal=DATABASE_PASSWORD="${PG_PASS:-iso-secure-password}" \
  --from-literal=LLM_API_KEY="${OPENAI_KEY:-REPLACE_ME}" \
  --from-literal=JWT_SECRET="${JWT}" \
  --from-literal=SAML_IDP_X509_CERT="${SAML_IDP_X509_CERT}" \
  --from-literal=GIT_USERNAME="" \
  --from-literal=GIT_PASSWORD="" \
  --dry-run=client -o yaml | oc apply -f -

log "Restarting iso-api-orchestrator and iso-web"
oc apply -f "${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/gitops/layers/03-application/iso-api.yaml" -n "${NS}" >/dev/null 2>&1 || true
oc rollout restart deploy/iso-api-orchestrator deploy/iso-web -n "${NS}"
oc rollout status deploy/iso-api-orchestrator -n "${NS}" --timeout=300s

log "SAML ACS URL (register in Google Admin): ${SAML_SP_ACS_URL}"
log "SAML Entity ID: ${SAML_SP_ENTITY_ID}"
curl -sf "${ISO_WEB_URL}/api/auth/config" | grep -q '"saml_enabled":true'
log "saml_enabled=true"
