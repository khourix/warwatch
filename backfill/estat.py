"""Monthly pickup and SUV exports from Japan to the war-zone countries and the Gulf, from Japan Customs through e-Stat (free appId in
ESTAT_APP_ID). Same products as backfill/trade.py but about six weeks late, not eight months, and from Japan's own 9-digit codes.
Writes backfill/data/estat_jpn_<pickup|suv>_<dest>.csv as `YYYY-MM-01,units`.

  python3 backfill/estat.py [--start 2015]
Safe to re-run; the newest tables are always re-read because customs revises the latest months.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
API = "https://api.e-stat.go.jp/rest/3.0/app/json/"
TABLE_NAME = "貿易統計_全国分 品別国別表 輸出"
PICKUP6 = ("870421", "870422", "870431", "870432")      # pickups and light trucks
SUV6 = ("870323", "870324", "870332", "870333")          # large petrol and diesel cars (Land Cruiser class)
DESTS = {"sudan": "スーダン", "southsudan": "南スーダン", "libya": "リビア", "yemen": "イエメン", "drc": "コンゴ民主共和国", "iraq": "イラク",
         "chad": "チャド", "syria": "シリア", "somalia": "ソマリア", "uae": "アラブ首長国連邦", "jordan": "ヨルダン", "turkey": "トルコ",
         "saudi": "サウジアラビア", "kuwait": "クウェート", "bahrain": "バーレーン", "qatar": "カタール", "oman": "オマーン"}


def get(key, ep, tries=4, **p):
    p["appId"] = key
    for i in range(tries):
        try:
            with urllib.request.urlopen(API + ep + "?" + urllib.parse.urlencode(p), timeout=120) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))


def listify(x):
    return x if isinstance(x, list) else [x]


def tables(key):
    """Annual-cycle export tables as [(statsDataId, first_year, last_year)], oldest first."""
    d = get(key, "getStatsList", statsCode="00350300", searchWord="品別国別 輸出", limit=100)["GET_STATS_LIST"]["DATALIST_INF"]
    out = []
    for t in listify(d.get("TABLE_INF", [])):
        if t.get("STATISTICS_NAME") != TABLE_NAME or t.get("CYCLE") != "年次":
            continue
        y = re.findall(r"(\d{4})年", (t["TITLE"] if isinstance(t["TITLE"], str) else t["TITLE"].get("$", "")))
        if y:
            out.append((t["@id"], int(y[0]), int(y[-1])))
    return sorted(out, key=lambda x: x[1])


def classes(obj):
    return {c["@code"]: c["@name"] for c in listify(obj["CLASS"])}


def monthly_cols(cat02):
    """{code: month} for the 'N月_数量2' columns (数量1 is blank for vehicles; 数量2 is the count in units)."""
    out = {}
    for code, name in cat02.items():
        m = re.match(r"^(\d{1,2})月_数量2$", name)
        if m:
            out[code] = int(m.group(1))
    return out


def rows_to_monthly(values, kind_of, month_of, year_of):
    """e-Stat VALUE rows -> {"pickup": {YYYY-MM-01: units}, "suv": {...}} per destination key via area -> use callers' maps."""
    out = {}
    for v in values:
        kind, month = kind_of.get(v.get("@cat01")), month_of.get(v.get("@cat02"))
        if not kind or not month:
            continue
        try:
            n = float(v["$"])
        except (KeyError, ValueError):
            continue
        y = year_of(v.get("@time"))
        out.setdefault((v.get("@area"), kind), {}).setdefault(f"{y}-{month:02d}-01", 0.0)
        out[(v.get("@area"), kind)][f"{y}-{month:02d}-01"] += n
    return out


def fetch_table(key, sid):
    meta = get(key, "getMetaInfo", statsDataId=sid)["GET_META_INFO"]["METADATA_INF"]["CLASS_INF"]["CLASS_OBJ"]
    objs = {o["@id"]: o for o in listify(meta)}
    cat01, cat02, area = classes(objs["cat01"]), classes(objs["cat02"]), classes(objs["area"])
    kind_of = {}
    for code in cat01:
        if code.startswith(PICKUP6):
            kind_of[code] = "pickup"
        elif code.startswith(SUV6):
            kind_of[code] = "suv"
    months = monthly_cols(cat02)
    area_of = {}
    for a, name in area.items():
        base = name.split("_", 1)[-1]
        for k, jp in DESTS.items():
            if base == jp:
                area_of[a] = k
    missing = sorted(set(DESTS) - set(area_of.values()))
    if missing:
        print("  no area code for", missing)
    values = []
    for a in area_of:
        start = 1
        while start:
            d = get(key, "getStatsData", statsDataId=sid, cdArea=a, cdCat01=",".join(kind_of), cdCat02=",".join(months), limit=100000, startPosition=start)
            body = d["GET_STATS_DATA"]["STATISTICAL_DATA"]
            values += listify(body["DATA_INF"].get("VALUE", [])) if body.get("DATA_INF") else []
            nxt = d["GET_STATS_DATA"]["RESULT_INF"].get("NEXT_KEY") if "RESULT_INF" in d["GET_STATS_DATA"] else None
            start = int(nxt) if nxt else 0
    year_of = lambda t: int(str(t)[:4])
    per = rows_to_monthly(values, kind_of, months, year_of)
    out = {}
    for (a, kind), series in per.items():
        out.setdefault((area_of[a], kind), {}).update(series)
    # A table lists all 12 months of its year; months not yet published read 0. Keep up to the last month with any exports at all.
    last = max((m for series in out.values() for m, v in series.items() if v > 0), default=None)
    if last:
        out = {k: {m: v for m, v in series.items() if m <= last} for k, series in out.items()}
    return out


def path(kind, dest):
    return os.path.join(OUT, f"estat_jpn_{kind}_{dest}.csv")


def load(p):
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return {r[0]: float(r[1]) for r in csv.reader(f) if len(r) > 1}


def save(p, data):
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        for m in sorted(data):
            w.writerow([m, int(round(data[m]))])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    a = ap.parse_args()
    key = os.environ.get("ESTAT_APP_ID")
    if not key:
        sys.exit("ESTAT_APP_ID is not set")
    os.makedirs(OUT, exist_ok=True)
    tabs = [t for t in tables(key) if t[2] >= a.start]
    newest = {t[0] for t in tabs[-2:]}
    for sid, y0, y1 in tabs:
        p0 = path("pickup", "sudan")
        if sid not in newest and os.path.exists(p0) and any(m.startswith(f"{y1}-") for m in load(p0)):
            continue
        print("table", sid, y0, y1)
        got = fetch_table(key, sid)
        for (dest, kind), series in got.items():
            cur = load(path(kind, dest))
            cur.update({m: v for m, v in series.items() if int(m[:4]) >= a.start})
            save(path(kind, dest), cur)
    print("done")


if __name__ == "__main__":
    main()
