"""Validate that indexed RAG chunks faithfully represent the imported clauses.

After each import we:
  1. Sample up to N clauses from iso_clause_text.
  2. For each clause, search rag_documents for its clause_id.
  3. Check that key phrases from the stored body appear in the retrieved chunk.
  4. Compute a hit_rate and return a structured ValidationReport.

The report is stored in corpus_documents.metadata so it is visible in the UI.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ClauseValidation:
    clause_id: str
    title: str
    body_length: int
    found_in_rag: bool
    phrases_checked: int
    phrases_hit: int
    sample_phrase: str = ""


@dataclass
class ValidationReport:
    standard: str
    language: str
    total_clauses: int
    sampled: int
    rag_hit_rate: float          # 0.0–1.0  fraction of sampled clauses found in RAG
    phrase_hit_rate: float       # 0.0–1.0  fraction of key phrases found in matched chunks
    details: list[ClauseValidation] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @property
    def passed(self) -> bool:
        return self.rag_hit_rate >= 0.8 and self.phrase_hit_rate >= 0.7


# ── helpers ────────────────────────────────────────────────────────────────

_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "to", "is", "be", "are", "was",
    "were", "that", "this", "with", "for", "on", "at", "by", "from", "its",
    "shall", "not", "may", "can", "has", "have", "been", "being", "will",
    "which", "it", "as", "if", "any", "all", "each", "their", "where", "when",
}


def _key_phrases(body: str, n: int = 4) -> list[str]:
    """Pick n distinctive phrases (2-word bigrams) from clause body."""
    words = re.findall(r"[A-Za-z\u0590-\u05FF]{4,}", body.lower())
    words = [w for w in words if w not in _STOP]
    bigrams: list[str] = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    # Prefer longer / less common bigrams
    bigrams = list(dict.fromkeys(bigrams))  # dedupe order-preserving
    return bigrams[:n]


def _rag_content_for_clause(conn: Any, *, standard: str, language: str, clause_id: str) -> str:
    """Fetch all RAG chunks for a specific clause and join them."""
    from app.iso.rag_index import LEGACY_COLLECTION_ID, collection_id_for_standard, normalize_standard_id

    std = normalize_standard_id(standard)
    coll = collection_id_for_standard(std)
    rows = conn.execute(
        """
        SELECT content FROM rag_documents
        WHERE (
                collection_id = %s
             OR (collection_id = %s AND metadata->>'standard' = %s)
              )
          AND metadata->>'standard' = %s
          AND metadata->>'language' = %s
          AND metadata->>'clause_id' = %s
        ORDER BY chunk_index
        """,
        (coll, LEGACY_COLLECTION_ID, std, std, language, clause_id),
    ).fetchall()
    return " ".join(r["content"] for r in rows).lower()


# ── public API ─────────────────────────────────────────────────────────────

def validate_import(
    conn: Any,
    *,
    standard: str,
    language: str,
    sample_n: int = 20,
) -> ValidationReport:
    """Run post-import validation; return a ValidationReport."""
    # Count total clauses
    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM iso_clause_text WHERE standard = %s AND language = %s",
        (standard, language),
    ).fetchone()
    total = int(total_row["c"]) if total_row else 0

    if total == 0:
        return ValidationReport(
            standard=standard,
            language=language,
            total_clauses=0,
            sampled=0,
            rag_hit_rate=0.0,
            phrase_hit_rate=0.0,
        )

    # Sample clauses (every n-th so we spread across the standard)
    rows = conn.execute(
        """
        SELECT clause_id, title, body
        FROM iso_clause_text
        WHERE standard = %s AND language = %s
          AND trim(body) != ''
        ORDER BY sort_order, clause_id
        """,
        (standard, language),
    ).fetchall()

    from app.db import rows_to_list
    all_clauses = rows_to_list(rows)
    step = max(1, len(all_clauses) // sample_n)
    sample = all_clauses[::step][:sample_n]

    details: list[ClauseValidation] = []
    rag_hits = 0
    phrase_total = 0
    phrase_hits = 0

    for row in sample:
        cid = row["clause_id"]
        body = row["body"] or ""
        rag_text = _rag_content_for_clause(
            conn, standard=standard, language=language, clause_id=cid
        )
        found = bool(rag_text)
        rag_hits += int(found)

        phrases = _key_phrases(body)
        p_hits = 0
        sample_phrase = ""
        if found and phrases:
            for phrase in phrases:
                if phrase in rag_text:
                    p_hits += 1
                    if not sample_phrase:
                        sample_phrase = phrase
            phrase_total += len(phrases)
            phrase_hits += p_hits

        details.append(
            ClauseValidation(
                clause_id=cid,
                title=row.get("title", ""),
                body_length=len(body),
                found_in_rag=found,
                phrases_checked=len(phrases),
                phrases_hit=p_hits,
                sample_phrase=sample_phrase,
            )
        )

    n = len(sample)
    rag_rate = rag_hits / n if n else 0.0
    phrase_rate = phrase_hits / phrase_total if phrase_total else 0.0

    return ValidationReport(
        standard=standard,
        language=language,
        total_clauses=total,
        sampled=n,
        rag_hit_rate=round(rag_rate, 3),
        phrase_hit_rate=round(phrase_rate, 3),
        details=details,
    )
