#!/bin/bash
# Check current state of ISO clause data in database

set -e

echo "═══ ISO CLAUSE TEXT DATABASE CHECK ═══"
echo

# Database connection (adjust as needed)
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_USER="${DATABASE_USER:-iso}"
DB_NAME="${DATABASE_NAME:-iso}"

echo "Connecting to: $DB_HOST:$DB_PORT/$DB_NAME as $DB_USER"
echo

# Count by standard and language
echo "Clause counts by standard and language:"
PGPASSWORD="${DATABASE_PASSWORD:-iso}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
SELECT
    standard,
    language,
    COUNT(*) as clause_count,
    COUNT(CASE WHEN LENGTH(body) > 100 THEN 1 END) as good_bodies,
    COUNT(CASE WHEN LENGTH(body) = 0 THEN 1 END) as empty_bodies
FROM iso_clause_text
GROUP BY standard, language
ORDER BY standard, language;
EOF

echo
echo "Sample clause titles (first 5 from each standard/language):"
PGPASSWORD="${DATABASE_PASSWORD:-iso}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
SELECT
    standard,
    language,
    clause_id,
    LEFT(title, 50) as title,
    LENGTH(body) as body_len
FROM iso_clause_text
WHERE clause_id IN ('1', '4', '4.1', '5.1.1')
ORDER BY standard, language, clause_id;
EOF

echo
echo "Check for mixed language content (Hebrew chars in EN, Latin in HE):"
PGPASSWORD="${DATABASE_PASSWORD:-iso}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
-- Hebrew characters in English rows
SELECT
    'EN with Hebrew' as issue,
    standard,
    clause_id,
    LEFT(title, 60) as title
FROM iso_clause_text
WHERE language = 'en'
  AND title ~ '[א-ת]'
LIMIT 5;

-- English characters in Hebrew rows (excluding ISO, numbers)
SELECT
    'HE with English' as issue,
    standard,
    clause_id,
    LEFT(title, 60) as title
FROM iso_clause_text
WHERE language = 'he'
  AND title ~ '[A-Z][a-z]{3,}'
  AND title NOT LIKE '%ISO%'
LIMIT 5;
EOF

echo
echo "Done!"
