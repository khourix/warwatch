"""Wider GDELT event types per theatre, daily from 2018: the free stand-in for POLECAT (which is paid).

The live build counts four CAMEO root codes by where events happen (13 threaten, 15 posture, 18 assault, 19 fight). This
reads the same free GDELT 1.0 daily files and keeps, per theatre and day, the counts the test plan (docs/GDELTWIDE_PLAN.md)
needs, fixed before any day was read:
  loc_*  events located in the theatre's countries (config.GDELT_CC, FIPS): all, verbal conflict (QuadClass 3), material
         conflict (QuadClass 4), summed Goldstein score, threats of military force (CAMEO 138x), alert and mobilisation
         (152, 153, 154), reduce relations and coerce (roots 16, 17)
  dy_*   events between the theatre's two sides (actor country codes, either direction; for civil wars, two actors of the
         same country, one of them armed): all, conflict (QuadClass 3 or 4), summed Goldstein, force (138x, root 15, root 17)
Output: backfill/data/gdeltwide/<year>.csv, one row per day and theatre. A day already in the file is skipped.
"""
import csv
import datetime as dt
import io
import os
import sys
import zipfile

import common as K

sys.path.insert(0, os.path.join(os.path.dirname(K.HERE), "warwatch"))
import config as C  # noqa: E402

URL = "http://data.gdeltproject.org/events/{:%Y%m%d}.export.CSV.zip"
OUT = os.path.join(K.DATA, "gdeltwide")
SIDES = {   # CAMEO actor country codes; None on the right = a civil war, both actors of the left country and one of them armed
    "ukraine": (("RUS", "BLR"), ("UKR",)),
    "europe_east": (("RUS", "BLR"), ("POL", "LTU", "LVA", "EST", "FIN", "ROU")),
    "iran": (("IRN",), ("ISR", "USA")),
    "yemen": (("YEM",), ("SAU", "ARE", "USA", "ISR", "GBR")),
    "israel": (("ISR",), ("LBN", "PSE", "SYR", "IRN")),
    "taiwan": (("CHN",), ("TWN",)),
    "scs": (("CHN",), ("PHL", "VNM")),
    "korea": (("PRK",), ("KOR", "USA", "JPN")),
    "southasia": (("IND",), ("PAK",)),
    "libya": (("LBY",), None),
    "sudan": (("SDN", "SSD"), None),
    "drc": (("COD",), ("RWA", "UGA")),
    "venezuela": (("VEN",), ("GUY", "USA")),
}
ARMED = {"MIL", "REB", "INS", "SEP"}
COLS = ["loc_all", "loc_q3", "loc_q4", "loc_gold", "loc_mil138", "loc_mob", "loc_coerce", "dy_all", "dy_q34", "dy_gold", "dy_force"]
LOC = {cc: th for th, v in C.GDELT_CC.items() for cc in v}


def _dyads(a1, a2, t1, t2):
    out = []
    for th, (A, B) in SIDES.items():
        if B is None:
            if a1 in A and a2 in A and (t1 in ARMED or t2 in ARMED):
                out.append(th)
        elif (a1 in A and a2 in B) or (a1 in B and a2 in A):
            out.append(th)
    return out


def parse(rows):
    """Tab-split GDELT 1.0 event rows -> {theatre: {col: value}}."""
    out = {th: dict.fromkeys(COLS, 0.0) for th in SIDES}
    for r in rows:
        if len(r) < 52:
            continue
        code, root, q = r[26], r[28], r[29]
        try:
            g = float(r[30] or 0)
        except ValueError:
            g = 0.0
        th = LOC.get(r[51])
        if th:
            o = out[th]
            o["loc_all"] += 1
            o["loc_q3"] += q == "3"
            o["loc_q4"] += q == "4"
            o["loc_gold"] += g
            o["loc_mil138"] += code.startswith("138")
            o["loc_mob"] += code in ("152", "153", "154")
            o["loc_coerce"] += root in ("16", "17")
        for th in _dyads(r[7], r[17], r[12], r[22]):
            o = out[th]
            o["dy_all"] += 1
            o["dy_q34"] += q in ("3", "4")
            o["dy_gold"] += g
            o["dy_force"] += code.startswith("138") or root in ("15", "17")
    return out


def _read(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {(r["day"], r["theatre"]): r for r in csv.DictReader(f)}


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["day", "theatre"] + COLS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def cmd_gdeltwide(start, end):
    for year in range(start.year, end.year + 1):
        path = os.path.join(OUT, f"{year}.csv")
        rows = _read(path)
        done = {d for d, _ in rows}
        got = 0
        for d in K.days(max(start, dt.date(year, 1, 1)), min(end, dt.date(year, 12, 31))):
            if d.isoformat() in done:
                continue
            try:
                b = K.get(URL.format(d), raw=True, retries=3)
                z = zipfile.ZipFile(io.BytesIO(b))
                rd = csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"), delimiter="\t")
                res = parse(rd)
            except Exception as e:
                K.log("skip", d, str(e)[:100])
                continue
            for th, o in res.items():
                rows[(d.isoformat(), th)] = {"day": d.isoformat(), "theatre": th, **{c: round(v, 1) for c, v in o.items()}}
            got += 1
            if got % 30 == 0:
                _write(path, rows)
                K.log(year, d, got, "days")
        _write(path, rows)
        K.log(year, "done:", got, "new days")
