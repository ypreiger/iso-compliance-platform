#!/usr/bin/env bash
# Local dry-run: Postgres + API tests + web build + smoke curls (no OpenShift).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON="${PYTHON:-/opt/miniconda3/bin/python3}"
if ! "$PYTHON" -m pytest --version &>/dev/null 2>&1; then
  PYTHON=python3
  for c in /opt/miniconda3/bin/python3 /opt/homebrew/bin/python3; do
    if "$c" -m pytest --version &>/dev/null 2>&1; then PYTHON="$c"; break; fi
  done
fi
export PYTHON

log() { printf '[dry-run] %s\n' "$*"; }
fail() { printf '[dry-run] FAIL: %s\n' "$*" >&2; exit 1; }

export PATH="/opt/homebrew/bin:${PATH:-}"

log "1/6 RAG local verify"
./scripts/verify-rag-local.sh

log "2/6 Start Postgres (docker compose)"
if command -v docker &>/dev/null; then
  docker compose up -d postgres
  for _ in $(seq 1 30); do
    docker compose exec -T postgres pg_isready -U iso &>/dev/null && break
    sleep 1
  done
else
  log "WARN: docker not available — API tests need Postgres on localhost:5432"
fi

log "3/6 Python tests"
"$PYTHON" -m pip install -q -r apps/iso-api/requirements.txt pytest pyyaml 2>/dev/null || true
export USE_SQLITE=1
export SQLITE_PATH="/tmp/iso-dry-run.db"
rm -f "${SQLITE_PATH}"
export AUTH_DEV_MODE=1
export ADMIN_EMAILS="yaakovpreiger@gmail.com,valeria.preiger@gmail.com"

PYTHONPATH=apps/iso-api:services/rag-iso "$PYTHON" -m pytest -q apps/iso-api/tests services/rag-iso/tests || fail "pytest failed"

log "4/6 API smoke (TestClient)"
PYTHONPATH=apps/iso-api "$PYTHON" - <<'PY' || fail "API smoke failed"
import os
os.environ["USE_SQLITE"] = "1"
os.environ["SQLITE_PATH"] = "/tmp/iso-dry-run-smoke.db"
os.environ["AUTH_DEV_MODE"] = "1"
os.environ["ADMIN_EMAILS"] = "yaakovpreiger@gmail.com,valeria.preiger@gmail.com"
if os.path.exists(os.environ["SQLITE_PATH"]):
    os.remove(os.environ["SQLITE_PATH"])
from fastapi.testclient import TestClient
from app.main import app
from app.db import ensure_schema
ensure_schema()
c = TestClient(app)
assert c.get("/health").json()["status"] == "ok"
t = c.post("/auth/dev-login", json={"email": "yaakovpreiger@gmail.com"}).json()["access_token"]
h = {"Authorization": f"Bearer {t}"}
assert c.get("/admin/users", headers=h).status_code == 200
assert c.get("/v1/iso/clauses?standard=ISO9001&language=he", headers=h).json()["clauses"]
print("smoke OK")
PY

log "5/6 iso-web build"
NPM="$(command -v npm || true)"
[[ -z "$NPM" && -x /opt/homebrew/bin/npm ]] && NPM=/opt/homebrew/bin/npm
if [[ -n "$NPM" ]]; then
  (cd apps/iso-web && "$NPM" install --silent && "$NPM" run build) || fail "web build failed"
else
  log "WARN: npm not found — skip web build (CI will build iso-web)"
fi

log "6/6 shellcheck + kustomize"
if command -v shellcheck &>/dev/null; then
  shellcheck scripts/*.sh
fi
if command -v kubectl &>/dev/null; then
  for d in gitops/layers/*/; do kubectl kustomize "$d" >/dev/null; done
fi

log "DRY-RUN OK"
