#!/usr/bin/env python3
"""Keeps the committed history files current. Standard library only; run by the monthly refit on a GitHub runner.

    python3 warwatch/backfill.py gdelt [MAX_DAYS]   # extend backtest/history/gdelt_country_day.csv.gz to yesterday (GDELT 1.0 daily files)
    python3 warwatch/backfill.py gdelt-add [CC,CC] START END   # countries added to config.GDELT_CC later: their days from START to END, one shard per year
    python3 warwatch/backfill.py gdelt-merge        # fold those shards into the history file

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


SHARDS = os.path.join(os.path.dirname(HERE), "backfill", "data", "gdelt_add")
ROOT_ORDER = {r: i for i, r in enumerate(S.GDELT_ROOTS + ("all",))}


def _rows(path):
    if not os.path.exists(path):
        return []
    with gzip.open(path, "rt", newline="") as f:
        return [r for r in csv.reader(f)]


def missing_codes(path=None):
    """Countries config.GDELT_CC watches that the history file has no rows for (added after it was built)."""
    have = {cc for cc, _ in S.gdelt_history()} if path is None else {r[1] for r in _rows(path)}
    return sorted({c for v in C.GDELT_CC.values() for c in v} - have)


def gdelt_add(codes, start, end, shard_dir=None, day_fn=None):
    """Read the daily files from start to end for the given countries only, into one shard per year
    (backfill/data/gdelt_add/<year>.csv.gz, the history file's columns). Days already in a shard are skipped, so a re-run resumes.
    A day GDELT never published is skipped, as in the history file."""
    shard_dir = shard_dir or SHARDS
    day_fn = day_fn or S.gdelt_day
    os.makedirs(shard_dir, exist_ok=True)
    got = 0
    for year in range(start.year, end.year + 1):
        path = os.path.join(shard_dir, f"{year}.csv.gz")
        rows = _rows(path)
        done = {(r[0], r[1]) for r in rows}
        d, last = max(start, dt.date(year, 1, 1)), min(end, dt.date(year, 12, 31))
        new = 0
        while d <= last:
            todo = [c for c in codes if (d.isoformat(), c) not in done]
            if todo:
                try:
                    counts = day_fn(d, set(todo))
                except RuntimeError as e:
                    print("skip", d, str(e)[:80], flush=True)
                    d += dt.timedelta(days=1)
                    continue
                rows += [[d.isoformat(), cc, root, str(counts.get((cc, root), 0))] for cc in todo for root in S.GDELT_ROOTS + ("all",)]
                new += 1
                if new % 30 == 0:
                    _write(path, rows)
                    print(year, d, new, "days", flush=True)
            d += dt.timedelta(days=1)
        _write(path, rows)
        got += new
        print(f"gdelt-add {year}: {new} new days", flush=True)
    return got


def _write(path, rows):
    rows = sorted(rows, key=lambda r: (r[0], r[1], ROOT_ORDER.get(r[2], 9)))
    with gzip.open(path, "wt", newline="") as f:
        csv.writer(f).writerows(rows)


def gdelt_merge(path=None, shard_dir=None):
    """Add the shards' rows to the history file for (day, country) pairs it lacks, up to its last day (later days come from the
    monthly extension, which reads every watched country). Re-running adds nothing."""
    path = path or S.GDELT_HISTORY
    shard_dir = shard_dir or SHARDS
    rows = _rows(path)
    have = {(r[0], r[1]) for r in rows}
    last = max(r[0] for r in rows)
    add = []
    for fn in sorted(os.listdir(shard_dir)) if os.path.isdir(shard_dir) else []:
        if fn.endswith(".csv.gz"):
            add += [r for r in _rows(os.path.join(shard_dir, fn)) if r[0] <= last and (r[0], r[1]) not in have]
    if add:
        _write(path, rows + add)
    S._GH.clear()
    print(f"gdelt-merge: added {len(add)} rows for {sorted({r[1] for r in add})}")
    return len(add)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "gdelt":
        gdelt(int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    elif cmd == "gdelt-add" and len(sys.argv) == 5:
        gdelt_add([c for c in sys.argv[2].split(",") if c] or missing_codes(), dt.date.fromisoformat(sys.argv[3]), dt.date.fromisoformat(sys.argv[4]))
    elif cmd == "gdelt-merge":
        gdelt_merge()
    else:
        sys.exit(__doc__)
