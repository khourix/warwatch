#!/usr/bin/env python3
"""Base watch against past events (docs/BASEWATCH_STUDY_PLAN.md and its amendment of 2026-10-17). Standard library only.

Replays the monitor's two-pass rule day by day over the backfilled Sentinel-1 scenes, counts per theatre and day the sites
"out" and "in", and compares how often that count is 1 or more in the 14 days before events with how often it is in calm
14-day windows. Writes docs/BASEWATCH_STUDY.md. Changes nothing the live page reads.

    python3 warwatch/basestudy.py
"""
import bisect
import csv
import datetime as dt
import gzip
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import basewatch as B  # noqa: E402

ROOT = os.path.dirname(HERE)
BACKFILL = os.path.join(ROOT, "backfill", "data", "basewatch", "scenes.csv.gz")
OUT = os.path.join(ROOT, "docs", "BASEWATCH_STUDY.md")
EVENTS = os.path.join(HERE, "data", "events.csv")
ADDED = os.path.join(HERE, "data", "events_added.csv")
START = dt.date(2022, 3, 1)
LEAD, GAP, STEP = 14, 30, 14
P_MAX, CALM_MAX = 0.05, 0.15
CASES = [("al_udeid", "2025-06-19", "aircraft dispersed before Iran's strike of 23 Jun 2025"),
         ("nsa_bahrain", "2026-02-26", "US ships left port before the strikes of 28 Feb 2026"),
         ("olenya", "2025-06-01", "bombers present, then struck on 1 Jun 2025")]


def load_scenes(backfill=BACKFILL, live=B.SCENES):
    rows = {}
    if os.path.exists(backfill):
        with gzip.open(backfill, "rt", newline="") as f:
            for r in csv.DictReader(f):
                rows[(r["scene_id"], r["site"], r["part"])] = r
    for r in B.read_csv(live):
        rows.setdefault((r["scene_id"], r["site"], r["part"]), r)
    return list(rows.values())


def site_passes(rows, sites):
    """{site id: ([dates], [z]) of scored passes on the site's main part, oldest first}."""
    metric = f"{B.METRIC}@{B.T_DB:g}"
    by = {}
    for r in rows:
        by.setdefault(r["site"], []).append(r)
    out = {}
    for s in sites:
        sr = by.get(s["id"], [])
        main = "harbour" if s["kind"] in ("naval", "port") else "apron"
        if not any(r["part"] == main for r in sr):
            main = "harbour" if any(r["part"] == "harbour" for r in sr) else "apron"
        sc = [(d, z) for d, _, _, z in B.scene_z(sr, metric, main) if z is not None]
        if sc:
            out[s["id"]] = ([dt.date.fromisoformat(d) for d, _ in sc], [z for _, z in sc])
    return out


def state_on(passes, day):
    """The monitor's state (alerts on) from the scored passes up to `day`: out, in, or other; None without a pass in 10 days."""
    ds, zs = passes
    k = bisect.bisect_right(ds, day)
    if k == 0 or (day - ds[k - 1]).days > 10:
        return None
    if k >= 2 and (ds[k - 1] - ds[k - 2]).days <= 7:
        if zs[k - 1] <= -B.Z_AT and zs[k - 2] <= -B.Z_AT:
            return "out"
        if zs[k - 1] >= B.Z_AT and zs[k - 2] >= B.Z_AT:
            return "in"
    return "other"


def daily(sites, passes, d0, d1):
    """{theatre: {day: (n out + n in, [site ids firing])}} on days where at least one of the theatre's sites has a state."""
    out = {}
    day = d0
    while day <= d1:
        st = {sid: state_on(p, day) for sid, p in passes.items()}
        for s in sites:
            v = st.get(s["id"])
            if v is None:
                continue
            for t in s["theatres"]:
                n, who = out.setdefault(t, {}).get(day, (0, []))
                if v in ("out", "in"):
                    n, who = n + 1, who + [f"{s['id']} {v}"]
                out[t][day] = (n, who)
        day += dt.timedelta(days=1)
    return out


def fired(series, end, days=LEAD):
    """True/False whether the count was 1 or more on any day of the `days` days before `end`; None with no data in them."""
    seen = [series[d] for d in (end - dt.timedelta(k) for k in range(1, days + 1)) if d in series]
    if not seen:
        return None
    return any(n >= 1 for n, _ in seen)


def fisher_greater(a, b, c, d):
    """One-sided Fisher exact p that events fire more often than calm windows. a, b: events fired, not; c, d: calm fired, not."""
    n1, n2, k = a + b, c + d, a + c
    N = n1 + n2
    tot = math.comb(N, k)
    return float(sum(math.comb(n1, x) * math.comb(n2, k - x) for x in range(a, min(n1, k) + 1)) / tot) if tot else 1.0


def events(theatres, d1, path=EVENTS, added=ADDED):
    with open(added, newline="", encoding="utf-8") as f:
        add = {(r["date"], r["theatre"]) for r in csv.DictReader(f)}
    seen, out = set(), []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = dt.date.fromisoformat(r["date"])
            key = (r["date"], r["theatre"])
            if START <= d <= d1 and r["theatre"] in theatres and key not in seen:
                seen.add(key)
                out.append({"date": d, "theatre": r["theatre"], "what": r["description"], "added": key in add})
    return out


def calm_windows(theatres, evs, d1):
    """[(theatre, window end)] for 14-day windows from START, stepped every 14 days, with no event of the theatre from 30
    days before the window to 30 days after it."""
    by = {}
    for e in evs:
        by.setdefault(e["theatre"], []).append(e["date"])
    out = []
    for t in sorted(theatres):
        s = START
        while s + dt.timedelta(LEAD) <= d1:
            e = s + dt.timedelta(LEAD)          # the window is the 14 days before e
            if not any(s - dt.timedelta(GAP) <= x <= e + dt.timedelta(GAP) for x in by.get(t, [])):
                out.append((t, e))
            s += dt.timedelta(STEP)
    return out


def study(rows=None, sites=None, write=True):
    sites = sites if sites is not None else B.load_bases()
    rows = rows if rows is not None else load_scenes()
    passes = site_passes(rows, sites)
    if not passes:
        raise SystemExit("no scored scenes: run the backfill first")
    d1 = max(ds[-1] for ds, _ in passes.values())
    theatres = {t for s in sites for t in s["theatres"]}
    ser = daily(sites, passes, START - dt.timedelta(LEAD), d1)
    evs = events(theatres, d1)
    res_ev = []
    for e in evs:
        f = fired(ser.get(e["theatre"], {}), e["date"])
        who = sorted({w for k in range(1, LEAD + 1) for w in ser.get(e["theatre"], {}).get(e["date"] - dt.timedelta(k), (0, []))[1]})
        res_ev.append(dict(e, fired=f, who=who))
    calm = [(t, end, fired(ser.get(t, {}), end)) for t, end in calm_windows(theatres, evs, d1)]
    scored = [e for e in res_ev if e["fired"] is not None]
    cs = [c for c in calm if c[2] is not None]
    a = sum(e["fired"] for e in scored)
    c = sum(f for _, _, f in cs)
    p = fisher_greater(a, len(scored) - a, c, len(cs) - c)
    calm_rate = c / len(cs) if cs else float("nan")
    ok = p < P_MAX and calm_rate <= CALM_MAX
    per_site = {}
    for t, end, f in cs:
        if f:
            for k in range(1, LEAD + 1):
                for w in ser.get(t, {}).get(end - dt.timedelta(k), (0, []))[1]:
                    per_site[w.split()[0]] = per_site.get(w.split()[0], 0) + 1
    res = {"pass": ok, "p": p, "hit": a, "n_ev": len(scored), "calm_fired": c, "n_calm": len(cs), "calm_rate": calm_rate,
           "nodata_ev": len(res_ev) - len(scored), "nodata_calm": len(calm) - len(cs), "events": res_ev, "per_site": per_site,
           "sites": len(passes), "d1": d1, "passes": passes, "series": ser}
    for lab, flag in (("original", False), ("added", True)):
        sub = [e for e in scored if e["added"] == flag]
        k = sum(e["fired"] for e in sub)
        res[lab] = (k, len(sub), fisher_greater(k, len(sub) - k, c, len(cs) - c))
    if write:
        write_md(res, sites)
    return res


def _pct(a, n):
    return f"{100 * a / n:.0f}%" if n else "n/a"


def write_md(r, sites, path=OUT):
    names = {s["id"]: s["name"] for s in sites}
    L = ["# Base watch against past events: result", "",
         f"Written by `warwatch/basestudy.py` on {dt.date.today().isoformat()} to the plan fixed before the backfill was read "
         "([BASEWATCH_STUDY_PLAN.md](BASEWATCH_STUDY_PLAN.md), amendment of 2026-10-17).", "",
         f"**Verdict: {'PASS' if r['pass'] else 'FAIL'}.** A base was out or in during the 14 days before "
         f"{r['hit']} of {r['n_ev']} events ({_pct(r['hit'], r['n_ev'])}), against {r['calm_fired']} of {r['n_calm']} calm windows "
         f"({_pct(r['calm_fired'], r['n_calm'])}); one-sided Fisher p = {r['p']:.3f}. The rule needs p < {P_MAX} and calm firing "
         f"of {CALM_MAX:.0%} or less.", "",
         f"Sites with scored radar passes: {r['sites']} of {len(sites)}. Scenes to {r['d1'].isoformat()}. Left out for lack of "
         f"data: {r['nodata_ev']} events and {r['nodata_calm']} calm windows.", "",
         "| Events | Fired before | Share | p against calm |", "|---|---:|---:|---:|"]
    for lab in ("original", "added"):
        k, n, p = r[lab]
        L.append(f"| {lab} | {k} of {n} | {_pct(k, n)} | {p:.3f} |")
    L += ["", "## Feasibility cases", "", "| Site | Case date | State in the 14 days before | What |", "|---|---|---|---|"]
    for sid, day, what in CASES:
        d = dt.date.fromisoformat(day)
        p = r["passes"].get(sid)
        sts = sorted({state_on(p, d - dt.timedelta(k)) or "no data" for k in range(0, LEAD)}) if p else ["no data"]
        L.append(f"| {names.get(sid, sid)} | {day} | {', '.join(sts)} | {what} |")
    L += ["", "## Sites that fired most in calm windows (the first to look at)", "", "| Site | Calm window-days firing |", "|---|---:|"]
    for sid, n in sorted(r["per_site"].items(), key=lambda x: -x[1])[:15]:
        L.append(f"| {names.get(sid, sid)} | {n} |")
    L += ["", "## Each event", "", "| Date | Theatre | Event | Fired | Sites |", "|---|---|---|---|---|"]
    for e in r["events"]:
        f = "no data" if e["fired"] is None else ("yes" if e["fired"] else "no")
        L.append(f"| {e['date']} | {e['theatre']} | {e['what'][:80]} | {f} | {'; '.join(e['who'][:4])} |")
    L += ["", "Contains modified Copernicus Sentinel data 2021–2026 (Sentinel-1 RTC via Microsoft Planetary Computer)."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    r = study()
    print(f"{'PASS' if r['pass'] else 'FAIL'}: events {r['hit']}/{r['n_ev']}, calm {r['calm_fired']}/{r['n_calm']}, p {r['p']:.4f}")
