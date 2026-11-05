#!/usr/bin/env python3
"""Folds the CrisisWatch issues recovered from the Wayback Machine (backtest/predstudy/data/crisiswatch) into the live archive
history/cache/crisiswatch.csv (month, list, slug), which the RSS feed alone fills only from October 2026. Keeps the four lists and drops
anchor text that isn't a country (podcast, op-ed and the like never match a theatre anyway). Idempotent.

    python3 backtest/predstudy/cw_backfill.py
"""
import csv
import gzip
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "warwatch"))
import predstudy as PS  # noqa: E402
import store  # noqa: E402

JUNK = {"podcast", "q&a", "op-ed", "commentary", "report", "briefing", "statement", "read-more", "crisiswatch"}


def main():
    with gzip.open(os.path.join(PS.CWDIR, "crisiswatch_wayback.csv.gz"), "rt", newline="") as f:
        rows = list(csv.DictReader(f))
    new = set()
    for r in rows:
        m = PS.cw_issue_month(r["month"])
        slug = r["entry"].strip().lower()
        if re.fullmatch(r"\d{4}-\d{2}-01", m) and r["list"] in ("alert", "deteriorated", "improved", "resolution") and slug not in JUNK \
                and re.fullmatch(r"[a-z0-9-]+", slug):
            new.add((m, r["list"], slug))
    kept = {tuple(r) for r in store.cache_rows("crisiswatch")}
    out = sorted(kept | new)
    store.cache_rows_save("crisiswatch", [list(r) for r in out])
    months = sorted({r[0] for r in out})
    print(f"crisiswatch archive: {len(kept)} rows before, {len(out)} after, {len(months)} issues, {months[0]} to {months[-1]}")


if __name__ == "__main__":
    main()
