#!/usr/bin/env python3
"""Keeps the committed history files current. Standard library only; run by the monthly refit on a GitHub runner.

    python3 warwatch/backfill.py gdelt [MAX_DAYS]   # extend backtest/history/gdelt_country_day.csv.gz to yesterday (GDELT 1.0 daily files)

Phase 3 adds the other fast feeds here as they are back-filled.
"""
import csv
import datetime as dt
import gzip
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402
import sources as S  # noqa: E402


def gdelt(max_days=120, today=None, path=None):
    """Append the days after the file's last day, up to yesterday (at most max_days per run). A day GDELT has not published is skipped."""
    path = path or S.GDELT_HISTORY
    ccs = sorted({c for v in C.GDELT_CC.values() for c in v})
    rows = []
    if os.path.exists(path):
        with gzip.open(path, "rt", newline="") as f:
            rows = [r for r in csv.reader(f)]
    last = max((r[0] for r in rows), default="2017-12-31")
    d = dt.date.fromisoformat(last) + dt.timedelta(days=1)
    end = (today or dt.date.today()) - dt.timedelta(days=1)
    new, got = [], 0
    while d <= end and got < max_days:
        try:
            counts = S.gdelt_day(d, set(ccs))
        except RuntimeError as e:
            print("skip", d, str(e)[:80])
            d += dt.timedelta(days=1)
            continue
        for cc in ccs:
            for root in S.GDELT_ROOTS + ("all",):
                new.append([d.isoformat(), cc, root, str(counts.get((cc, root), 0))])
        got += 1
        d += dt.timedelta(days=1)
    if new:
        with gzip.open(path, "wt", newline="") as f:
            csv.writer(f).writerows(rows + new)
    S._GH.clear()
    print(f"gdelt: added {got} days" + (f" through {new[-1][0]}" if new else ""))
    return got


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "gdelt":
        gdelt(int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    else:
        sys.exit(__doc__)
