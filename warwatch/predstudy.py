#!/usr/bin/env python3
"""Prediction study (plan: docs/PREDSTUDY_PLAN.md). Part 3: do the Caldara-Iacoviello geopolitical-risk indices (GPR and the
LLM-scored AI-GPR) time events? Reuses timingstudy.Study, so the baseline and the gates are exactly the published model's.

    python3 warwatch/predstudy.py gpr            # G1..G5 -> backtest/predstudy/gpr_results.json
    python3 warwatch/predstudy.py gpr --quick    # one ridge strength and 300 shifts, for checking the code
    python3 warwatch/predstudy.py cw             # CrisisWatch alerts against events by theatre-month -> backtest/predstudy/cw_results.json
    python3 warwatch/predstudy.py poly           # Polymarket 7-day log-odds change before events -> backtest/predstudy/poly_results.json

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


# ------------------------------------------------------------------ Part 5: CrisisWatch alerts (plan question 5)
CWDIR = os.path.join(ROOT, "backtest", "predstudy", "data", "crisiswatch")


def _events():
    ev = pd.read_csv(os.path.join(V.DATA, "events.csv"), parse_dates=["date"], keep_default_na=False)
    return ev[ev["theatre"].isin(TH)]


def _binom_greater(k, n, p0):
    from scipy.stats import binomtest
    return float(binomtest(int(k), int(n), float(p0), alternative="greater").pvalue) if n else float("nan")


def _cmh(rows):
    """Cochran-Mantel-Haenszel test across theatres (flag x event 2x2 per theatre): is a flagged month likelier to hold an event than an
    unflagged month of the same theatre? -> (common odds ratio, one-sided p)."""
    from scipy.stats import norm
    num = den = a_sum = e_sum = v_sum = 0.0
    for a, b, c, d in rows:                       # a flagged+event, b flagged+calm, c unflagged+event, d unflagged+calm
        n = a + b + c + d
        if n < 2 or (a + c) == 0 or (b + d) == 0 or (a + b) == 0 or (c + d) == 0:
            continue
        num += a * d / n
        den += b * c / n
        a_sum += a
        e_sum += (a + b) * (a + c) / n
        v_sum += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
    orr = num / den if den else float("inf")
    z = (a_sum - e_sum) / np.sqrt(v_sum) if v_sum else float("nan")
    return orr, float(1 - norm.cdf(z)) if z == z else float("nan")


def run_cw():
    import re
    import osint
    cw = pd.read_csv(os.path.join(CWDIR, "crisiswatch_wayback.csv.gz"), keep_default_na=False)
    # Page snapshots whose issue month wasn't printed are filed by snapshot date: a snapshot from the 5th on shows that month's issue
    # (published at the start of the month), an earlier one still shows the previous month's.
    def _issue(m):
        if not m.startswith("snap-"):
            return m
        d = dt.date(int(m[5:9]), int(m[9:11]), int(m[11:13]))
        if d.day < 5:
            d = (d.replace(day=1) - dt.timedelta(days=1))
        return f"{d.year:04d}-{d.month:02d}-01"
    cw["month"] = cw["month"].map(_issue)
    cw = cw[cw["month"].str.match(r"^\d{4}-\d{2}-01$")].drop_duplicates()
    months = sorted(cw["month"].unique())
    res = {"months_recovered": len(months), "first": months[0] if months else None, "last": months[-1] if months else None,
           "rows": int(len(cw)), "by_list": cw.groupby("list").size().to_dict()}
    ev = _events()
    evm = {(t, d.strftime("%Y-%m-01")) for t, d in zip(ev["theatre"], ev["date"])}
    allm = pd.period_range("2018-01", "2026-10", freq="M").strftime("%Y-%m-01")
    rows = []
    for t in TH:
        pat = re.compile(osint.CW_THEATRE[t])
        sub = cw[cw["entry"].str.contains(pat)]
        al = set(sub.loc[sub["list"] == "alert", "month"])
        de = set(sub.loc[sub["list"] == "deteriorated", "month"])
        for i, m in enumerate(allm):
            prev = [allm[j] for j in range(max(0, i - 3), i)]
            rows.append({"theatre": t, "month": m, "covered": m in set(months), "alert": m in al, "deteriorated": m in de,
                         "event": (t, m) in evm, "event_prev3": any((t, p) in evm for p in prev)})
    R = pd.DataFrame(rows)
    R["any"] = R["alert"] | R["deteriorated"]
    R["year"] = R["month"].str[:4].astype(int)
    res["coverage_by_year"] = R[R["theatre"] == TH[0]].groupby("year")["covered"].sum().astype(int).to_dict()
    C = R[R["covered"]]
    for flag in ("alert", "deteriorated", "any", "event_prev3"):
        for since in (2018, 2021):
            D = C[C["year"] >= since]
            ev_m, calm = D[D["event"]], D[~D["event"]]
            n, k = len(ev_m), int(ev_m[flag].sum())
            p0 = float(calm[flag].mean()) if len(calm) else float("nan")
            tabs = [(int((g[flag] & g["event"]).sum()), int((g[flag] & ~g["event"]).sum()), int((~g[flag] & g["event"]).sum()),
                     int((~g[flag] & ~g["event"]).sum())) for _, g in D.groupby("theatre")]
            orr, p_cmh = _cmh(tabs)
            res[f"{flag}_{since}"] = {"event_months": n, "flagged_event_months": k, "hit_rate": k / n if n else float("nan"),
                                      "calm_months": int(len(calm)), "calm_flag_rate": p0, "binom_p": _binom_greater(k, n, p0),
                                      "within_theatre_odds_ratio": orr, "within_theatre_cmh_p": p_cmh,
                                      "precision": float(D.loc[D[flag], "event"].mean()) if D[flag].any() else float("nan")}
    d21 = res.get("any_2021", {})
    res["passes_plan_rule"] = bool(d21 and d21["hit_rate"] > d21["calm_flag_rate"] and d21["binom_p"] < 0.05)
    with open(os.path.join(OUT, "cw_results.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    R.to_csv(os.path.join(OUT, "cw_theatre_months.csv.gz"), index=False)
    print(json.dumps(res, indent=1, default=str))
    return res


# ------------------------------------------------------------------ Part 4: Polymarket (plan question 4), description only
PMDIR = os.path.join(ROOT, "backtest", "predstudy", "data", "polymarket")
PM_THEATRE = {   # question text -> theatre (a market can name more than one)
    "ukraine": r"ukrain|kyiv|crimea|donbas|donetsk|zaporizh|kharkiv|odesa|kursk|putin.*zelensk|zelensk",
    "europe_east": r"poland|polish|baltic|lithuania|latvia|estonia|finland|moldova|nato (?:country|member|territory)|article 5",
    "iran": r"\biran|tehran|hormuz|irgc|khamenei|fordow|natanz",
    "yemen": r"yemen|houthi|red sea",
    "israel": r"israel|gaza|hamas|hezbollah|lebanon|syria|west bank|idf|netanyahu",
    "taiwan": r"taiwan",
    "scs": r"south china sea|philippin|scarborough|second thomas",
    "korea": r"north korea|kim jong|pyongyang|south korea",
    "southasia": r"\bindia\b|\bindian\b|pakistan|kashmir",
    "libya": r"libya", "sudan": r"sudan|\brsf\b|el fasher|khartoum", "drc": r"congo|\bdrc\b|rwanda|\bm23\b|goma",
    "venezuela": r"venezuela|maduro|caracas|guyana|essequibo",
}


def _logit(p):
    p = np.clip(p, 0.005, 0.995)
    return np.log(p / (1 - p))


def run_poly():
    import re
    mk = pd.read_csv(os.path.join(PMDIR, "markets.csv.gz"), keep_default_na=False, dtype={"id": str})
    px = pd.read_csv(os.path.join(PMDIR, "prices_daily.csv.gz"), dtype={"id": str})
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values(["id", "date"]).drop_duplicates(["id", "date"], keep="last")
    th_of = {}
    for mid, q in zip(mk["id"], mk["question"]):
        ts = [t for t, r in PM_THEATRE.items() if re.search(r, q, re.I)]
        if ts:
            th_of[mid] = ts
    res = {"markets": int(len(mk)), "markets_with_prices": int(px["id"].nunique()), "mapped": len(th_of),
           "price_rows": int(len(px)), "first_price": str(px["date"].min().date()) if len(px) else None}
    res["mapped_by_theatre"] = {t: sum(t in v for v in th_of.values()) for t in TH}
    # daily log-odds per market on a full calendar, then 7-day change ending the day before
    chg = []
    for mid, g in px[px["id"].isin(th_of)].groupby("id"):
        s = g.set_index("date")["p_yes"].astype(float)
        s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D")).ffill(limit=3)
        L = pd.Series(_logit(s.values), index=s.index)
        d7 = (L.shift(1) - L.shift(8)).dropna()
        lvl = L.shift(1).dropna()
        for t in th_of[mid]:
            chg.append(pd.DataFrame({"theatre": t, "id": mid, "date": d7.index, "d7": d7.values, "lvl": lvl.reindex(d7.index).values}))
    if not chg:
        res["note"] = "no mapped market has a price history"
    else:
        Cg = pd.concat(chg)
        TD = Cg.groupby(["theatre", "date"]).agg(d7=("d7", "mean"), d7max=("d7", "max"), lvl=("lvl", "mean"), n=("id", "nunique")).reset_index()
        ev = _events()
        ev = ev[ev["date"] >= "2024-01-01"]
        near = set()
        for t, d in zip(ev["theatre"], ev["date"]):
            for k in range(-30, 8):
                near.add((t, d + pd.Timedelta(days=k)))
        evs = set(zip(ev["theatre"], ev["date"]))
        TD["event"] = [(t, d) in evs for t, d in zip(TD["theatre"], TD["date"])]
        TD["calm"] = [(t, d) not in near for t, d in zip(TD["theatre"], TD["date"])]
        TD = TD[TD["date"] >= "2024-01-01"]
        E, Cm = TD[TD["event"]], TD[TD["calm"]]
        res["events_2024_on"] = int(len(ev))
        res["events_with_open_market"] = int(len(E))
        res["events_by_theatre_with_market"] = E.groupby("theatre").size().to_dict()
        out = {}
        for col in ("d7", "d7max", "lvl"):
            num = den = 0.0
            for t, g in pd.concat([E, Cm]).groupby("theatre"):
                n1 = int(g["event"].sum())
                if n1 and n1 < len(g):
                    num += n1 * V.auc(g["event"].values.astype(int), g[col].values)
                    den += n1
            out[col] = {"event_mean": float(E[col].mean()) if len(E) else float("nan"), "calm_mean": float(Cm[col].mean()) if len(Cm) else float("nan"),
                        "event_median": float(E[col].median()) if len(E) else float("nan"), "calm_median": float(Cm[col].median()) if len(Cm) else float("nan"),
                        "within_theatre_auc": num / den if den else float("nan")}
        res["compare"] = out
        res["event_rows"] = E.assign(date=E["date"].dt.strftime("%Y-%m-%d")).to_dict("records")
    with open(os.path.join(OUT, "poly_results.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "event_rows"}, indent=1, default=str))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "gpr"
    if cmd == "gpr":
        run_gpr("--quick" in sys.argv)
    elif cmd == "cw":
        run_cw()
    elif cmd == "poly":
        run_poly()
    else:
        sys.exit(__doc__)
