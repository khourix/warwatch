#!/usr/bin/env python3
"""Backtest and validation harness for the v7 engine. Standard library only.

    python3 warwatch/backtest.py fetch        # long histories of every catalogue series that has one (needs the API keys)
    python3 warwatch/backtest.py run          # replay the engine day by day, write docs/BACKTEST.md and backtest/results.json
    python3 warwatch/backtest.py weights      # export the weight table to docs/weights_<version>.csv

What it can and cannot test. Only series whose source serves old data can be replayed: FRED prices, Twelve Data
equities, IMF PortWatch transits, ECB exchange rates, UK advisory history, US/EU procurement and trade, IODA outages and
HAPI conflict counts. The live OSINT feeds (aircraft, ships, fires, GNSS, news) start in 2026 and cannot be replayed, so
this tests the aggregation maths and the slow indicators, not the full leading-indicator set. The report says so.

Each series is replayed with the publication delay its source really has (monthly data about two months, PortWatch
about a week), so a score on a given day uses only what was public that day.
"""
import bisect
import csv
import datetime as dt
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import config as C  # noqa: E402
import engine  # noqa: E402
import scoring  # noqa: E402
import sources as S  # noqa: E402
import stats  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "backtest", "history")
DOCS = os.path.join(ROOT, "docs")
START, END, STEP = dt.date(2021, 7, 1), dt.date(2024, 12, 31), 2
LONG = {"fetch_fred", "fetch_twelvedata", "fetch_market", "fetch_portwatch", "fetch_fcdo", "fetch_ioda", "fetch_frankfurter", "fetch_cboe_vix", "fetch_fx_current",
        "fetch_usaspending", "fetch_comext", "fetch_census", "fetch_ted", "fetch_hapi_events"}
# days between a point's date (end of the month for monthly series) and the day it is public
LAG = {"fetch_fred": 2, "fetch_twelvedata": 1, "fetch_market": 1, "fetch_portwatch": 7, "fetch_fcdo": 0, "fetch_ioda": 1, "fetch_frankfurter": 1, "fetch_cboe_vix": 1, "fetch_fx_current": 1,
       "fetch_usaspending": 45, "fetch_comext": 70, "fetch_census": 40, "fetch_ted": 20, "fetch_hapi_events": 60}
EVENTS = {   # theatre -> [(what happened, date)]
    "ukraine": [("Russia invades Ukraine", "2022-02-24")],
    "europe_east": [("Russia invades Ukraine (eastern flank)", "2022-02-24")],
    "yemen": [("Houthis seize Galaxy Leader, Red Sea campaign begins", "2023-11-19"), ("US and UK strike the Houthis", "2024-01-12")],
    "israel": [("Hamas attack on Israel", "2023-10-07"), ("Iran missile and drone attack on Israel", "2024-04-13")],
    "iran": [("Iran strikes Israel directly", "2024-04-13")],
    "taiwan": [("PLA drills after the Pelosi visit", "2022-08-04")],
}
SNAPSHOTS = [("Ukraine, one week before the invasion", "ukraine", "2022-02-17"), ("Yemen, during the Red Sea campaign", "yemen", "2024-01-10"),
             ("Taiwan, days before the Pelosi drills", "taiwan", "2022-08-01")]
PRE, CALM_GAP, LOOK = 30, 60, 60     # pre-event window, days away from any event to count as calm, lead-time look-back


# ------------------------------------------------------------------ fetch
def _patch():
    o = {n: getattr(S, n) for n in LONG | {"fcdo_daily"} if hasattr(S, n)}
    S.fetch_fred = lambda series, key, days=0: o["fetch_fred"](series, key, days=3300)
    S.fetch_frankfurter = lambda ccy, days=0, base="EUR": o["fetch_frankfurter"](ccy, days=3300, base=base)
    S.fetch_cboe_vix = lambda days=0: o["fetch_cboe_vix"](days=12000)
    S.fetch_ioda = lambda cc, source="bgp", days=0: o["fetch_ioda"](cc, source, days=1500)
    S.fetch_usaspending = lambda *a, **k: o["fetch_usaspending"](*a, **{**k, "years": 9})
    S.fetch_comext = lambda product, partners, since=None: o["fetch_comext"](product, partners, since="2018-01")
    S.fetch_census = lambda hs6, names, key, since=None: o["fetch_census"](hs6, names, key, since="2018-01")
    S.fetch_ted = lambda cpvs, months=0: o["fetch_ted"](cpvs, months=84)
    S.fcdo_daily = lambda p, days=0, today=None: o["fcdo_daily"](p, days=3300, today=today)

    def portwatch(name, days=0):
        since = (dt.date.today() - dt.timedelta(days=3300)).isoformat()
        out, off = [], 0
        while True:
            q = S.urllib.parse.urlencode({"where": f"portname LIKE '%{name}%' AND date >= DATE '{since}'", "outFields": "date,portname,n_total",
                                          "returnGeometry": "false", "orderByFields": "date ASC", "resultRecordCount": 1000, "resultOffset": off, "f": "json"})
            p = S.get(S.PW + "Daily_Chokepoints_Data/FeatureServer/0/query?" + q)
            out += S.parse_portwatch(p)
            if len(p.get("features", [])) < 1000:
                return out
            off += 1000
    S.fetch_portwatch = portwatch

    def twelve(symbol, key):
        wait = 8.0 - (S.time.time() - S._TD["last"])
        if wait > 0 and S._TD["last"]:
            S.time.sleep(wait)
        S._TD["last"] = S.time.time()
        q = S.urllib.parse.urlencode({"symbol": symbol, "interval": "1day", "outputsize": 5000, "start_date": "2018-01-01", "apikey": key})
        return S.parse_twelvedata(S.get("https://api.twelvedata.com/time_series?" + q))
    S.fetch_twelvedata = twelve
    S.fetch_market = lambda symbol: twelve(symbol, os.environ["TWELVEDATA_API_KEY"])   # Yahoo refuses runners; long history from Twelve Data


def _fetcher(s):
    names = set(s["fetch"].__code__.co_names) & LONG
    return next(iter(names)) if names else None


def cmd_fetch(only=None):
    _patch()
    os.makedirs(HIST, exist_ok=True)
    for s in catalog.SERIES:
        if only and s["id"] not in only:
            continue
        fn = _fetcher(s)
        if not fn:
            continue
        if [k for k in s["needs"] if not os.environ.get(k)]:
            print("skip (no key)", s["id"])
            continue
        try:
            pts = s["fetch"]()
        except Exception as e:
            print("FAIL", s["id"], str(e)[:120], flush=True)
            continue
        if not pts:
            print("empty", s["id"])
            continue
        with open(os.path.join(HIST, s["id"] + ".csv"), "w", newline="") as f:
            csv.writer(f).writerows((l, repr(float(v))) for l, v in pts)
        print("ok", s["id"], len(pts), pts[0][0], pts[-1][0], flush=True)


# ------------------------------------------------------------------ replay
def _eom(label):
    y, m = int(label[:4]), int(label[5:7])
    return (dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1))


def load_series():
    out = []
    for s in catalog.SERIES:
        fn = _fetcher(s)
        p = os.path.join(HIST, s["id"] + ".csv")
        if not fn or not os.path.exists(p):
            continue
        with open(p) as f:
            pts = [(r[0], float(r[1])) for r in csv.reader(f)]
        if s["kind"] == "daily":
            avail = [(dt.date.fromisoformat(l[:10]) + dt.timedelta(days=LAG[fn])).toordinal() for l, _ in pts]
        else:
            avail = [(_eom(l) + dt.timedelta(days=LAG[fn])).toordinal() for l, _ in pts]
        out.append({"id": s["id"], "theatre": s["theatre"], "domain": s["domain"], "direction": s["direction"], "lag": s["lag"], "kind": s["kind"], "scored": s["scored"],
                    "transform": s.get("transform"), "all": pts, "avail": avail, "status": "ok"})
    return out


def snapshot(series, d, keep=250):
    """Series as the dashboard would have seen them on day d: only points already public, scored by both engines."""
    rows = []
    o = d.toordinal()
    for s in series:
        cut = bisect.bisect_right(s["avail"], o)
        pts = s["all"][max(0, cut - keep):cut]
        r = {k: s[k] for k in ("id", "theatre", "domain", "direction", "lag", "kind", "scored")}
        r.update(points=pts, score=stats.score_series(pts, s["kind"], transform=s.get("transform"), scale=s.get("scale")), old=stats.legacy_score_series(pts, s["kind"]))
        rows.append(r)
    return rows


def _old(rows, theatre):
    old_rows = [dict(r, score=r["old"]) for r in rows if r["theatre"] == theatre]
    dom = scoring.theatre_view(old_rows, theatre)
    lv = scoring.level(dom)
    zs = sorted((v["z"] for v in dom.values() if v["z"] is not None), reverse=True)
    proxy = len(lv["firing"]) * 10 + (statistics.fmean(zs[:2]) if zs else 0.0)    # continuous stand-in for the 0/5 count
    return {"level": lv["level"], "firing": lv["firing"], "proxy": proxy, "domains": {k: v["z"] for k, v in dom.items()}}


def evaluate(rows, theatre, weights, calib=(0.0, 1.0)):
    new, aud = engine.theatre_composite(rows, theatre, weights[theatre], calib)
    return new, aud, _old(rows, theatre)


def evaluate_day(rows, theatres, weights):
    """The production engine for one day (one pass: thresholds come from the calm-world simulation, not from the day's readings)."""
    calib = (0.0, 1.0)
    return {t: evaluate(rows, t, weights, calib) for t in theatres}, calib


def replay(series, weights, theatres):
    res = {t: [] for t in theatres}
    d = START
    while d <= END:
        rows = snapshot(series, d)
        day, _ = evaluate_day(rows, theatres, weights)
        for t in theatres:
            new, _, old = day[t]
            res[t].append({"d": d.isoformat(), "zc": new["zc"], "lvl": new["level"], "score": new["score"], "nlive": new["scorable"], "nser": sum(1 for r in rows if r["theatre"] == t and r["score"]),
                           "old": old["level"], "oldp": old["proxy"], "oldf": len(old["firing"])})
        d += dt.timedelta(days=STEP)
    return res


# ------------------------------------------------------------------ metrics
def auc(pos, neg):
    """P(score of a positive day > score of a calm day), ties half. Mann-Whitney."""
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks, i = {}, 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    rs = sum(ranks[k] for k, (_, lab) in enumerate(allv) if lab)
    return (rs - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def spearman(a, b):
    def rk(x):
        s = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for n, i in enumerate(s):
            r[i] = n
        return r
    ra, rb = rk(a), rk(b)
    ma, mb = statistics.fmean(ra), statistics.fmean(rb)
    va, vb = sum((x - ma) ** 2 for x in ra), sum((x - mb) ** 2 for x in rb)
    return 1.0 if va == 0 or vb == 0 else sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / math.sqrt(va * vb)


def metrics(res):
    out = []
    for t, evs in EVENTS.items():
        rows = res.get(t)
        if not rows:
            continue
        dates = [dt.date.fromisoformat(r["d"]) for r in rows]
        ev_d = [dt.date.fromisoformat(d) for _, d in evs]
        calm = [r for r, d in zip(rows, dates) if all(abs((d - e).days) > CALM_GAP for e in ev_d) and r["zc"] is not None]
        n_calm = len(calm)
        for what, ds in evs:
            e = dt.date.fromisoformat(ds)
            pre = [r for r, d in zip(rows, dates) if 0 < (e - d).days <= PRE and r["zc"] is not None]
            win = [(r, d) for r, d in zip(rows, dates) if 0 < (e - d).days <= LOOK]
            def lead(test):
                for r, d in win:
                    if test(r):
                        return (e - d).days
                return None
            rank = engine.rank
            m = {"theatre": t, "event": what, "date": ds, "pre_days": len(pre), "calm_days": n_calm,
                 "auc_new": auc([r["zc"] for r in pre], [r["zc"] for r in calm]),
                 "auc_old": auc([r["oldp"] for r in pre], [r["oldp"] for r in calm]),
                 "lead_watch": lead(lambda r: rank(r["lvl"]) >= 1), "lead_elev": lead(lambda r: rank(r["lvl"]) >= 2),
                 "lead_old_watch": lead(lambda r: r["old"] in ("Watch", "Warning", "Alert")), "lead_old_warn": lead(lambda r: r["old"] in ("Warning", "Alert")),
                 "fpr_watch": sum(1 for r in calm if engine.rank(r["lvl"]) >= 1) / n_calm if n_calm else None,
                 "fpr_elev": sum(1 for r in calm if engine.rank(r["lvl"]) >= 2) / n_calm if n_calm else None,
                 "fpr_old_watch": sum(1 for r in calm if r["old"] in ("Watch", "Warning", "Alert")) / n_calm if n_calm else None,
                 "fpr_old_warn": sum(1 for r in calm if r["old"] in ("Warning", "Alert")) / n_calm if n_calm else None}
            out.append(m)
    return out


def calibration(res):
    """Empirical 90/95/99th percentiles of the composite on calm days against the thresholds the null simulation set."""
    out = []
    for t, rows in res.items():
        ev_d = [dt.date.fromisoformat(d) for _, d in EVENTS.get(t, [])]
        calm = sorted(r["zc"] for r in rows if r["zc"] is not None and all(abs((dt.date.fromisoformat(r["d"]) - e).days) > CALM_GAP for e in ev_d))
        if len(calm) < 100:
            continue
        pct = lambda p: calm[min(len(calm) - 1, int(p * len(calm)))]
        out.append({"theatre": t, "n": len(calm), "p90": pct(.9), "p95": pct(.95), "p99": pct(.99)})
    return out


def sensitivity(series, weights, d, theatre):
    """Leave-one-signal-out and leave-one-domain-out at one date. Reports how far the theatre's composite moves and whether the
    ranking of all theatres (Spearman) survives."""
    rows = snapshot(series, d)
    base = {}
    day, calib = evaluate_day(rows, sorted({r["theatre"] for r in rows if r["theatre"] != "global"}), weights)
    for t, (new, _, _) in day.items():
        if new["zc"] is not None:
            base[t] = new["zc"]
    full = base.get(theatre)
    if full is None:
        return None
    ts = sorted(base)
    drops, worst_rho = [], 1.0
    for r in rows:
        if r["theatre"] != theatre or not r["score"]:
            continue
        rest = [x for x in rows if x is not r]
        new, _, _ = evaluate(rest, theatre, weights, calib)
        z = new["zc"] if new["zc"] is not None else full
        rho = spearman([base[t] for t in ts], [z if t == theatre else base[t] for t in ts]) if len(ts) > 2 else 1.0
        worst_rho = min(worst_rho, rho)
        drops.append((r["id"], z - full, rho))
    drops.sort(key=lambda x: -abs(x[1]))
    dom = []
    for dname in C.DOMAINS:
        rest = [x for x in rows if not (x["theatre"] == theatre and x["domain"] == dname)]
        new, _, _ = evaluate(rest, theatre, weights, calib)
        dom.append((dname, (new["zc"] if new["zc"] is not None else full) - full))
    return {"theatre": theatre, "date": d.isoformat(), "zc": full, "signals": drops, "domains": dom, "min_rho": worst_rho, "n_theatres": len(ts)}


# ------------------------------------------------------------------ report
f1 = lambda v: "n/a" if v is None else f"{v:.2f}"
pc = lambda v: "n/a" if v is None else f"{100 * v:.1f}%"
ld = lambda v: "never (within 60 days)" if v is None else f"{v} days"


def write_report(res, mets, cal, snaps, sens, coverage, weights):
    L = ["# Warwatch v7 backtest and validation", "",
         f"Generated by `warwatch/backtest.py run`. Replay window {START} to {END}, every {STEP} days. Weights version {weights['version']}.", "",
         "## What this tests, and what it cannot", "",
         "Only series whose source still serves old data can be replayed. The live feeds that carry the early signals (military aircraft, ships, fires, GNSS jamming, news counts) only exist from 2026, so they cannot be replayed. "
         "This backtest therefore checks the aggregation maths and the slower indicators (prices, shipping transits, advisories, procurement, trade, conflict counts). "
         "It does **not** show how well the leading OSINT set would have warned. Treat lead times below as what the slow indicators alone would have done.", "",
         "Each series is replayed with the delay its source really has (monthly data about two months late, PortWatch a week), so a day's score uses only data public on that day. "
         "Revisions to old data are ignored.", "", "### Series available per theatre", "",
         "| Theatre | Series replayed | Domains with data |", "|---|---|---|"]
    for t, (n, doms) in sorted(coverage.items()):
        L.append(f"| {C.THEATRES[t]['name']} | {n} | {', '.join(sorted(doms)) or 'none'} |")
    L += ["", "With one to four series per theatre and two or three domains, these are thin tests. The numbers show the machinery behaves sensibly; they are not evidence of forecasting skill.", "",
          "## Lead time, discrimination and false positives", "",
          f"Positive days are the {PRE} days before the event; calm days are all days more than {CALM_GAP} days from any listed event. "
          "AUC is the chance that a pre-event day scores higher than a calm day (0.5 = coin flip). "
          "Lead time is how many days before the event the level first reached the stated line in the {0} days before it. "
          "False-positive rate is the share of calm days at or above the line. The old method is compared on its own lines (Watch, and Warning-or-Alert) and on a continuous stand-in for its 0 to 5 count (firing groups x 10 + mean of the two strongest group scores).".format(LOOK), "",
          "| Theatre | Event | AUC new | AUC old | Lead: new Watch | Lead: new Elevated | Lead: old Watch | Lead: old Warning | FPR new Watch | FPR new Elevated | FPR old Watch | FPR old Warning |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in mets:
        L.append(f"| {C.THEATRES[m['theatre']]['name']} | {m['event']} ({m['date']}) | {f1(m['auc_new'])} | {f1(m['auc_old'])} | {ld(m['lead_watch'])} | {ld(m['lead_elev'])} | {ld(m['lead_old_watch'])} | {ld(m['lead_old_warn'])} | "
                 f"{pc(m['fpr_watch'])} | {pc(m['fpr_elev'])} | {pc(m['fpr_old_watch'])} | {pc(m['fpr_old_warn'])} |")
    L += ["", "## Threshold calibration", "",
          "Production thresholds come from a seeded Monte Carlo of a calm world (every signal a mildly heavy-tailed standard normal) pushed through the same pipeline, taking its 90th, 95th and 99th percentiles for Watch, Elevated and Critical. "
          "Most theatres have under a year of history for their live signals, so empirical percentiles are not usable in production. Where this replay has enough calm days it checks the null thresholds against the real composite:", "",
          "| Theatre | Calm days | Empirical 90th | Empirical 95th | Empirical 99th |", "|---|---|---|---|---|"]
    for c in cal:
        L.append(f"| {C.THEATRES[c['theatre']]['name']} | {c['n']} | {c['p90']:.2f} | {c['p95']:.2f} | {c['p99']:.2f} |")
    L += ["", "Compare with the thresholds each theatre shows on the dashboard (`th` in the page data, also in `site/audit.json`). If the empirical percentile sits well above the null one, the level fires more often than the stated 10%, 5% and 1%.", "",
          "## Before and after on three snapshots", ""]
    for title, t, ds, new, old, drivers in snaps:
        L += [f"### {title} ({ds})", "",
              f"- **Old method:** {old['level']}; groups firing: {', '.join(old['firing']) or 'none'} ({len(old['firing'])}/5).",
              f"- **New method:** {new['level']}; threat score {f1(new['score'])}/100; composite z {f1(new['zc'])}; imbalance {f1(new['imbalance'])}; confidence {new['conf_label']} ({new['scorable']} domains scored).", "",
              "| Domain | Weight | Domain score | Contribution to composite | Old group score | Strongest signals |", "|---|---|---|---|---|---|"]
        for dname in C.DOMAINS:
            x = new["doms"][dname]
            oz = old["domains"].get(dname)
            L.append(f"| {C.DOMAINS[dname]} | {x['w']:.2f} | {f1(x['z'])} | {x['contrib']:+.2f} | {f1(oz)} | {', '.join(f'{i} {z:+.1f}' for i, z in x['drivers']) or 'no data'} |")
        L += ["", "The contributions add up to the weighted mean of the domain scores (exact, so equal to each domain's Shapley share of that mean); the imbalance term of the Mazziotta-Pareto index is extra and only ever raises the index.", ""]
    L += ["## Sensitivity", "",
          "Each signal is removed in turn and the day is re-scored. 'Max change' is the largest shift of the theatre's composite z; 'rank correlation' is the Spearman correlation between the full ranking of all theatres and the ranking with that one signal removed (1.0 = unchanged).", ""]
    for s in sens:
        if not s:
            continue
        L += [f"### {C.THEATRES[s['theatre']]['name']}, {s['date']} (composite z {s['zc']:.2f}, {s['n_theatres']} theatres ranked)", "",
              f"Lowest rank correlation over all single-signal removals: **{s['min_rho']:.3f}**.", "", "| Signal removed | Change in composite z | Rank correlation |", "|---|---|---|"]
        for i, dz, rho in s["signals"][:8]:
            L.append(f"| {i} | {dz:+.3f} | {rho:.3f} |")
        L += ["", "| Domain removed | Change in composite z |", "|---|---|"] + [f"| {C.DOMAINS[d]} | {dz:+.3f} |" for d, dz in s["domains"]] + [""]
    L += ["## Reading this honestly", "",
          "- The replay covers a handful of events, each with at most four slow series. Lead times of days to weeks here mostly reflect market and shipping reactions, not forecasts.",
          "- The old method's AUC uses a stand-in score because the 0 to 5 count is too coarse to rank days.",
          "- Weights are expert priors and were not tuned on these events. Tuning them on four events would overfit.",
          "- HAPI conflict counts are published about two months late and the replay assumes that delay, so they rarely help before an event.", ""]
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "BACKTEST.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def cmd_run():
    series = load_series()
    if not series:
        sys.exit("no histories: run `backtest.py fetch` first")
    wv = engine.load_weights()
    theatres = sorted({s["theatre"] for s in series if s["theatre"] != "global"})
    res = replay(series, wv["weights"], theatres)
    mets = metrics(res)
    cal = calibration(res)
    cov = {}
    for t in theatres:
        ss = [s for s in series if s["theatre"] == t]
        cov[t] = (len(ss), {s["domain"] for s in ss})
    snaps, sens = [], []
    for title, t, ds in SNAPSHOTS:
        d = dt.date.fromisoformat(ds)
        rows = snapshot(series, d)
        day, _ = evaluate_day(rows, sorted({r["theatre"] for r in rows if r["theatre"] != "global"}), wv["weights"])
        new, _, old = day[t]
        snaps.append((title, t, ds, new, old, None))
        sens.append(sensitivity(series, wv["weights"], d, t))
    write_report(res, mets, cal, snaps, sens, cov, wv)
    os.makedirs(os.path.join(ROOT, "backtest"), exist_ok=True)
    with open(os.path.join(ROOT, "backtest", "results.json"), "w") as f:
        json.dump({"weights_version": wv["version"], "step_days": STEP, "metrics": mets, "calibration": cal,
                   "series": {t: [[r["d"], r["zc"], r["lvl"], r["old"]] for r in rows] for t, rows in res.items()}}, f, separators=(",", ":"))
    print("wrote docs/BACKTEST.md")


def cmd_weights():
    wv = engine.load_weights()
    doms = list(C.DOMAINS)
    with open(os.path.join(DOCS, f"weights_{wv['version']}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["version", "theatre"] + doms + ["rationale"])
        for t, ws in wv["weights"].items():
            w.writerow([wv["version"], t] + [ws[d] for d in doms] + [wv["rationale"][t]])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"fetch": lambda: cmd_fetch(set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None), "run": cmd_run, "weights": cmd_weights}[cmd]()
