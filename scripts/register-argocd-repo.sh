#!/usr/bin/env bash
# Register GitHub repo with Argo CD (private repo + LFS).
set -euo pipefail

REPO_URL="${ISO_GIT_REPO:-https://github.com/ypreiger/iso-compliance-platform.git}"
NS="${ISO_GITOPS_NAMESPACE:-openshift-gitops}"
SECRET_NAME="${ISO_ARGO_REPO_SECRET:-iso-compliance-platform-repo}"

: "${GITHUB_TOKEN:?Set GITHUB_TOKEN (PAT with repo read)}"

oc create secret generic "${SECRET_NAME}" \
  -n "${NS}" \
  --from-literal=type=git \
  --from-literal=url="${REPO_URL}" \
  --from-literal=password="${GITHUB_TOKEN}" \
  --from-literal=username=git \
  --dry-run=client -o yaml | oc apply -f -

oc label secret "${SECRET_NAME}" -n "${NS}" \
  argocd.argoproj.io/secret-type=repository --overwrite

echo "Registered ${REPO_URL} as ${SECRET_NAME} in ${NS}"
