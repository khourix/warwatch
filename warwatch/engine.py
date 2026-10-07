"""Composite threat engine (v7). Standard library only, deterministic, every intermediate kept for audit.

series -> modified z (stats.score_series: 90-day baseline, winsorized +-5)
       -> redundancy groups (correlated series are averaged, so one signal is not counted twice)
       -> domain score (OWA over the strongest groups, orness 0.3: agreement is needed, one spike is not enough)
       -> theatre composite: weighted Mazziotta-Pareto index over domains (non-compensatory: a lopsided
          profile is not averaged away), then level by calibrated thresholds
       -> region -> global (same idea, see rollup).
See docs/METHODOLOGY.md for the reasoning and the departures from the brief.
"""
import bisect
import json
import math
import os
import random
import statistics
import zlib

import config as C
import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ORNESS = 0.3          # 0 = min (all must agree), 0.5 = mean, 1 = max
TOPK = 6              # a domain looks at its strongest TOPK groups, so 40 quiet series cannot dilute one real signal
LONE = 0.7            # a domain with a single scorable group is shrunk: one source alone is weak evidence
CORR_MIN = 0.8        # redundancy: groups whose recent changes correlate above this are averaged
CORR_DAYS, CORR_MONTHS = 30, 24
NULL_N = 2000
PCTS = (0.90, 0.95, 0.99)     # Watch, Elevated, Critical thresholds, as percentiles of the calm-world distribution
LEVELS = ("Normal", "Watch", "Elevated", "Critical")
SEED = 20261007


def load_weights(version=None):
    with open(os.path.join(HERE, "weights.json"), encoding="utf-8") as f:
        doc = json.load(f)
    ver = version or doc["current"]
    for v in doc["versions"]:
        if v["version"] == ver:
            return {"version": ver, "weights": v["weights"], "rationale": v["rationale"]}
    raise KeyError(ver)


def owa_weights(n, orness=ORNESS):
    """Exponential OWA weights for n ranked inputs (rank 1 = strongest), solved so the orness matches."""
    if n == 1:
        return [1.0]
    def orn(r):
        w = [r ** i for i in range(n)]
        t = sum(w)
        return sum(x / t * (n - 1 - i) / (n - 1) for i, x in enumerate(w))
    lo, hi = 1e-6, 1e6   # r<1 favours the strongest (or-like), r>1 the weakest (and-like)
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        if orn(mid) > orness:
            lo = mid
        else:
            hi = mid
    r = math.sqrt(lo * hi)
    w = [r ** i for i in range(n)]
    t = sum(w)
    return [x / t for x in w]


def mpi(values, weights):
    """Weighted Mazziotta-Pareto index of domain scores on a 100 +- 10 scale. Risk goes up with the
    score, so the imbalance penalty is added (MPI+ = M + S * S/M): a lopsided profile reads higher
    than an even one with the same mean. -> (M, S, MPI)."""
    tw = sum(weights)
    idx = [100 + 10 * v for v in values]
    m = sum(w * x for w, x in zip(weights, idx)) / tw
    sd = math.sqrt(sum(w * (x - m) ** 2 for w, x in zip(weights, idx)) / tw)
    return m, sd, m + sd * sd / m


def _pearson(a, b):
    n = len(a)
    if n < 10:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def _changes(points, kind):
    """Recent day-on-day (month-on-month) changes keyed by label, signed so that up = worse."""
    n = CORR_DAYS + 1 if kind == "daily" else CORR_MONTHS + 1
    pts = points[-n:]
    return {pts[i][0]: pts[i][1] - pts[i - 1][1] for i in range(1, len(pts))}


def groups_of(items):
    """Union series whose recent changes correlate above CORR_MIN. Differences, not levels: two
    trending series correlate by construction. items: dicts with id, kind, z, sign, ch (changes)."""
    parent = list(range(len(items)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a["kind"] != b["kind"]:
                continue
            keys = sorted(set(a["ch"]) & set(b["ch"]))
            r = _pearson([a["ch"][k] * a["sign"] for k in keys], [b["ch"][k] * b["sign"] for k in keys])
            if r is not None and r > CORR_MIN:
                parent[find(i)] = find(j)
                pairs.append((a["id"], b["id"], round(r, 2)))
    out = {}
    for i in range(len(items)):
        out.setdefault(find(i), []).append(items[i])
    return list(out.values()), pairs


def domain_score(zs):
    """OWA over the strongest TOPK group scores. -> (score, [(rank weight, z)])."""
    zs = sorted(zs, reverse=True)[:TOPK]
    w = owa_weights(len(zs))
    sc = sum(a * b for a, b in zip(w, zs))
    if len(zs) == 1:
        sc *= LONE
    return sc, list(zip(w, zs))


def theatre_items(series, theatre):
    out = []
    for s in series:
        if s["theatre"] != theatre or not s.get("score"):
            continue
        d = s["direction"]
        sign = -1 if d == "down" else 1
        z = {"up": s["score"]["z"], "down": -s["score"]["z"]}.get(d, abs(s["score"]["z"]))
        out.append({"id": s["id"], "domain": s["domain"], "z": z, "lag": bool(s["lag"]), "kind": s["kind"], "sign": sign,
                    "both": d not in ("up", "down"), "miss": s["score"].get("miss", 0.0), "raw": s["score"].get("z_raw", s["score"]["z"]),
                    "ch": _changes(s["points"], s["kind"])})
    return out


_DOMS = {}


def _dom_null(flags):
    """Calm-world distribution of one domain's score: its groups' z drawn from a mildly heavy-tailed standard normal
    (10% of draws are twice as wide), winsorized, then the same OWA as production. Seeded from the shape.
    -> (sorted-by-draw list of scores, mean, sd)."""
    if flags not in _DOMS:
        rnd = random.Random(zlib.crc32(repr((SEED, flags)).encode()))
        norm = 1 / math.sqrt(1.3)
        arr = []
        for _ in range(NULL_N):
            zs = []
            for both in flags:
                z = max(-stats.WINSOR, min(stats.WINSOR, rnd.gauss(0, 1) * (2.0 if rnd.random() < 0.1 else 1.0) * norm))
                zs.append(abs(z) if both else z)
            arr.append(domain_score(zs)[0])
        m = statistics.fmean(arr)
        _DOMS[flags] = (arr, m, statistics.pstdev(arr) or 1e-6)
    return _DOMS[flags]


def estimate_calib(results):
    """Empirical null (Efron): real signals are more spread out and more persistent than independent standard normals,
    so the calm-world domain scores are re-centred and re-scaled to match the bulk of the live domain scores.
    Each live domain score is standardised against its simulated calm distribution; the median of those is the shift
    (mu), 1.4826 x the median absolute deviation the stretch (kappa). A few real crises barely move a median/MAD.
    -> (mu, kappa), clamped to [-0.5, 1] and [1, 3]."""
    u = []
    for r in results:
        for d in r["doms"].values():
            if d["z"] is not None and d.get("shape") is not None and r["theatre"] != "global":
                _, m, sd = _dom_null(tuple(d["shape"]))
                u.append((d["z"] - m) / sd)
    if len(u) < 8:
        return (0.0, 1.0)
    med = statistics.median(u)
    mad = statistics.median(abs(x - med) for x in u)
    return (max(-0.5, min(1.0, med)), max(1.0, min(3.0, 1.4826 * mad)))


_NULLS = {}


def thresholds(shape, weights, key, calib=(0.0, 1.0)):
    ck = (shape, tuple(round(c, 2) for c in calib), tuple(round(weights[d], 4) for d in C.DOMAINS))
    if ck not in _NULLS:
        mu, kap = calib
        parts = [(weights[d], _dom_null(tuple(fl))) for d, fl in shape if fl]
        out = []
        for i in range(NULL_N):
            vals = [m + mu * sd + kap * (arr[i] - m) for _, (arr, m, sd) in parts]
            out.append((mpi(vals, [w for w, _ in parts])[2] - 100) / 10)
        out.sort()
        _NULLS[ck] = out
    n = _NULLS[ck]
    return n, [n[min(len(n) - 1, int(p * len(n)))] for p in PCTS]


def logistic_score(zc, th):
    """0-100: 50 at the Watch threshold, 90 at the Critical one."""
    z90, z99 = th[0], th[2]
    tau = max(1e-6, (z99 - z90) / math.log(9))
    x = max(-50, min(50, -(zc - z90) / tau))
    return 100 / (1 + math.exp(x))


def theatre_composite(series, theatre, wt, calib=(0.0, 1.0)):
    """One theatre. wt = load_weights()['weights'][theatre]. Returns the dashboard fields plus an audit trail."""
    items = theatre_items(series, theatre)
    total = sum(1 for s in series if s["theatre"] == theatre)
    doms, audit_groups = {}, {}
    pairs_all = []
    for dom in C.DOMAINS:
        its = [i for i in items if i["domain"] == dom]
        if not its:
            doms[dom] = {"z": None, "n": 0, "fast": False, "drivers": [], "w": wt[dom], "contrib": 0.0}
            continue
        grp, pairs = groups_of(its)
        pairs_all += pairs
        rows = []
        for g in grp:
            best = max(g, key=lambda i: i["z"])
            rows.append({"z": sum(i["z"] for i in g) / len(g), "ids": [i["id"] for i in g], "best": best["id"],
                         "fast": any(not i["lag"] for i in g), "both": all(i["both"] for i in g)})
        rows.sort(key=lambda r: -r["z"])
        sc, ranked = domain_score([r["z"] for r in rows])
        doms[dom] = {"z": sc, "n": len(its), "groups": len(rows), "fast": rows[0]["fast"],
                     "drivers": [(r["best"], round(r["z"], 2)) for r in rows[:3]], "w": wt[dom], "contrib": 0.0,
                     "shape": sorted(r["both"] for r in rows)}
        audit_groups[dom] = [{"ids": r["ids"], "z": round(r["z"], 3), "owa_w": round(ranked[k][0], 3) if k < len(ranked) else 0} for k, r in enumerate(rows)]
    live = [d for d in C.DOMAINS if doms[d]["z"] is not None]
    scored = len(items)
    cov_series = scored / total if total else 0.0
    missing = round(1 - cov_series, 3)
    conf_label = "Low" if missing > 0.2 else "Medium" if missing > 0.1 else "High"
    wcov = sum(wt[d] for d in live)
    mean_miss = statistics.fmean(i["miss"] for i in items) if items else 0.0
    res = {"theatre": theatre, "level": "insufficient data", "score": None, "zc": None, "index": None, "imbalance": None,
           "worst": None, "confidence": round(wcov * cov_series * (1 - mean_miss), 3), "conf_label": conf_label,
           "missing": missing, "firing": [], "scorable": len(live), "basis": "", "doms": doms, "th": None}
    if items:
        w = max(items, key=lambda i: i["z"])
        res["worst"] = {"id": w["id"], "z": round(w["z"], 2), "lag": w["lag"]}
    if len(live) < 2:
        return res, {"groups": audit_groups, "correlated": pairs_all}
    vals = [doms[d]["z"] for d in live]
    ws = [wt[d] for d in live]
    m, sd, idx = mpi(vals, ws)
    tw = sum(ws)
    for d in live:
        doms[d]["contrib"] = round(wt[d] / tw * doms[d]["z"], 3)
    shape = tuple((d, tuple(doms[d]["shape"]) if d in live else ()) for d in C.DOMAINS)
    null, th = thresholds(shape, wt, theatre, calib)
    zc = (idx - 100) / 10
    lvl = LEVELS[sum(zc >= t for t in th)]
    firing = sorted(d for d in live if doms[d]["z"] >= C.THRESH_WATCH)
    basis = ""
    if lvl in ("Elevated", "Critical"):
        basis = "leading and lagging" if any(doms[d]["fast"] for d in firing) else "lagging only"
    res.update(level=lvl, zc=round(zc, 3), index=round(idx, 2), score=round(logistic_score(zc, th), 1),
               imbalance=round(sd, 2), firing=firing, basis=basis, th=[round(t, 3) for t in th], calib=[round(c, 2) for c in calib],
               pctl=round(100 * bisect.bisect_left(null, zc) / len(null), 1))
    return res, {"groups": audit_groups, "correlated": pairs_all, "mean": round(m, 2), "sd": round(sd, 2), "mpi": round(idx, 2)}


def rank(level):
    return {"insufficient data": -1}.get(level, LEVELS.index(level) if level in LEVELS else -1)


def rollup(theatres, regions):
    """Region = worst child level (a crisis is not averaged away), score = highest child score, index = MPI+ of child
    composites. Global Threat Index = MPI+ of the region scores (0-100), level = worst region level."""
    out = []
    for rid, name, kids in regions:
        ch = [theatres[k] for k in kids if theatres[k]["score"] is not None]
        if not ch:
            out.append({"id": rid, "name": name, "kids": kids, "level": "insufficient data", "score": None})
            continue
        top = max(ch, key=lambda t: (rank(t["level"]), t["score"]))
        zs = [t["zc"] for t in ch]
        idx = mpi(zs, [1] * len(zs))[2]
        out.append({"id": rid, "name": name, "kids": kids, "level": top["level"], "score": max(t["score"] for t in ch),
                    "index": round(idx, 2), "lead": top["theatre"]})
    live = [r for r in out if r["score"] is not None]
    if not live:
        return out, {"level": "insufficient data", "score": None}
    sc = [r["score"] for r in live]
    m = statistics.fmean(sc)
    sd = statistics.pstdev(sc)
    gti = min(100.0, m + sd * sd / m) if m else 0.0
    worst = max(live, key=lambda r: (rank(r["level"]), r["score"]))
    return out, {"score": round(gti, 1), "level": worst["level"], "lead": worst["id"],
                 "counts": {l: sum(1 for r in live if r["level"] == l) for l in LEVELS}}


def compute_composite_score(metrics, weights, baseline_window=90):
    """Stand-alone entry point for one theatre or portfolio.
    metrics: {name: {"domain": str, "direction": "up|down|both", "kind": "daily|monthly", "lag": bool,
                     "points": [(label, value), ...]}}; weights: {domain: weight}.
    -> {"level", "score", "zc", "index", "imbalance", "worst", "confidence", "domains", "audit"}"""
    series = []
    for name, m in metrics.items():
        sc = stats.score_series(m["points"], m.get("kind", "daily"), baseline_window)
        series.append({"id": name, "theatre": "x", "domain": m["domain"], "direction": m.get("direction", "up"), "lag": m.get("lag", False),
                       "kind": m.get("kind", "daily"), "points": m["points"], "score": sc})
    res, audit = theatre_composite(series, "x", weights)
    res["audit"] = audit
    return res


def evaluate_all(series, theatres, wv_weights):
    """Two passes: plain, then re-run with the empirical-null calibration estimated from all theatres."""
    first = {t: theatre_composite(series, t, wv_weights[t]) for t in theatres}
    calib = estimate_calib([r for r, _ in first.values()])
    return {t: theatre_composite(series, t, wv_weights[t], calib) for t in theatres}, calib


def evaluate(series, regions=None, version=None):
    wv = load_weights(version)
    both, calib = evaluate_all(series, list(C.THEATRES), wv["weights"])
    th = {t: r for t, (r, _) in both.items()}
    audit = {t: a for t, (_, a) in both.items()}
    reg, gti = rollup(th, regions if regions is not None else C.REGIONS)
    return {"theatres": th, "regions": reg, "global": gti, "weights_version": wv["version"], "audit": audit, "calib": calib}
