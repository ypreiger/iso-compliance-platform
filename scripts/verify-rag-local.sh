#!/usr/bin/env bash
# Validate RAG tree locally (no cluster).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${REPO_ROOT}/RAG/manifest.yaml"

[[ -f "${MANIFEST}" ]] || { echo "missing ${MANIFEST}" >&2; exit 1; }

for dir in RAG-Standards RAG-Samples; do
  [[ -d "${REPO_ROOT}/RAG/${dir}" ]] || { echo "missing required RAG/${dir}" >&2; exit 1; }
  count="$(find "${REPO_ROOT}/RAG/${dir}" -type f ! -name '.DS_Store' | wc -l | tr -d ' ')"
  [[ "${count}" -gt 0 ]] || { echo "empty RAG/${dir}" >&2; exit 1; }
  echo "OK RAG/${dir} files=${count}"
done

if [[ -d "${REPO_ROOT}/RAG/RAG-Templates" ]]; then
  echo "OK RAG/RAG-Templates (optional)"
else
  echo "optional missing: RAG-Templates"
fi

# Rich validation when pytest deps available
if python3 -c "import yaml" 2>/dev/null; then
  PYTHONPATH="${REPO_ROOT}/services/rag-iso" python3 -c "
from pathlib import Path
from rag_iso.manifest import load_manifest, iter_seed_files
root = Path('${REPO_ROOT}') / 'RAG'
for c in load_manifest(root):
    print(f'manifest OK {c.id} files={len(iter_seed_files(c))}')
"
fi

echo "RAG local verify OK"
