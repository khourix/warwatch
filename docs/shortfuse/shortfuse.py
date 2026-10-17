#!/usr/bin/env python3
"""Short-fuse study: which signals, alone or combined, are on in the 7 days before an event onset (PLAN.md).

Reads the WarWatch repo read-only (loaders from leadstudy, basestudy, tells, sourcestudy's fire mapping) and writes
results.json next to this file. RESULTS.md is written by hand from results.json.

    python3 docs/shortfuse/shortfuse.py [/path/to/warwatch]
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import sys
from collections import defaultdict

REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "warwatch"))
import leadstudy as L  # noqa: E402
import basestudy as BS  # noqa: E402
import basewatch as BW  # noqa: E402
import tells as T  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BF = os.path.join(REPO, "backfill", "data")
DATA = os.path.join(REPO, "warwatch", "data")
THEATRES = L.THEATRES
ALIAS = {"iran": ["iran", "iraq", "gulf"], "israel": ["israel", "lebanon", "syria"]}
FIRE_BOX = {"ukraine": "ukraine", "europe_east": "europe_east", "iran": "iran", "yemen": "yemen", "israel": "israel", "korea": "korea", "libya": "libya"}
GAP, W, CALM_PAD, MIN_DATA = 30, 7, 30, 4
CUT = 2.0
START, END = dt.date(2018, 1, 1), dt.date(2026, 10, 16)
K_TESTS = 15
ALPHA = 0.05 / K_TESTS
FA_MAX = 0.20
D1 = dt.timedelta(1)


def boxes(th):
    return ALIAS.get(th, [th])


# ------------------------------------------------------------------ events
def load_events():
    with open(os.path.join(DATA, "events_added.csv"), newline="", encoding="utf-8") as f:
        add = {(r["date"], r["theatre"], r["description"]) for r in csv.DictReader(f)}
    ev = defaultdict(list)
    with open(os.path.join(DATA, "events.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ev[r["theatre"]].append((dt.date.fromisoformat(r["date"]), (r["date"], r["theatre"], r["description"]) in add, r["description"]))
    allev = {t: sorted(e[0] for e in v) for t, v in ev.items()}
    on = {}
    for t, v in ev.items():
        v = sorted(set(v))
        out, last = [], None
        for e in v:
            if last is None or (e[0] - last).days > GAP:
                out.append(e)
            last = e[0]
        on[t] = out
    return on, allev


# ------------------------------------------------------------------ per family: {theatre: {data day: (fired, score)}}
def z_family(path_fmt, transform=None):
    out = {}
    for th in THEATRES:
        merged = {}
        for b in boxes(th):
            p = path_fmt.format(b=b)
            if not os.path.exists(p):
                continue
            pts = L.daily(p)
            if transform:
                pts = transform(pts)
            for d, z in L.zseries(pts).items():
                if d not in merged or z > merged[d]:
                    merged[d] = z
        if len(merged) >= 200:
            out[th] = {d: (z >= CUT, z) for d, z in merged.items()}
    return out


def fire_family(col):
    out = {}
    for th, b in FIRE_BOX.items():
        targets = [th] + (["iraq", "gulf"] if th == "iran" else ["lebanon", "syria"] if th == "israel" else [])
        p = os.path.join(BF, "firecls", f"firms_cls_{b}.csv")
        if not os.path.exists(p):
            continue
        pts = {}
        with open(p) as f:
            for r in csv.DictReader(f):
                if col == "anom":
                    pts[dt.date.fromisoformat(r["date"])] = float(r["anom"]) + float(r["hot"])
                else:
                    pts[dt.date.fromisoformat(r["date"])] = float(r[col])
        z = L.zseries(pts)
        for t in targets:
            if t in THEATRES:
                out[t] = {d: (v >= CUT, v) for d, v in z.items()}
    return out


def firms_anom_family():
    # the published replay series (anom + hot), as FIREANOM.md uses
    out = {}
    for th, b in FIRE_BOX.items():
        p = os.path.join(BF, "firecls", f"firms_anom_{b}.csv")
        z = L.zseries(L.daily(p))
        out[th] = {d: (v >= CUT, v) for d, v in z.items()}
    return out


def gdelt_family():
    rows = defaultdict(dict)
    for p in sorted(glob.glob(os.path.join(BF, "gdeltwide", "*.csv"))):
        with open(p) as fh:
            for r in csv.DictReader(fh):
                if float(r["loc_all"]) >= 50:
                    rows[r["theatre"]][dt.date.fromisoformat(r["day"])] = 1000.0 * float(r["loc_q4"]) / float(r["loc_all"])
    out = {}
    for th in THEATRES:
        merged = {}
        for b in boxes(th):
            for d, z in L.zseries(rows.get(b, {})).items():
                if d not in merged or z > merged[d]:
                    merged[d] = z
        if len(merged) >= 200:
            out[th] = {d: (z >= CUT, z) for d, z in merged.items()}
    return out


def base_family():
    sites = BW.load_bases()
    rows = BS.load_scenes()
    passes = BS.site_passes(rows, sites)
    d1 = max(ds[-1] for ds, _ in passes.values())
    ser = BS.daily(sites, passes, BS.START - dt.timedelta(30), d1)
    out = {}
    for th in THEATRES:
        merged = {}
        for b in boxes(th):
            for d, (n, _) in ser.get(b, {}).items():
                merged[d] = max(merged.get(d, 0), n)
        if merged:
            out[th] = {d: (n >= 1, float(n)) for d, n in merged.items()}
    return out


TELL_IDS = ["departure", "leave", "sea", "wave", "tankers"]


def tell_families():
    get = T.history_lookup()
    by = {tid: {} for tid in TELL_IDS}
    for tell in T.TELLS:
        if tell["id"] not in TELL_IDS:
            continue
        for th in THEATRES:
            merged = {}
            for b in boxes(th):
                pts = T._resolve(tell, b, get)
                days = sorted({d for _, p in pts for d, _ in p})
                if len(days) < 120:
                    continue
                d, end = dt.date.fromisoformat(days[59]), dt.date.fromisoformat(days[-1])
                while d <= end:
                    ok, _ = T.fires(tell, pts, d.isoformat())
                    merged[d] = merged.get(d, False) or bool(ok)
                    d += D1
            if merged:
                by[tell["id"]][th] = {d: (v, float(v)) for d, v in merged.items()}
    return by


def union(fams, need_all=False):
    """Data-day union of families: fired if any fired; score = max."""
    out = {}
    for th in THEATRES:
        parts = [f.get(th) for f in fams]
        if need_all and not all(parts):
            continue
        parts = [p for p in parts if p]
        if not parts:
            continue
        m = {}
        for p in parts:
            for d, (fi, s) in p.items():
                a = m.get(d)
                m[d] = (fi or (a[0] if a else False), max(s, a[1]) if a else s)
        out[th] = m
    return out


# ------------------------------------------------------------------ scoring days
def scoring(fam):
    """{theatre: {scoring day: (on, score, n data days)}} for d where any of d-7..d-1 has data."""
    out = {}
    for th, ser in fam.items():
        days = sorted(ser)
        a, b = days[0] + D1, days[-1] + D1
        res = {}
        d = a
        while d <= b:
            v = [ser[x] for x in (d - dt.timedelta(k) for k in range(1, W + 1)) if x in ser]
            if v:
                res[d] = (any(x[0] for x in v), max(x[1] for x in v), len(v))
            d += D1
        out[th] = res
    return out


def window(sc, first, last, ndata=None):
    """(hit, valid) for scoring days first..last."""
    v = [sc.get(first + dt.timedelta(k)) for k in range((last - first).days + 1)]
    v = [x for x in v if x is not None]
    if not v:
        return None
    if ndata is not None and not ndata(first, last):
        return None
    return any(x[0] for x in v)


def ndata_fn(fam, th):
    ser = fam.get(th, {})

    def f(first, last):
        lo, hi = first - dt.timedelta(W), last - D1
        return sum(1 for k in range((hi - lo).days + 1) if lo + dt.timedelta(k) in ser) >= MIN_DATA
    return f


def fisher(a, b, c, d):
    return BS.fisher_greater(a, b, c, d)


def auc_within(sc_all, allev, onsets):
    """Within-theatre day-level AUC: positives = onset in d+1..d+7, negatives = calm days; weighted by positives."""
    tot_w, acc = 0, 0.0
    for th, sc in sc_all.items():
        ons = {e[0] for e in onsets.get(th, [])}
        evd = allev.get(th, [])
        pos, neg = [], []
        for d, (on, s, n) in sc.items():
            if any(d + dt.timedelta(k) in ons for k in range(1, W + 1)):
                pos.append(s)
            elif not any(-CALM_PAD - W <= (e - d).days <= CALM_PAD + W for e in evd):
                neg.append(s)
        if not pos or not neg:
            continue
        allv = sorted([(x, 1) for x in pos] + [(x, 0) for x in neg])
        # rank-sum with ties
        ranks, i = {}, 0
        rs = 0.0
        while i < len(allv):
            j = i
            while j < len(allv) and allv[j][0] == allv[i][0]:
                j += 1
            r = (i + j + 1) / 2.0
            rs += r * sum(1 for k in range(i, j) if allv[k][1] == 1)
            i = j
        a = (rs - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
        acc += a * len(pos)
        tot_w += len(pos)
    return acc / tot_w if tot_w else None


def evaluate(name, sc_all, onsets, allev, valid_fn, continuous=True):
    ev = {"orig": [], "added": []}
    calm = []
    e_minus1 = {"orig": [], "added": []}
    span = [None, None]
    theatres = []
    for th, sc in sc_all.items():
        if not sc:
            continue
        lo, hi = min(sc), max(sc)
        span = [min(lo, span[0]) if span[0] else lo, max(hi, span[1]) if span[1] else hi]
        theatres.append(th)
        vf = valid_fn(th)
        for E, added, desc in onsets.get(th, []):
            h = window(sc, E - dt.timedelta(W), E - D1, vf)
            if h is None:
                continue
            ev["added" if added else "orig"].append((th, E.isoformat(), desc, h))
            x = sc.get(E - D1)
            if x is not None:
                e_minus1["added" if added else "orig"].append(x[0])
        evd = allev.get(th, [])
        s = max(lo, START)
        while s + dt.timedelta(W - 1) <= hi:
            e = s + dt.timedelta(W - 1)
            if not any(s - dt.timedelta(CALM_PAD) <= x <= e + dt.timedelta(CALM_PAD) for x in evd):
                h = window(sc, s, e, vf)
                if h is not None:
                    calm.append(h)
            s += dt.timedelta(W)
    nc, c = len(calm), sum(calm)
    fa = c / nc if nc else float("nan")
    calm_day = [x[0] for sc in sc_all.values() for d, x in sc.items()]
    r = {"name": name, "span": [span[0].isoformat() if span[0] else None, span[1].isoformat() if span[1] else None],
         "theatres": sorted(theatres), "calm_blocks": nc, "calm_fired": c, "fa": fa}
    for k in ("orig", "added", "pooled"):
        lst = ev["orig"] + ev["added"] if k == "pooled" else ev[k]
        n, h = len(lst), sum(x[3] for x in lst)
        hr = h / n if n else float("nan")
        r[k] = {"n": n, "hits": h, "hit_rate": hr, "lift": (hr / fa) if n and fa and fa == fa else None,
                "p": fisher(h, n - h, c, nc - c) if n and nc else None}
    m1 = e_minus1["orig"] + e_minus1["added"]
    r["on_day_before"] = {"events": len(m1), "share": (sum(m1) / len(m1)) if m1 else None}
    r["auc_within"] = auc_within(sc_all, allev, onsets) if continuous else None
    r["hit_events"] = [x[:3] for x in ev["orig"] + ev["added"] if x[3]]
    return r


def verdict(r, holdout_only=False):
    o, a = r["orig"], r["added"]
    po, pa = o["p"], a["p"]
    lift_ok = lambda x: x["lift"] is not None and x["lift"] > 1  # noqa: E731
    if holdout_only:
        r["passes"] = bool(pa is not None and pa < ALPHA and r["fa"] <= FA_MAX)
        r["close"] = bool(pa is not None and pa < 0.05 and lift_ok(a))
    else:
        r["passes"] = bool(po is not None and pa is not None and po < ALPHA and pa < ALPHA and r["fa"] <= FA_MAX)
        r["close"] = bool(po is not None and pa is not None and po < 0.05 and pa < 0.05 and lift_ok(o) and lift_ok(a))
    return r


def profile(sc_all, onsets, allev, label):
    """Mean score (and share on) on days -14..0 relative to onsets, against calm days."""
    acc = {k: [] for k in range(-14, 1)}
    on = {k: [] for k in range(-14, 1)}
    calm_s, calm_on = [], []
    for th, sc in sc_all.items():
        evd = allev.get(th, [])
        for E, added, desc in onsets.get(th, []):
            for k in range(-14, 1):
                x = sc.get(E + dt.timedelta(k))
                if x is not None:
                    acc[k].append(x[1])
                    on[k].append(x[0])
        for d, x in sc.items():
            if not any(-CALM_PAD - W <= (e - d).days <= CALM_PAD + W for e in evd):
                calm_s.append(x[1])
                calm_on.append(x[0])
    mean = lambda v: (sum(v) / len(v)) if v else None  # noqa: E731
    return {"days": {str(k): {"n": len(acc[k]), "mean_score": mean(acc[k]), "share_on": mean([float(b) for b in on[k]])} for k in acc},
            "calm": {"n": len(calm_s), "mean_score": mean(calm_s), "share_on": mean([float(b) for b in calm_on])},
            "score_is": label}


# ------------------------------------------------------------------ main
def main():
    onsets, allev = load_events()
    print("loading families", flush=True)
    fams = {
        "base": base_family(),
        "firms_anom": firms_anom_family(),
        "adsb_tanker": z_family(os.path.join(BF, "adsb_{b}_tanker.csv")),
        "adsb_fighter": z_family(os.path.join(BF, "adsb_{b}_fighter.csv")),
        "adsb_lift": z_family(os.path.join(BF, "adsb_{b}_lift.csv")),
        "nga": z_family(os.path.join(BF, "nga_{b}.csv")),
        "sar": z_family(os.path.join(BF, "sar_{b}.csv")),
        "gdelt_accel": gdelt_family(),
        "wiki": z_family(os.path.join(BF, "wiki_{b}.csv")),
        "fire_site": fire_family("esite"),
    }
    print("replaying tells", flush=True)
    tf = tell_families()
    fams["tells"] = union([tf[k] for k in TELL_IDS])
    tells_dip = union([tf[k] for k in ("departure", "leave", "wave")])
    singles = ["base", "firms_anom", "adsb_tanker", "adsb_fighter", "adsb_lift", "nga", "sar", "gdelt_accel", "wiki", "tells", "fire_site"]
    sc = {k: scoring(fams[k]) for k in singles}
    res = {}
    for k in singles:
        binary = k in ("tells",)
        res[k] = verdict(evaluate(k, sc[k], onsets, allev, lambda th, k=k: ndata_fn(fams[k], th), continuous=not binary))
        print(k, res[k]["orig"], res[k]["added"], round(res[k]["fa"], 3), flush=True)

    # domains at the scoring-day level
    domains = {
        "air": scoring(union([fams["adsb_tanker"], fams["adsb_fighter"], fams["adsb_lift"]])),
        "sea": scoring(union([fams["nga"], fams["sar"]])),
        "ground": sc["base"],
        "fire": sc["firms_anom"],
        "diplomatic": scoring(tells_dip),
        "attention": scoring(union([fams["wiki"], fams["gdelt_accel"]])),
    }

    def count_sc(kmin):
        out = {}
        for th in THEATRES:
            days = set()
            for dsc in domains.values():
                days |= set(dsc.get(th, {}))
            m = {}
            for d in days:
                have = [dsc[th][d] for dsc in domains.values() if th in dsc and d in dsc[th]]
                if len(have) < kmin:
                    continue
                n = sum(1 for x in have if x[0])
                m[d] = (n >= kmin, float(n), len(have))
            if m:
                out[th] = m
        return out

    for k, kmin in (("conv2", 2), ("conv3", 3)):
        s = count_sc(kmin)
        sc[k] = s
        res[k] = verdict(evaluate(k, s, onsets, allev, lambda th: None))
        print(k, res[k]["orig"], res[k]["added"], round(res[k]["fa"], 3), flush=True)

    # satellite-confirmed air
    air2 = scoring(union([fams["adsb_tanker"], fams["adsb_lift"]]))
    s = {}
    for th in THEATRES:
        a, b = air2.get(th, {}), sc["base"].get(th, {})
        m = {d: (a[d][0] and b[d][0], float(a[d][0]) + float(b[d][0]), 0) for d in set(a) & set(b)}
        if m:
            s[th] = m
    sc["sat_air"] = s
    res["sat_air"] = verdict(evaluate("sat_air", s, onsets, allev, lambda th: None))
    print("sat_air", res["sat_air"]["orig"], res["sat_air"]["added"], round(res["sat_air"]["fa"], 3), flush=True)

    # short-fuse index: weights from original events only
    idx_fams = [k for k in singles if k != "fire_site"]      # fire_site is a restricted copy of firms_anom
    weights = {}
    for k in idx_fams:
        o = res[k]["orig"]
        if o["n"] == 0 or res[k]["calm_blocks"] == 0:
            weights[k] = 0.0
            continue
        lift = o["lift"]          # raw lift on original events, as PLAN.md says (amendment 1: run 1 smoothed it by mistake)
        weights[k] = round(math.log(lift), 3) if lift is not None and lift > 1 else 0.0
    wsum = sum(weights.values())
    raw = {}
    for th in THEATRES:
        days = set()
        for k in idx_fams:
            if weights[k] > 0:
                days |= set(sc[k].get(th, {}))
        m = {}
        for d in days:
            v = sum(weights[k] for k in idx_fams if weights[k] > 0 and th in sc[k] and d in sc[k][th] and sc[k][th][d][0])
            m[d] = 100.0 * v / wsum if wsum else 0.0
        if m:
            raw[th] = m
    # cut: lowest index value that keeps calm-block false alarms at 20% or less
    cands = sorted({round(v, 6) for m in raw.values() for v in m.values() if v > 0})
    cut_pick = None
    for cv in cands:
        s = {th: {d: (v >= cv - 1e-9, v, 0) for d, v in m.items()} for th, m in raw.items()}
        r = evaluate("index", s, onsets, allev, lambda th: None, continuous=False)
        if r["fa"] <= FA_MAX:
            cut_pick = cv
            break
    s = {th: {d: (v >= cut_pick - 1e-9, v, 0) for d, v in m.items()} for th, m in raw.items()}
    sc["index"] = s
    res["index"] = verdict(evaluate("index", s, onsets, allev, lambda th: None), holdout_only=True)
    res["index"]["weights"] = weights
    res["index"]["cut"] = cut_pick
    print("index", weights, cut_pick, res["index"]["orig"], res["index"]["added"], round(res["index"]["fa"], 3), flush=True)

    # top 3 by pooled p, profile
    ranked = sorted(res, key=lambda k: (res[k]["pooled"]["p"] if res[k]["pooled"]["p"] is not None else 2))
    top = ranked[:3]
    lab = lambda k: ("index value 0-100" if k == "index" else "domains on (0-6)" if k.startswith("conv") else  # noqa: E731
                     "tanker/lift on + base on (0-2)" if k == "sat_air" else "tell on (0/1)" if k == "tells" else
                     "sites out or in" if k == "base" else "max z in trailing 7 days")
    prof = {k: profile(sc[k], onsets, allev, lab(k)) for k in top}
    # also the index and conv2 profiles, since they are the proposed metric shapes
    for k in ("index", "conv2"):
        if k not in prof:
            prof[k] = profile(sc[k], onsets, allev, lab(k))
    out = {"made": dt.date.today().isoformat(), "plan": "PLAN.md", "alpha_bonferroni": ALPHA, "k_tests": K_TESTS, "fa_max": FA_MAX,
           "candidates": res, "ranked_by_pooled_p": ranked, "top3": top, "profiles": prof}
    with open(os.path.join(HERE, "results.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("top3", top)


if __name__ == "__main__":
    main()
