#!/usr/bin/env python3
"""Prediction study (plan: docs/PREDSTUDY_PLAN.md). Part 3: do the Caldara-Iacoviello geopolitical-risk indices (GPR and the
LLM-scored AI-GPR) time events? Reuses timingstudy.Study, so the baseline and the gates are exactly the published model's.

    python3 warwatch/predstudy.py gpr            # G1..G5 -> backtest/predstudy/gpr_results.json
    python3 warwatch/predstudy.py gpr --quick    # one ridge strength and 300 shifts, for checking the code

Reads backtest/predstudy/data/gpr (pulled by backtest/predstudy/fetch.py). Needs numpy, pandas and scipy. Writes nothing the live build reads.
"""
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timingstudy as TS  # noqa: E402
import validate as V  # noqa: E402

ROOT = V.ROOT
GPR = os.path.join(ROOT, "backtest", "predstudy", "data", "gpr")
OUT = os.path.join(ROOT, "backtest", "predstudy")
TH = V.TH
MONTH_LAG_DAYS = 4          # a month's AI-GPR value counts as public on the 5th of the next month
DAILY_LAG_DAYS = 7          # daily files: public a week later (the classic file is posted weekly)

# Fixed before any run (docs/PREDSTUDY_PLAN.md)
COUNTRIES = {
    "ukraine": ["Ukraine"], "europe_east": ["Poland", "Lithuania", "Latvia", "Estonia", "Finland", "Romania", "Moldova"],
    "iran": ["Iran"], "yemen": ["Yemen", "Saudi Arabia"], "israel": ["Israel", "Lebanon", "Syria", "Palestine"],
    "taiwan": ["Taiwan"], "scs": ["Philippines", "Vietnam"], "korea": ["North Korea", "South Korea"], "southasia": ["India", "Pakistan"],
    "libya": ["Libya"], "sudan": ["Sudan"], "drc": ["DRC", "Rwanda"], "venezuela": ["Venezuela", "Guyana"],
}
PAIRS = {
    "ukraine": ["Russia|Ukraine", "Ukraine|Russia"],
    "europe_east": ["Russia|Poland", "Russia|Lithuania", "Russia|Latvia", "Russia|Estonia", "Russia|Finland", "Russia|Romania", "Lithuania|Russia"],
    "iran": ["Israel|Iran", "Iran|Israel", "USA|Iran", "Iran|USA", "Iran|Saudi Arabia", "Saudi Arabia|Iran", "Iran|Iraq", "Iraq|Iran", "Iran|Kuwait", "UK|Iran"],
    "yemen": ["Saudi Arabia|Yemen", "USA|Yemen", "Yemen|USA", "UK|Yemen", "Egypt|Yemen"],
    "israel": ["Israel|Palestine", "Palestine|Israel", "Israel|Lebanon", "Lebanon|Israel", "Israel|Syria", "Syria|Israel", "Iran|Lebanon", "Palestine|Lebanon"],
    "taiwan": ["China|Taiwan", "Taiwan|China", "USA|Taiwan"],
    "scs": ["China|Philippines", "China|Vietnam", "Vietnam|China", "USA|Philippines", "Philippines|USA"],
    "korea": ["North Korea|South Korea", "South Korea|North Korea", "USA|North Korea", "North Korea|USA", "North Korea|Japan", "Japan|North Korea"],
    "southasia": ["India|Pakistan", "Pakistan|India"],
    "libya": ["Libya|Egypt", "Libya|Chad", "France|Libya", "UK|Libya", "Libya|UK", "USA|Libya", "Libya|USA"],
    "sudan": ["Sudan|South Sudan", "USA|Sudan", "Sudan|USA"],
    "drc": ["Rwanda|DRC", "Rwanda|Congo", "Uganda|Congo", "Congo|DRC", "DRC|Congo", "Angola|DRC", "USA|DRC"],
    "venezuela": ["USA|Venezuela", "Venezuela|USA", "Cuba|Venezuela"],
}
OILREGION = {"iran": "GPR_OIL_MiddleEast", "yemen": "GPR_OIL_MiddleEast", "israel": "GPR_OIL_MiddleEast", "ukraine": "GPR_OIL_Russia",
             "europe_east": "GPR_OIL_Russia", "venezuela": "GPR_OIL_Venezuela"}


def _read(name):
    return pd.read_csv(os.path.join(GPR, name), low_memory=False)


def _monthly_evidence(sid, t, df, cols):
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return None
    s = df[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
    pts = [(d[:7], float(v)) for d, v in zip(df["Date"], s) if v == v]
    pts = [(m, v + 1.0) for m, v in pts]          # +1: score_series takes logs; a zero month stays finite
    avail = [(dt.date(int(m[:4]), int(m[5:7]), 1) + dt.timedelta(days=32)).replace(day=1 + MONTH_LAG_DAYS).toordinal() for m, _ in pts]
    keep = [i for i, (m, _) in enumerate(pts) if m >= "2010-01"]
    return TS._evidence(sid, t, "monthly", [pts[i] for i in keep], [avail[i] for i in keep])


def _daily_evidence(sid, t, dates, vals):
    pts = [(d, float(v)) for d, v in zip(dates, vals) if v == v and d >= "2016-01-01"]
    avail = [(dt.date.fromisoformat(d) + dt.timedelta(days=DAILY_LAG_DAYS)).toordinal() for d, _ in pts]
    return TS._evidence(sid, t, "daily", pts, avail)


def fam_G1():
    c = _read("ai_gpr_country_monthly.csv__csv.csv.gz")
    e = _read("ai_gpr_country_eventtype_monthly.csv__csv.csv.gz")
    out = {"aigpr_country": {}, "aigpr_milconf": {}}
    for t in TH:
        a = _monthly_evidence(f"aigpr_country_{t}", t, c, [f"{k}_all" for k in COUNTRIES[t]])
        b = _monthly_evidence(f"aigpr_milconf_{t}", t, e, [f"{k}_military_conflict" for k in COUNTRIES[t]])
        if a is not None:
            out["aigpr_country"][t] = a
        if b is not None:
            out["aigpr_milconf"][t] = b
    return out


def fam_G2():
    b = _read("ai_gpr_bilateral_monthly.csv__csv.csv.gz")
    out = {"aigpr_pair": {}}
    for t in TH:
        s = _monthly_evidence(f"aigpr_pair_{t}", t, b, PAIRS[t])
        if s is not None:
            out["aigpr_pair"][t] = s
    return out


def fam_G3():
    g = _read("data_gpr_daily_recent.xls__Sheet1.csv.gz")
    gd = [f"{str(int(x))[:4]}-{str(int(x))[4:6]}-{str(int(x))[6:8]}" for x in g["DAY"]]
    a = _read("ai_gpr_data_daily.csv__csv.csv.gz")
    e1 = _daily_evidence("gprd_threat", "global", gd, g["GPRD_THREAT"].values)
    e2 = _daily_evidence("aigpr_threat", "global", list(a["Date"]), a["THREATS_GPR_AI"].values)
    return {"gprd_threat": {t: e1 for t in TH}, "aigpr_threat": {t: e2 for t in TH}}


def fam_G4():
    a = _read("ai_gpr_data_daily.csv__csv.csv.gz")
    out = {"aigpr_oilregion": {}}
    cache = {}
    for t, col in OILREGION.items():
        if col not in cache:
            cache[col] = _daily_evidence(f"aigpr_{col}", "x", list(a["Date"]), a[col].values)
        out["aigpr_oilregion"][t] = cache[col]
    return out


def fam_G5():
    out = {}
    for f in (fam_G1, fam_G2, fam_G3, fam_G4):
        out.update(f())
    return out


CANDS = {"G1": fam_G1, "G2": fam_G2, "G3": fam_G3, "G4": fam_G4, "G5": fam_G5}
NAMES = {"base": "Baseline (published model)", "G1": "AI-GPR, country (all and military conflict)", "G2": "AI-GPR, country pairs",
         "G3": "GPR and AI-GPR daily threats (global)", "G4": "AI-GPR oil-region daily", "G5": "G1 to G4 together"}
ALPHA = 0.05 / len(CANDS)


def single_auc(S, fam):
    """Within-theatre AUC of one family's raw evidence on the out-of-sample years (days with a value), a description, no fit."""
    P, y, lab = S.get("P"), S.get("y"), S.get("lab")
    yr = P["date"].dt.year.values
    x = P[fam].values
    ok = lab & ~np.isnan(x) & (yr >= V.TEST_YEARS[0]) & S["core"]
    num = den = 0.0
    th = P["theatre"].values
    for t in TH:
        m = ok & (th == t)
        n1 = y[m].sum()
        if n1 == 0 or n1 == m.sum():
            continue
        num += n1 * V.auc(y[m], x[m])
        den += n1
    return num / den if den else float("nan"), int(len({e for e in S["eid"][ok & (y == 1)]}))


def run_gpr(quick):
    TS.FAMS.update(CANDS)
    TS.N_TRIED = len(CANDS)
    TS.ALPHA = ALPHA
    st = TS.Study(quick=quick)
    res = {}
    for c in ["base"] + list(CANDS):
        r = st.run([] if c == "base" else [c])
        row = {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in r.items()
               if k in ("bss", "auc", "auc_lo", "auc_hi", "wauc", "shuffle_p", "shuf95", "flagged", "events", "hit_ep", "false_ep", "lam", "nfam")}
        row["years"] = {int(k): float(v) for k, v in r["years"].items()}
        row["gates_005"] = bool(r["bss"] > 0 and r["auc_lo"] > 0.5 and r["shuffle_p"] < 0.05)
        row["validated"] = bool(r["bss"] > 0 and r["auc_lo"] > 0.5 and r["shuffle_p"] < ALPHA)
        if c != "base":
            S_ = st.setup([c])
            fams = list(CANDS[c]().keys())
            row["single"] = {f: single_auc(S_, f) for f in fams if f in S_["P"].columns}
        res[c] = row
        print(c, json.dumps({k: v for k, v in row.items() if k != "years"}, default=str), flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "gpr_results.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "gpr"
    if cmd == "gpr":
        run_gpr("--quick" in sys.argv)
    else:
        sys.exit(__doc__)
