#!/usr/bin/env python3
"""History back-fills for the leading feeds the live build only keeps for 1-150 days (methodology review, phase 3).

    python3 backfill/backfill.py fred
    python3 backfill/backfill.py firms THEATRE [--start D --end D]
    python3 backfill/backfill.py gfw   THEATRE [--start D --end D]
    python3 backfill/backfill.py nga   [--start D --end D]
    python3 backfill/backfill.py adsb  [--start D --end D --step N]
    python3 backfill/backfill.py pla   [--start D --end D]
    python3 backfill/backfill.py wiki  [--start D --end D]     # Wikipedia page views per theatre
    python3 backfill/backfill.py forecasts                     # ConflictForecast and VIEWS monthly vintages
    python3 backfill/backfill.py gdeltwide [--start D --end D] # wider GDELT event types and dyads per theatre
    python3 backfill/backfill.py senkaku                       # Japan Coast Guard Senkaku vessel counts (monthly PDFs, text kept)
    python3 backfill/backfill.py state THEATRE[,THEATRE...] [--start D --end D]
    python3 backfill/backfill.py merge       # fold ADS-B quarter shards into data/
    python3 backfill/backfill.py coverage

Output: backfill/data/<series>.csv (date,value). Nothing here changes the live score; see backfill/README.md.
"""
import argparse
import datetime as dt
import os
import sys

import common as K


def date(s):
    return dt.date.fromisoformat(s)


def need(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"{name} is not set")
    return v


def cmd_coverage():
    rows = []
    for f in sorted(os.listdir(K.DATA)) if os.path.isdir(K.DATA) else []:
        if f.endswith(".csv"):
            d = K.load(f[:-4])
            if d:
                ks = sorted(d)
                vals = list(d.values())
                rows.append((f[:-4], len(d), ks[0], ks[-1], sum(1 for v in vals if v) / len(vals)))
    out = ["# Back-fill coverage", "", "Written by `backfill.py coverage`. `nonzero` is the share of days with a value above zero (a series that is all zeros cannot be tested).", "",
           "| series | days | first | last | nonzero |", "|---|---:|---|---|---:|"]
    out += [f"| {s} | {n} | {a} | {b} | {z:.0%} |" for s, n, a, b, z in rows]
    open(os.path.join(K.HERE, "COVERAGE.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))


def cmd_merge():
    """Fold backfill/shards/*/ (one dir per ADS-B quarter) into backfill/data/ and remove the shards."""
    import shutil
    base = os.path.join(K.HERE, "shards")
    out = os.path.join(K.HERE, "data")
    os.makedirs(out, exist_ok=True)
    for sh in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        d = os.path.join(base, sh)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".csv"):
                continue
            cur = {}
            for p in (os.path.join(out, f), os.path.join(d, f)):
                cur.update(K.read_csv(p))
            K.write_csv(os.path.join(out, f), cur)
        shutil.rmtree(d)
        print("merged", sh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--start", type=date, default=K.START)
    ap.add_argument("--end", type=date, default=K.YDAY)
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args()
    if a.cmd in ("firms", "gfw", "nga"):
        import sources_fast as F
    if a.cmd == "fred":
        import sources_fast as F
        F.cmd_fred(need("FRED_API_KEY"))
    elif a.cmd == "firms":
        F.cmd_firms(need("FIRMS_MAP_KEY"), a.arg, a.start, a.end)
    elif a.cmd == "gfw":
        F.cmd_gfw(need("GFW_TOKEN"), a.arg, a.start, a.end)
    elif a.cmd == "nga":
        F.cmd_nga(a.start, a.end)
    elif a.cmd == "adsb":
        import sources_adsb as A
        A.cmd_adsb(max(a.start, dt.date(2022, 1, 1)), a.end, a.step, os.environ.get("GITHUB_TOKEN"))
    elif a.cmd == "pla":
        import sources_slow as L
        L.cmd_pla(max(a.start, dt.date(2020, 1, 1)), a.end)
    elif a.cmd == "wiki":
        import sources_wiki as W
        W.cmd_wiki(a.start, a.end)
    elif a.cmd == "forecasts":
        import sources_forecasts as O
        for f in (O.cmd_conflictforecast, O.cmd_views):
            try:
                f()
            except Exception as e:
                K.log("::warning::", f.__name__, "failed:", str(e)[:200])
    elif a.cmd == "senkaku":
        import sources_senkaku as J
        J.cmd_senkaku()
    elif a.cmd == "gdeltwide":
        import sources_gdelt as G
        G.cmd_gdeltwide(a.start, min(a.end, K.YDAY))
    elif a.cmd == "state":
        import sources_slow as L
        L.cmd_state(a.arg.split(","), a.start, a.end)
    elif a.cmd == "merge":
        cmd_merge()
    elif a.cmd == "coverage":
        cmd_coverage()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
