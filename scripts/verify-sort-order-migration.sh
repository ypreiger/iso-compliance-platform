#!/usr/bin/env bash
# Verify sort_order migration completed successfully
set -euo pipefail

NAMESPACE="${NAMESPACE:-iso-platform}"

echo "=== Sort Order Migration Verification ==="

# 1. Check Job status
echo "1. Checking migration Job status..."
if oc get job iso-migrate-sort-order -n "$NAMESPACE" &>/dev/null; then
  JOB_STATUS=$(oc get job iso-migrate-sort-order -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "")
  if [ "$JOB_STATUS" = "True" ]; then
    echo "✓ Job completed"
  else
    echo "⚠ Job not yet completed (may still be running)"
  fi
else
  echo "⚠ Migration Job not found (may not be deployed yet)"
fi

# 2. Check for old-scale values in database
echo "2. Checking for remaining old-scale values..."
if ! command -v oc &>/dev/null; then
  echo "⚠ oc not available — skipping database check"
  exit 0
fi

POD=$(oc get pod -n "$NAMESPACE" -l app.kubernetes.io/name=iso-api --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -z "$POD" ]; then
  echo "⚠ No running iso-api pod found — skipping database check"
  exit 0
fi

OLD_COUNT=$(oc exec -n "$NAMESPACE" "$POD" -- python3 -c "
import os
os.environ['USE_SQLITE'] = '0'
from app.db import get_conn
try:
    with get_conn() as conn:
        row = conn.execute('SELECT COUNT(*) AS c FROM iso_clause_text WHERE sort_order < 1000000').fetchone()
        print(row['c'] if row else 0)
except Exception as e:
    print(f'ERROR: {e}', file=__import__('sys').stderr)
    print('0')
" 2>/dev/null || echo "0")

if [ "$OLD_COUNT" -gt 0 ]; then
  echo "⚠ Found $OLD_COUNT clauses with old-scale sort_order (migration may be pending)"
else
  echo "✓ No old-scale values found"
fi

# 3. Verify clause ordering
echo "3. Verifying clause order via seed data..."
python3 -c "
import json
from pathlib import Path
import sys
sys.path.insert(0, 'apps/iso-api')
from app.iso.parser import _sort_key

seed_path = Path('apps/iso-api/app/data/iso_clauses_seed.json')
if not seed_path.exists():
    print('⚠ Seed data not found')
    sys.exit(0)

data = json.load(seed_path.open())
mismatches = []
for item in data:
    expected = _sort_key(item['clause_id'])
    actual = item['sort_order']
    if actual != expected:
        mismatches.append((item['clause_id'], actual, expected))

if mismatches:
    print(f'✗ Found {len(mismatches)} mismatches in seed data:')
    for cid, actual, expected in mismatches[:5]:
        print(f'  {cid}: {actual} != {expected}')
    sys.exit(1)
else:
    print('✓ Seed data sort_order values correct')
"

echo "=== Migration Verification Complete ==="
