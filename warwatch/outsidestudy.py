"""Outside forecasts (ConflictForecast, VIEWS) against past events, to the plan fixed before the data was read
(docs/OUTSIDE_PLAN.md). Reads backfill/data/forecasts/ (backfill/forecasts_compact.py), writes docs/OUTSIDE.md.

Test A (lead): the monthly series scored as the live build scores a monthly series, then the indicator study's test.
Test B (standing risk): the probability in force the day before each event against calm days, all theatres pooled.
Benchmark (description only, not part of the pass rule): on the days our 30-day model was tested out of sample, the
outside probability and our published probability ranked against the same labels.
"""
import csv
import datetime as dt
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backfill"))
import indicatorstudy as S  # noqa: E402
import sourcestudy as Q  # noqa: E402
import stats  # noqa: E402
import validate as V  # noqa: E402
from sources_forecasts import ISO  # noqa: E402

DIR = os.path.join(V.ROOT, "backfill", "data", "forecasts")
OUT = os.path.join(V.ROOT, "docs", "OUTSIDE.md")


def _next_month(y, m):
    return dt.date(y + (m == 12), m % 12 + 1, 1)


def cf_points(fam):
    """{theatre: [(public day, highest probability among its countries)]} for one ConflictForecast family."""
    by = {}
    for r in csv.DictReader(open(os.path.join(DIR, f"cf_{fam}.csv"))):
        m, y = int(r["vintage"][:2]), int(r["vintage"][3:])
        if r["all"] not in ("", "nan"):
            by.setdefault(_next_month(y, m), {})[r["isocode"]] = float(r["all"])
    return {th: [(d, max(v[i] for i in isos if i in v)) for d, v in sorted(by.items()) if any(i in v for i in isos)] for th, isos in ISO.items()}


def views_points():
    """VIEWS: first forecast month of each run; for one label month the newest model generation and the latest t wins."""
    runs = {}
    for r in csv.DictReader(open(os.path.join(DIR, "views.csv"))):
        runs.setdefault(r["run"], []).append(r)
    pick = {}
    for run in runs:
        gen, y, m, t = run.split("_")          # fatalities002_2024_01_t01
        if m == "00":
            continue                           # label month 00 is ambiguous; left out
        key = (int(y), int(m))
        if key not in pick or (gen, t) > pick[key][:2]:
            pick[key] = (gen, t, run)
    by = {}
    for (y, m), (_, _, run) in pick.items():
        first = {}
        for r in runs[run]:
            mid = int(r["month_id"])
            if r["isoab"] not in first or mid < first[r["isoab"]][0]:
                first[r["isoab"]] = (mid, float(r["main_dich"]))
        by[_next_month(y, m)] = {i: v for i, (_, v) in first.items()}
    return {th: [(d, max(v[i] for i in isos if i in v)) for d, v in sorted(by.items()) if any(i in v for i in isos)] for th, isos in ISO.items()}


def daily(points, until):
    """Carry each vintage forward day by day until the next one (a missing vintage leaves the previous one in force)."""
    out = {}
    for k, (d, v) in enumerate(points):
        end = points[k + 1][0] if k + 1 < len(points) else until
        while d < end:
            out[d] = v
            d += dt.timedelta(1)
    return out


def boot_auc(pos, neg, B=2000, seed=1):
    rng = np.random.default_rng(seed)
    pos, neg = np.asarray(pos), np.asarray(neg)
    a = [S.auc(list(rng.choice(pos, len(pos))), list(rng.choice(neg, len(neg)))) for _ in range(B)]
    return float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))


def test_b(pts, until):
    on, allev = S.events()
    lvl = {th: daily(p, until) for th, p in pts.items() if p}
    ev, calm = [], []
    for th, s in lvl.items():
        near = set()
        for d in allev.get(th, []):
            near.update(d + dt.timedelta(k) for k in range(-S.LEAD, S.GAP + 1))
        for r in on[on.theatre == th].itertuples():
            v = s.get(r.date - dt.timedelta(1))
            if v is not None:
                ev.append((v, r.added))
        d = min(s)
        while d <= max(s):
            if d not in near:
                calm.append(s[d])
            d += dt.timedelta(S.CALM_STEP)
    out = {"calm": len(calm), "start": min(min(s) for s in lvl.values()).isoformat()}
    for nm, sel in (("orig", lambda a: not a), ("added", lambda a: a)):
        w = [v for v, a in ev if sel(a)]
        out[nm] = {"n": len(w), "auc": S.auc(w, calm), "ci": boot_auc(w, calm) if len(w) >= 3 else (float("nan"), float("nan")),
                   "mean": float(np.mean(w)) if w else float("nan")}
    out["calm_mean"] = float(np.mean(calm))
    a = out["added"]
    out["pass"] = bool(a["n"] and a["auc"] >= 0.65 and a["ci"][0] > 0.5)
    return out


def test_a(pts, until):
    zs = {}
    for th, p in pts.items():
        z = []
        for i in range(len(p)):
            r = stats.score_series([(d.isoformat(), v) for d, v in p[max(0, i - 60):i + 1]], "monthly")
            if r is not None:
                z.append((p[i][0], r["z"]))
        if z:
            zs[th] = daily(z, until)
    return Q.test(zs) if zs else None


def benchmark(srcs, until):
    """Our model's out-of-sample published probability and each outside source on the same theatre-days."""
    W = json.load(open(os.path.join(V.DATA, "model_weights.json")))
    P, meta, fams, X, y, lab, eid, ev, through = V.prepare()
    raw, base = V.rolling(P, X, y, lab, W["lambda_w"])
    pub, _ = V.nested_published(P, raw, base, y, lab)
    ok = lab & (P["date"].dt.year.values >= V.TEST_YEARS[0]) & ~np.isnan(pub)
    th, dd = P["theatre"].values, P["date"].dt.date.values
    res = {}
    for nm, pts in srcs.items():
        lvl = {t: daily(p, until) for t, p in pts.items() if p}
        o = np.array([lvl.get(t, {}).get(d - dt.timedelta(1), np.nan) for t, d in zip(th, dd)])
        m = ok & ~np.isnan(o)
        cl = (P["theatre"] + P["date"].dt.year.astype(str)).values[m]
        res[nm] = {"days": int(m.sum()), "pos": int(y[m].sum()), "auc_ours": V.auc(y[m], pub[m]), "auc_ours_ci": V.cluster_boot_auc(y[m], pub[m], cl),
                   "auc_theirs": V.auc(y[m], o[m]), "auc_theirs_ci": V.cluster_boot_auc(y[m], o[m], cl),
                   "auc_both": V.auc(y[m], pub[m] / pub[m].std() + o[m] / o[m].std())}
    return res


def write(A, B, BM):
    f = lambda x, s: "n/a" if x != x else format(x, s)      # noqa: E731
    L = ["# Outside forecasts against past events", "",
         "Written by `warwatch/outsidestudy.py` to the plan fixed before the data was read ([OUTSIDE_PLAN.md](OUTSIDE_PLAN.md)). "
         "ConflictForecast: the full-model probability of armed conflict, or of any violence, in the next 3 months, for each theatre the highest among its countries, "
         "public from the first day of the month after its vintage. VIEWS: the probability of 25 or more state-based deaths in the first forecast month, same lag.", "",
         "## Test B: the probability itself, the day before each event, against calm days", "",
         "Pass: AUC of 0.65 or more on the added events, with the bootstrap 95% interval above 0.5.", "",
         "| Source | From | Calm days | Mean on calm days | Original events | Mean before | AUC (95% interval) | Added events | Mean before | AUC (95% interval) | Passes |",
         "|---|---|---:|---:|---:|---:|---|---:|---:|---|---|"]
    for nm, r in B.items():
        o, a = r["orig"], r["added"]
        L.append(f"| {nm} | {r['start']} | {r['calm']} | {r['calm_mean']:.2f} | {o['n']} | {f(o['mean'], '.2f')} | {f(o['auc'], '.2f')} ({f(o['ci'][0], '.2f')} to {f(o['ci'][1], '.2f')}) | "
                 f"{a['n']} | {f(a['mean'], '.2f')} | {f(a['auc'], '.2f')} ({f(a['ci'][0], '.2f')} to {f(a['ci'][1], '.2f')}) | {'yes' if r['pass'] else 'no'} |")
    L += ["", "## Test A: does the forecast rise before events?", "",
          "Each monthly series scored as the live build scores a monthly series (needs 40 months, so scores start late), then the indicator study's test. "
          "Pass: added events p < 0.05, original events p < 0.10, AUC above 0.55 on both.", "",
          "| Source | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for nm, r in A.items():
        if r is None:
            L.append(f"| {nm} | too few months to score | | | | | | | | | | no |")
            continue
        o, a = r["orig"], r["added"]
        L.append(f"| {nm} | {r['calm']} | {f(r['fa'], '.0%')} | {o['n']} | {f(o['hit'], '.0%')} | {f(o['p'], '.3f')} | {f(o['auc'], '.2f')} | "
                 f"{a['n']} | {f(a['hit'], '.0%')} | {f(a['p'], '.3f')} | {f(a['auc'], '.2f')} | {'yes' if r['pass'] else 'no'} |")
    if BM:
        L += ["", "## Benchmark against our 30-day model (description, not a test)", "",
              "On the theatre-days our model was tested out of sample (2021 on) where the outside forecast exists: AUC of each against the "
              "same label (an event in the theatre within 30 days), with intervals from resampling theatre-years. \"Both\" adds the two, each scaled by its spread.", "",
              "| Source | Days | Days before an event | Our model | Outside forecast | Both |", "|---|---:|---:|---|---|---:|"]
        for nm, r in BM.items():
            L.append(f"| {nm} | {r['days']} | {r['pos']} | {r['auc_ours']:.2f} ({r['auc_ours_ci'][0]:.2f} to {r['auc_ours_ci'][1]:.2f}) | "
                     f"{r['auc_theirs']:.2f} ({r['auc_theirs_ci'][0]:.2f} to {r['auc_theirs_ci'][1]:.2f}) | {r['auc_both']:.2f} |")
    L.append("")
    open(OUT, "w").write("\n".join(L))


def main(bench=True):
    until = dt.date.today()
    srcs = {"cf_armedconf_3": cf_points("armedconf_3"), "cf_anyviolence_3": cf_points("anyviolence_3"), "views": views_points()}
    B = {nm: test_b(p, until) for nm, p in srcs.items()}
    A = {nm: test_a(p, until) for nm, p in srcs.items()}
    BM = benchmark(srcs, until) if bench else {}
    write(A, B, BM)
    return A, B, BM


if __name__ == "__main__":
    A, B, BM = main("--no-bench" not in sys.argv)
    for nm in B:
        print(nm, "B", {k: B[nm][k] for k in ("orig", "added", "pass")})
        print(nm, "A", None if A[nm] is None else {k: A[nm][k] for k in ("orig", "added", "pass")})
        print(nm, "bench", BM.get(nm))
