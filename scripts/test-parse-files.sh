#!/bin/bash
# Test parsing of ISO files to verify fixes work

set -e

echo "═══ ISO FILE PARSING TEST ═══"
echo
echo "This script tests the fixed parsing code on your ISO files."
echo "Point it to your ISO PDF/DOCX files and it will show parsing results."
echo

# Check if file path provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-iso-file.pdf|docx>"
    echo
    echo "Example:"
    echo "  $0 ~/Downloads/ISO-9001-2015-EN.pdf"
    echo "  $0 ~/Downloads/ISO-9001-2015-HE.docx"
    exit 1
fi

FILE_PATH="$1"

if [ ! -f "$FILE_PATH" ]; then
    echo "Error: File not found: $FILE_PATH"
    exit 1
fi

BASENAME=$(basename "$FILE_PATH")
echo "Testing file: $BASENAME"
echo

cd "$(dirname "$0")/.."

PYTHONPATH=apps/iso-api python3 << EOF
from pathlib import Path
from app.iso.clause_parse import parse_document_bytes

file_path = Path('$FILE_PATH')
print(f'Parsing: {file_path.name}')
print()

try:
    content = file_path.read_bytes()
    clauses = parse_document_bytes(content, filename=file_path.name)

    print(f'✓ Successfully parsed {len(clauses)} clauses')
    print()

    # Count by type
    good = sum(1 for c in clauses if len(c.body) > 100)
    partial = sum(1 for c in clauses if 0 < len(c.body) <= 100)
    empty = sum(1 for c in clauses if len(c.body) == 0)

    print(f'Quality breakdown:')
    print(f'  Good bodies (>100 chars):  {good} ({100*good//len(clauses)}%)')
    print(f'  Partial bodies (1-100):    {partial}')
    print(f'  Empty bodies:              {empty}')
    print()

    # Show first 10 clauses
    print('First 10 clauses:')
    for c in clauses[:10]:
        status = '✓' if len(c.body) > 100 else ('⚠' if len(c.body) > 0 else '✗')
        title = c.title[:55] if len(c.title) <= 55 else c.title[:52] + '...'
        print(f'  {status} {c.clause_id:8} │ {title:55} │ {len(c.body):4}')

    if len(clauses) > 10:
        print(f'  ... ({len(clauses) - 10} more clauses)')

    print()

    # Check for key clauses
    print('Key clauses check:')
    key_clauses = ['1', '4', '4.1', '4.2', '5.1.1', '7.1.5', '10.2']
    for cid in key_clauses:
        found = [c for c in clauses if c.clause_id == cid]
        if found:
            c = found[0]
            status = '✓' if len(c.body) > 80 else ('⚠' if len(c.body) > 0 else '✗')
            print(f'  {status} {c.clause_id:8} │ {c.title[:60]}')
        else:
            print(f'  ✗ {cid:8} │ NOT FOUND')

    print()

    # Show sample content from clause 4.1
    clause_4_1 = [c for c in clauses if c.clause_id == '4.1']
    if clause_4_1:
        c = clause_4_1[0]
        print('═══ Sample: Clause 4.1 ═══')
        print(f'Title: {c.title}')
        print(f'Body ({len(c.body)} chars):')
        print(c.body[:300])
        if len(c.body) > 300:
            print('...')

except Exception as e:
    print(f'✗ ERROR: {e}')
    import traceback
    traceback.print_exc()
    exit(1)

EOF

echo
echo "Done!"
