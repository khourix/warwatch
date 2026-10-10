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
    python3 backfill/backfill.py metaculus                     # Metaculus community forecasts on military questions (token)
    python3 backfill/backfill.py senkaku                       # Japan Coast Guard Senkaku vessel counts (monthly PDFs, text kept)
    python3 backfill/backfill.py alerts                        # Israel's attack waves since 2014, from the Home Front Command history mirror
    python3 backfill/backfill.py msa                           # China MSA military navigational warnings, every page of the list (about 600 requests)
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


def cmd_alerts():
    """tzeva_israel: attack waves in the last 7 days, from the open mirror of Home Front Command alerts (one CSV, about 65 MB)."""
    import urllib.request
    sys.path.insert(0, os.path.join(os.path.dirname(K.HERE), "warwatch"))
    import osint
    with urllib.request.urlopen(urllib.request.Request(osint.OREF_MIRROR, headers={"User-Agent": "warwatch-backfill"}), timeout=300) as r:
        text = r.read().decode("utf-8")
    waves = osint.alert_waves(osint.parse_oref_csv(text))
    if not waves:
        sys.exit("no alerts parsed from the mirror")
    pts = osint.weekly_waves(waves, waves[0].date() + dt.timedelta(days=7), waves[-1].date())
    K.log("alerts:", len(waves), "waves", waves[0].date(), "to", waves[-1].date(), "->", K.save("tzeva_israel", pts), "days")


def cmd_msa():
    """msa_<theatre>: China's military navigational warnings in the last 30 days, from every page of the MSA warning list."""
    import time
    sys.path.insert(0, os.path.join(os.path.dirname(K.HERE), "warwatch"))
    import extras
    rows, page, pages, oldest = {}, 1, 1, ""
    while page <= pages:
        for i in range(4):
            try:
                items, pages = extras.fetch_msa_page(page)
                break
            except Exception as e:
                K.log("page", page, "retry:", str(e)[:120])
                time.sleep(10 * (i + 1))
        else:
            sys.exit(f"MSA list failed at page {page}")
        for r in extras.parse_msa(items):
            rows[r[0]] = r
        oldest = str(items[-1].get("articlePublishTime") or "")[:10] if items else oldest
        if page % 50 == 0:
            K.log("page", page, "of", pages, "back to", oldest, len(rows), "military")
        page += 1
        time.sleep(0.3)
    first = dt.date.fromisoformat(oldest) + dt.timedelta(days=30)
    for th in extras.MSA_THEATRE:
        K.log("msa", th, K.save(f"msa_{th}", extras.msa_counts(list(rows.values()), th, first, K.YDAY)), "days from", first)


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
        import forecasts_compact
        forecasts_compact.main(O.RAW, O.OUT)
    elif a.cmd == "metaculus":
        import sources_metaculus as M
        M.cmd_metaculus(need("METACULUS_TOKEN"))
    elif a.cmd == "senkaku":
        import sources_senkaku as J
        J.cmd_senkaku()
    elif a.cmd == "gdeltwide":
        import sources_gdelt as G
        G.cmd_gdeltwide(a.start, min(a.end, K.YDAY))
    elif a.cmd == "state":
        import sources_slow as L
        L.cmd_state(a.arg.split(","), a.start, a.end)
    elif a.cmd == "alerts":
        cmd_alerts()
    elif a.cmd == "msa":
        cmd_msa()
    elif a.cmd == "merge":
        cmd_merge()
    elif a.cmd == "coverage":
        cmd_coverage()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
