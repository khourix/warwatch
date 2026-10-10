"""Monthly pickup and SUV exports from Japan and Thailand (Toyota's Land Cruiser and Hilux sources) to the war-zone countries and the
re-export hubs that supply them, from the UN Comtrade API (free key in COMTRADE_API_KEY). Mirror data: most war-zone countries do not
report their own imports. Writes backfill/data/trade_<origin>_<product>_<dest>.csv as `YYYY-MM-01,units`.

  python3 backfill/trade.py [--start 2015] [--end 2026] [--dest sudan,yemen]
Safe to re-run; the last two years are always re-fetched because Comtrade revises recent months.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
API = "https://comtradeapi.un.org/data/v1/get/C/M/HS"
ORIGINS = {"jpn": 392, "tha": 764}
DESTS = {"sudan": 729, "libya": 434, "yemen": 887, "drc": 180, "iraq": 368, "chad": 148, "syria": 760, "somalia": 706,
         "uae": 784, "jordan": 400, "turkey": 792,
         "saudi": 682, "kuwait": 414, "bahrain": 48, "qatar": 634, "oman": 512}     # the Gulf states (the UAE is above)
PICKUP4, PICKUP6 = "8704", ["870421", "870422", "870431", "870432"]      # pickups and light trucks
SUV6 = ["870323", "870324", "870332", "870333"]                            # large petrol and diesel cars (Land Cruiser class)
CODES = ",".join([PICKUP4] + PICKUP6 + SUV6)


def fetch(key, origin, dest, year, tries=4, codes=CODES):
    q = {"reporterCode": origin, "partnerCode": dest, "flowCode": "X", "cmdCode": codes, "maxRecords": 500,
         "period": ",".join(f"{year}{m:02d}" for m in range(1, 13))}
    for i in range(tries):
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={"Ocp-Apim-Subscription-Key": key, "User-Agent": "warwatch"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read()).get("data", [])
        except Exception as e:
            if getattr(e, "code", 0) == 429 or i < tries - 1:
                time.sleep(20 * (i + 1))
                continue
            print("  failed", origin, dest, year, str(e)[:100])
            return None
    return None


def monthly(rows):
    """Comtrade rows -> {"pickup": {month: units}, "suv": {month: units}}. A 4-digit pickup row already includes its 6-digit lines, so it wins."""
    per = {}
    for r in rows:
        if r.get("motCode", 0) not in (0, None) or r.get("customsCode", "C00") not in ("C00", None) or r.get("partner2Code", 0) not in (0, None):
            continue
        p = str(r.get("period"))
        month = f"{p[:4]}-{p[4:6]}-01"
        q = r.get("qty")
        if q is None:
            continue
        per.setdefault(month, {}).setdefault(str(r.get("cmdCode")), 0.0)
        per[month][str(r.get("cmdCode"))] += float(q)
    out = {"pickup": {}, "suv": {}}
    for m, c in per.items():
        pick = c.get(PICKUP4) if PICKUP4 in c else sum(c.get(k, 0.0) for k in PICKUP6) if any(k in c for k in PICKUP6) else None
        suv = sum(c.get(k, 0.0) for k in SUV6) if any(k in c for k in SUV6) else None
        if pick is not None:
            out["pickup"][m] = pick
        if suv is not None:
            out["suv"][m] = suv
    return out


_PUB = {}


def published(key, origin, year):
    """Months of `year` that the reporter has published at all (its exports to the world), so a missing country row can mean zero."""
    if (origin, year) not in _PUB:
        time.sleep(4)
        rows = fetch(key, origin, 0, year, codes="8704")
        _PUB[(origin, year)] = None if rows is None else {f"{str(r['period'])[:4]}-{str(r['period'])[4:6]}-01" for r in rows}
    return _PUB[(origin, year)]


def load(path):
    try:
        with open(path) as f:
            return {r[0]: float(r[1]) for r in csv.reader(f) if r}
    except OSError:
        return {}


def save(path, pts):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for k in sorted(pts):
            w.writerow([k, f"{pts[k]:g}"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=dt.date.today().year)
    ap.add_argument("--origin", default=",".join(ORIGINS))
    ap.add_argument("--dest", default=",".join(DESTS))
    a = ap.parse_args()
    key = os.environ.get("COMTRADE_API_KEY")
    if not key:
        sys.exit("COMTRADE_API_KEY is not set")
    recent = dt.date.today().year - 2
    for o, oc in ((o, ORIGINS[o]) for o in a.origin.split(",")):
        for d in a.dest.split(","):
            files = {k: os.path.join(OUT, f"trade_{o}_{k}_{d}.csv") for k in ("pickup", "suv")}
            have = {k: load(p) for k, p in files.items()}
            for y in range(a.start, a.end + 1):
                if y < recent and any(m.startswith(str(y)) for m in have["pickup"]) and any(m.startswith(str(y)) for m in have["suv"]):
                    continue
                time.sleep(4)
                rows = fetch(key, oc, DESTS[d], y)
                if rows is None:
                    continue
                pub = published(key, oc, y)
                if not pub:
                    continue
                got = monthly(rows)
                for k in ("pickup", "suv"):
                    for m in sorted(pub):                    # a published month with no row for this country is a month with no shipments
                        have[k][m] = got[k].get(m, 0.0)
            for k, p in files.items():
                if have[k]:
                    save(p, have[k])
            print(o, d, {k: len(v) for k, v in have.items()})


if __name__ == "__main__":
    main()
