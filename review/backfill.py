#!/usr/bin/env python3
"""Methodology review: back-fill long histories of the leading feeds that the live build only keeps for ~150 days,
so the review can test whether they rose before past wars and strikes. Public data only, standard library except h3.

    python3 review/backfill.py gdelt   SHARD NSHARDS   # GDELT 1.0 daily event files, 2018-01-01 .. yesterday
    python3 review/backfill.py gpsjam  SHARD NSHARDS   # gpsjam.org daily h3 files, 2022-02-14 .. yesterday
    python3 review/backfill.py polymarket              # resolved war/strike markets and their daily price history
    python3 review/backfill.py ooni                    # OONI anomaly counts per country-day
    python3 review/backfill.py gpr                     # Caldara-Iacoviello Geopolitical Risk index (daily + country monthly)
    python3 review/backfill.py ucdp                    # UCDP GED + candidate events -> fatalities per country-day (labels)
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "warwatch"))
import config as C  # noqa: E402

OUT = os.path.join(HERE, "data")
UA = {"User-Agent": "warwatch-review/0.1 (public-data research; github.com/khourix/warwatch)"}
YDAY = dt.date.today() - dt.timedelta(days=1)


def get(url, raw=False, timeout=120, retries=3):
    err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            err = e
        time.sleep(4 * (i + 1))
    raise RuntimeError(f"{err} @ {url[:90]}")


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def shard(seq, i, n):
    return [x for k, x in enumerate(seq) if k % n == i]


# ---------------------------------------------------------------- GDELT
ROOTS = {"13", "14", "15", "16", "17", "18", "19", "20"}   # threaten, protest, posture, reduce relations, coerce, assault, fight, mass violence


def cmd_gdelt(i, n):
    ccs = {c for v in C.GDELT_CC.values() for c in v} | {"RS", "CH", "US", "IZ", "SY", "SA", "TU", "GG", "AJ", "AM"}
    todo = shard(list(days(dt.date(2018, 1, 1), YDAY)), i, n)
    path = os.path.join(OUT, f"gdelt_{i:02d}.csv")
    done = set()
    if os.path.exists(path):
        done = {r[0] for r in csv.reader(open(path))}
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        for d in todo:
            if d.isoformat() in done:
                continue
            try:
                z = zipfile.ZipFile(io.BytesIO(get(f"http://data.gdeltproject.org/events/{d:%Y%m%d}.export.CSV.zip", raw=True)))
            except Exception as e:
                print("miss", d, str(e)[:80], flush=True)
                continue
            cnt, men, tot = {}, {}, {}
            for r in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"), delimiter="\t"):
                if len(r) <= 51:
                    continue
                cc = r[51]
                if cc not in ccs:
                    continue
                tot[cc] = tot.get(cc, 0) + 1
                if r[28] in ROOTS:
                    k = (cc, r[28])
                    cnt[k] = cnt.get(k, 0) + 1
                    try:
                        men[k] = men.get(k, 0) + int(r[31] or 0)
                    except ValueError:
                        pass
            for cc in sorted(ccs):
                w.writerow([d.isoformat(), cc, "all", tot.get(cc, 0), ""])
                for root in sorted(ROOTS):
                    w.writerow([d.isoformat(), cc, root, cnt.get((cc, root), 0), men.get((cc, root), 0)])
            f.flush()
            print("ok", d, flush=True)


# ---------------------------------------------------------------- GPSJam
def cmd_gpsjam(i, n):
    import h3
    cell = getattr(h3, "cell_to_latlng", None) or h3.h3_to_geo
    memo = {}
    boxes = dict(C.BOXES)
    path = os.path.join(OUT, f"gpsjam_{i:02d}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for d in shard(list(days(dt.date(2022, 2, 14), YDAY)), i, n):
            try:
                txt = get(f"https://gpsjam.org/data/{d.isoformat()}-h3_4.csv", raw=True).decode()
            except Exception as e:
                print("miss", d, str(e)[:80], flush=True)
                continue
            tot = {t: [0, 0] for t in boxes}
            for ln in txt.splitlines()[1:]:
                p = ln.split(",")
                if len(p) < 3:
                    continue
                try:
                    good, bad = int(p[1]), int(p[2])
                except ValueError:
                    continue
                if p[0] not in memo:
                    memo[p[0]] = cell(p[0])
                la, lo = memo[p[0]]
                for t, (la0, la1, lo0, lo1) in boxes.items():
                    if la0 <= la <= la1 and lo0 <= lo <= lo1:
                        tot[t][0] += good
                        tot[t][1] += bad
            for t, (g, b) in tot.items():
                w.writerow([d.isoformat(), t, g, b])
            print("ok", d, flush=True)


# ---------------------------------------------------------------- Polymarket
WAR = ("strike", "attack", "invade", "invasion", "war", "military", "missile", "ceasefire", "troops", "blockade", "airstrike", "bomb",
       "nuclear test", "clash", "offensive", "declare", "martial law", "drone", "hezbollah", "houthi", "hamas", "iran", "israel", "russia",
       "ukrain", "taiwan", "china", "north korea", "kim jong", "pakistan", "india", "venezuela", "maduro", "nato", "syria", "lebanon", "yemen",
       "sudan", "congo", "libya", "guyana", "philippines", "south china sea", "hormuz", "red sea")
SKIP = ("nba", "nfl", "nhl", "mlb", "ufc", "fifa", "world cup", "election", "president of", "win the", "bitcoin", "ethereum", "price of", "eurovision",
        "oscar", "grammy", "cricket", "olympic", "temperature", "box office", "tweet", "musk", "approval rating", "poll", "nominee", "primary")


def cmd_polymarket():
    path = os.path.join(OUT, "polymarket_markets.jsonl")
    seen = set()
    n_ok = 0
    with open(path, "w") as f:
        for closed in ("true", "false"):
            off = 0
            while True:
                q = urllib.parse.urlencode({"closed": closed, "limit": 500, "offset": off, "order": "volume", "ascending": "false", "volume_num_min": 20000})
                try:
                    page = get("https://gamma-api.polymarket.com/markets?" + q)
                except Exception as e:
                    print("page fail", off, e, flush=True)
                    break
                if not page:
                    break
                for m in page:
                    text = ((m.get("question") or "") + " " + (m.get("description") or "")[:300]).lower()
                    if m.get("id") in seen or not any(k in text for k in WAR) or any(k in (m.get("question") or "").lower() for k in SKIP):
                        continue
                    seen.add(m.get("id"))
                    try:
                        tok = json.loads(m.get("clobTokenIds") or "[]")[0]
                    except (ValueError, IndexError, TypeError):
                        continue
                    hist = []
                    try:
                        h = get("https://clob.polymarket.com/prices-history?" + urllib.parse.urlencode({"market": tok, "interval": "max", "fidelity": 1440}))
                        hist = [[int(x["t"]), float(x["p"])] for x in h.get("history", [])]
                    except Exception as e:
                        print("hist fail", m.get("id"), str(e)[:60], flush=True)
                    rec = {k: m.get(k) for k in ("id", "question", "slug", "startDate", "endDate", "closedTime", "outcomes", "outcomePrices", "volumeNum", "umaResolutionStatus", "closed")}
                    rec["description"] = (m.get("description") or "")[:600]
                    rec["history"] = hist
                    f.write(json.dumps(rec) + "\n")
                    n_ok += 1
                    time.sleep(0.15)
                off += 500
                if off > 60000:
                    break
                time.sleep(0.5)
    print("markets", n_ok)


# ---------------------------------------------------------------- OONI
OONI_CC = {"UA", "RU", "BY", "PL", "LT", "LV", "EE", "FI", "IR", "IQ", "YE", "IL", "LB", "PS", "SY", "TW", "PH", "VN", "KR", "IN", "PK", "LY", "SD", "SS", "CD", "VE", "CU"}


def cmd_ooni():
    path = os.path.join(OUT, "ooni.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for cc in sorted(OONI_CC):
            for y in range(2018, YDAY.year + 1):
                q = urllib.parse.urlencode({"probe_cc": cc, "since": f"{y}-01-01", "until": f"{y + 1}-01-01", "axis_x": "measurement_start_day", "test_name": "web_connectivity"})
                try:
                    p = get("https://api.ooni.io/api/v1/aggregation?" + q, timeout=180)
                except Exception as e:
                    print("fail", cc, y, str(e)[:80], flush=True)
                    continue
                for r in p.get("result", []):
                    w.writerow([r.get("measurement_start_day"), cc, r.get("measurement_count", 0), r.get("anomaly_count", 0), r.get("confirmed_count", 0), r.get("failure_count", 0)])
                print("ok", cc, y, flush=True)
                time.sleep(1)


# ---------------------------------------------------------------- GPR
def cmd_gpr():
    for name in ("data_gpr_daily_recent.xls", "data_gpr_export.xls"):
        try:
            b = get("https://www.matteoiacoviello.com/gpr_files/" + name, raw=True, timeout=180)
            open(os.path.join(OUT, name), "wb").write(b)
            print("ok", name, len(b))
        except Exception as e:
            print("fail", name, e)


# ---------------------------------------------------------------- UCDP
UCDP = ["https://ucdp.uu.se/downloads/ged/ged251-csv.zip",
        "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v25_0_12.csv", "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_1.csv",
        "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_2.csv", "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_3.csv",
        "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_4.csv", "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_5.csv",
        "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_6.csv", "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_7.csv",
        "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_8.csv"]


def cmd_ucdp():
    agg = {}
    for url in UCDP:
        try:
            b = get(url, raw=True, timeout=300, retries=2)
        except Exception as e:
            print("fail", url, str(e)[:80], flush=True)
            continue
        if url.endswith(".zip"):
            z = zipfile.ZipFile(io.BytesIO(b))
            name = [x for x in z.namelist() if x.endswith(".csv")][0]
            fh = io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace")
        else:
            fh = io.StringIO(b.decode("utf-8", "replace"))
        n = 0
        for r in csv.DictReader(fh):
            try:
                d = r["date_start"][:10]
                if d < "2017-01-01":
                    continue
                k = (d, r["country"], r["type_of_violence"])
                a = agg.setdefault(k, [0, 0])
                a[0] += 1
                a[1] += int(float(r.get("best") or 0))
                n += 1
            except (KeyError, ValueError):
                continue
        print("ok", url, n, flush=True)
    with open(os.path.join(OUT, "ucdp_country_day.csv"), "w", newline="") as f:
        w = csv.writer(f)
        for (d, c, t), (ev, best) in sorted(agg.items()):
            w.writerow([d, c, t, ev, best])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    cmd = sys.argv[1]
    a = [int(x) for x in sys.argv[2:]]
    {"gdelt": lambda: cmd_gdelt(*a), "gpsjam": lambda: cmd_gpsjam(*a), "polymarket": cmd_polymarket, "ooni": cmd_ooni, "gpr": cmd_gpr, "ucdp": cmd_ucdp}[cmd]()
