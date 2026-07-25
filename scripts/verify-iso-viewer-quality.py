#!/usr/bin/env python3
"""Verify ISO EN/HE viewer data quality (intro, contamination, titles, bodies).

Run inside iso-api pod or locally with DB env:
  PYTHONPATH=apps/iso-api python3 scripts/verify-iso-viewer-quality.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "iso-api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import get_conn  # noqa: E402
from app.iso.parser import normalize_hebrew_body  # noqa: E402
from app.routes.iso_text import _build_clause_list, _load_language_map  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    with get_conn() as conn:
        en_map = _load_language_map(conn, "ISO9001", "en")
        he_map = _load_language_map(conn, "ISO9001", "he")

    en = _build_clause_list("ISO9001", "en", en_map, he_map)
    he = _build_clause_list("ISO9001", "he", he_map, en_map)

    check("EN clause count >= 80", len(en) >= 80, f"count={len(en)}")
    check("HE clause count >= 80", len(he) >= 80, f"count={len(he)}")

    en_by = {c["clause_id"]: c for c in en}
    he_by = {c["clause_id"]: c for c in he}

    check("EN has Introduction (0)", "0" in en_by, en_by.get("0", {}).get("title", "missing"))
    check("EN 0 title is Introduction", en_by.get("0", {}).get("title") == "Introduction")
    check("EN has 0.1", "0.1" in en_by)
    check("EN first clause is intro", bool(en) and en[0]["clause_id"] in {"0", "0.1"},
          en[0]["clause_id"] if en else "empty")

    check("HE has מבוא (0)", "0" in he_by, he_by.get("0", {}).get("title", "missing"))
    check("HE 0 title is מבוא", he_by.get("0", {}).get("title") == "מבוא")
    check("HE 0.1 title is כללי", he_by.get("0.1", {}).get("title") == "כללי")
    check("HE 5.1.1 title is כללי", he_by.get("5.1.1", {}).get("title") == "כללי")
    check("HE 5.1.2 has customer-focus title", "לקוח" in (he_by.get("5.1.2", {}).get("title") or ""))

    en_he = [
        c["clause_id"]
        for c in en
        if re.search(r"[\u0590-\u05FF]", (c.get("title") or "") + (c.get("text") or ""))
    ]
    check("EN has no Hebrew contamination", not en_he, f"ids={en_he[:8]}")

    he_fallback = [c["clause_id"] for c in he if c.get("fallback")]
    check("HE has no cross-language fallback", not he_fallback, f"ids={he_fallback[:8]}")

    tokenized = []
    for c in he:
        text = c.get("text") or ""
        if not text or len(text) < 80:
            continue
        paras = [p for p in text.split("\n\n") if p.strip()]
        if len(paras) >= 8 and sum(1 for p in paras if len(p.split()) <= 2) / len(paras) > 0.6:
            tokenized.append(c["clause_id"])
    check("HE bodies not tokenized into many tiny paragraphs", not tokenized, f"ids={tokenized[:10]}")

    sample = he_by.get("0", {}).get("text") or ""
    check("HE intro body non-empty", len(sample) > 100, f"len={len(sample)}")
    check(
        "HE intro body has spaces (joined words)",
        " " in sample and sample.count("\n\n") < 30,
        f"newlines_dbl={sample.count(chr(10)+chr(10))} chars={len(sample)}",
    )

    en_l3 = sum(1 for c in en if c["clause_id"].count(".") == 2)
    he_l3 = sum(1 for c in he if c["clause_id"].count(".") == 2)
    check("EN level-3 >= 30", en_l3 >= 30, f"count={en_l3}")
    check("HE level-3 >= 30", he_l3 >= 30, f"count={he_l3}")

    bad_titles = [
        f"{c['clause_id']}:{c['title'][:40]}"
        for c in he
        if len((c.get("title") or "")) > 60
        or (c.get("title") or "").startswith("הערה")
        or (c.get("title") or "").startswith("( הערה")
    ]
    check("HE long body-as-title count == 0", not bad_titles, f"samples={bad_titles[:5]}")

    tok = "אימוץ\n\nמערכת\n\nניהול"
    check("normalize_hebrew_body joins tokens", "אימוץ מערכת ניהול" in normalize_hebrew_body(tok))

    failed = sum(1 for _, ok, _ in CHECKS if not ok)
    print(f"\nRESULT: {len(CHECKS) - failed}/{len(CHECKS)} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
