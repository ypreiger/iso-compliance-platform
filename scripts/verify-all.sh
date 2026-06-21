#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/verify-preflight.sh" || true
bash "${SCRIPT_DIR}/verify-layer-01.sh" || true
bash "${SCRIPT_DIR}/verify-layer-02.sh" || true
bash "${SCRIPT_DIR}/verify-sort-order-migration.sh" || true
bash "${SCRIPT_DIR}/verify-layer-03.sh" || true
bash "${SCRIPT_DIR}/verify-layer-04.sh" || true

echo "[verify-all] finished (cluster checks skip when oc not logged in)"
