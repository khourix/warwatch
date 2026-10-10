"""The 30-day event probability, per theatre (standard library only). Fitted and validated by validate.py, which writes data/model_weights.json.

    log-odds = theatre intercept + conflict history + sum over families of weight x evidence / 5
    evidence = max(0, warning-direction z), at most 5, the strongest series of the family in that theatre

The published probability is pulled toward the theatre's base rate (gamma) and floored at a share of it (phi); the interval is the
5th to 95th percentile over refits on resampled theatre-years. Each probability comes with its contributions in log-odds, so a reader
can see which families moved it. The model drives the page's levels only when its validation gates passed (`active` in the model
file); otherwise it runs in shadow and its probabilities go to the forward record only. See docs/MODEL.md and docs/EVENTS.md.
"""
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re

import config as C

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ROOT = os.path.dirname(HERE)
TH = [t for t in C.THEATRES if t != "global"]
LEVELS = ("Normal", "Watch", "Elevated", "Critical")
EVIDENCE_MAX = 5.0
AFTERMATH = 30       # days after an event during which the model is outside what it was validated on
MKT_CAL = (-0.76, 0.90)   # logit(true) = a + b logit(market p30), fitted on 602 Polymarket war markets priced 30 days before resolution (review, section 4)
MKT_WEIGHT = 0.30    # market share of the blend, in log-odds
MKT_MIN_VOLUME = 50000
FORWARD = os.path.join(ROOT, "forward", "log.csv")


def load(path=None):
    try:
        with open(path or os.path.join(DATA, "model_weights.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


ARMED_TYPES = ("onset", "strike", "maritime")
ARMED_MODEL = os.path.join(DATA, "model_weights_armed.json")
FORWARD_ARMED = os.path.join(ROOT, "forward", "log_armed.csv")


def load_events(path=None, types=None):
    out = []
    try:
        with open(path or os.path.join(DATA, "events.csv"), newline="") as f:
            for r in csv.DictReader(f):
                if types and r.get("type") not in types:
                    continue
                out.append((r["theatre"], dt.date.fromisoformat(r["date"])))
    except OSError:
        pass
    return out


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, x))))


_FAM = re.compile("_(" + "|".join(TH) + ")$")


WORLD = "world_tempo"     # the contributions of every global family, summed


def family(sid):
    return _FAM.sub("", sid)


def evidence(series, theatre):
    """{family: evidence 0..5} from this theatre's scored series and the global ones."""
    out = {}
    for s in series:
        if not s.get("score") or not s.get("scored", True) or s["theatre"] not in (theatre, "global"):
            continue
        z = s["score"]["z"]
        e = {"up": z, "down": -z}.get(s["direction"], abs(z))
        e = min(EVIDENCE_MAX, max(0.0, e))
        f = family(s["id"])
        out[f] = max(out.get(f, 0.0), e)
    return out


def history(events, theatre, today):
    """Scaled conflict-history terms, from events strictly before today: (events in the last year)/3, (last 3 years)/5, log days since the latest."""
    ds = [d for t, d in events if t == theatre and d < today]
    h1 = sum((today - d).days <= 365 for d in ds)
    h3 = sum((today - d).days <= 1095 for d in ds)
    since = min((today - max(ds)).days, 3650) if ds else 3650
    return [min(h1, 3) / 3, min(h3, 5) / 5, math.log1p(since) / math.log1p(3650)]


def _logit_raw(theta, theatre, hist, ev):
    z = theta["a0"] + theta["delta"].get(theatre, 0.0) + sum(c * h for c, h in zip(theta["hist"], hist))
    return z + sum(w * ev.get(f, 0.0) / EVIDENCE_MAX for f, w in theta["w"].items())


def shrink(p_raw, base, gamma, phi):
    return max(sigmoid(logit(base) + gamma * (logit(p_raw) - logit(base))), phi * base)


def level_of(p, bands):
    return LEVELS[sum(p >= b for b in bands)]


def predict(m, series, theatre, events, today):
    """-> dict(p, lo, hi, raw, level, contrib, aftermath) for one theatre."""
    ev = evidence(series, theatre)
    hist = history(events, theatre, today)
    th = m["theta"]
    z = _logit_raw(th, theatre, hist, ev)
    base = m["base"][theatre]
    cap = m.get("p_cap", 0.95)
    p = min(cap, shrink(sigmoid(z), base, m["gamma"], m["phi"]))
    bs = sorted(min(cap, shrink(sigmoid(_logit_raw(b, theatre, hist, ev)), base, m["gamma"], m["phi"])) for b in m.get("boot", []))
    lo, hi = (bs[int(0.05 * (len(bs) - 1))], bs[int(math.ceil(0.95 * (len(bs) - 1)))]) if bs else (p, p)
    contrib = [(f, round(w * ev[f] / EVIDENCE_MAX * m["gamma"], 3)) for f, w in th["w"].items() if ev.get(f) and w * ev[f] > 0]
    glob = {family(s["id"]) for s in series if s["theatre"] == "global"}
    world = round(sum(c for f, c in contrib if f in glob), 3)     # the global families add the same to every theatre: one line
    contrib = [(f, c) for f, c in contrib if f not in glob] + ([(WORLD, world)] if world > 0 else [])
    contrib.sort(key=lambda kv: -kv[1])
    hist_c = round(m["gamma"] * sum(c * h for c, h in zip(th["hist"], hist)), 3)
    last = max((d for t, d in events if t == theatre and d < today), default=None)
    return {"p": p, "lo": min(lo, p), "hi": max(hi, p), "raw": sigmoid(z), "base": base, "level": level_of(p, m["bands"]), "contrib": contrib[:6],
            "history": hist_c, "aftermath": bool(last and (today - last).days <= AFTERMATH)}


def market_probability(markets, theatre):
    """Volume-weighted log-odds mean of the theatre's liquid war markets, each put on a 30-day horizon and recalibrated. -> p or None."""
    xs = []
    today = dt.date.today()
    for mk in markets or []:
        if mk.get("theatre") != theatre or mk.get("vol", 0) < MKT_MIN_VOLUME or not (0.005 < mk.get("p", 0) < 0.995):
            continue
        try:
            days = max(1, (dt.date.fromisoformat(mk["end"]) - today).days)
        except (KeyError, ValueError):
            continue
        p30 = 1 - (1 - mk["p"]) ** (30.0 / days) if days > 30 else mk["p"]   # a deadline inside 30 days is taken as it stands
        p30 = min(max(p30, 0.005), 0.99)
        xs.append((MKT_CAL[0] + MKT_CAL[1] * logit(p30), mk["vol"]))
    if not xs:
        return None
    return sigmoid(sum(x * w for x, w in xs) / sum(w for _, w in xs))


def blend(p, p_mkt):
    return sigmoid((1 - MKT_WEIGHT) * logit(p) + MKT_WEIGHT * logit(p_mkt)) if p_mkt is not None else p


def global_view(m, per):
    """P(an event in at least one theatre) = 1 - prod(1 - p): an upper bound, theatres being positively correlated.
    Level: the odds against the climatological value, cut where the theatre bands cut the pooled base rate."""
    p_any = 1 - math.prod(1 - v["p"] for v in per.values())
    p_mm = 1 - math.prod(1 - v["p"] * m["mm_share"].get(t, 0.0) for t, v in per.items())
    odds = lambda p: p / (1 - p)
    ref = odds(m["p_any_clim"])
    ratio = odds(p_any) / ref
    cuts = [odds(b) / odds(m["pooled_base"]) for b in m["bands"]]
    lvl = LEVELS[0 if ratio < 1 else sum(ratio >= c for c in cuts)]
    return {"p_any": p_any, "p_market_moving": p_mm, "clim": m["p_any_clim"], "ratio": ratio, "level": lvl}


ALERT_DAYS = 7      # a level is set from the highest probability of the last 7 days (docs/IMPROVEMENTS.md: same events caught, fewer separate alarms)


def recent_max(today, days=ALERT_DAYS, path=None):
    """{theatre: highest logged probability on the days.. before today} from the forward record; empty where nothing is logged."""
    out = {}
    lo = (today - dt.timedelta(days=days - 1)).isoformat()
    try:
        with open(path or FORWARD, newline="") as f:
            for r in csv.DictReader(f):
                if lo <= r["date"] < today.isoformat() and r["theatre"] != "_any" and r["p"]:
                    out[r["theatre"]] = max(out.get(r["theatre"], 0.0), float(r["p"]))
    except OSError:
        pass
    return out


def apply(res, markets=None, today=None, events=None, m=None, forward_path=None):
    """Adds res['model'] (probabilities for every theatre) and, when the model is active, makes them the page's levels.
    Region and global levels are rebuilt from the new theatre levels. The composite level stays as 'level_composite'."""
    m = m or load()
    if not m:
        return res
    import engine
    today = today or dt.date.today()
    events = load_events() if events is None else events
    per = {}
    for t in TH:
        if t in res["theatres"]:
            per[t] = predict(m, res["series"], t, events, today)
            if markets is not None:
                pm = market_probability(markets, t)
                per[t]["p_market"] = pm
                per[t]["p_blend"] = blend(per[t]["p"], pm)
    recent = recent_max(today, path=forward_path)
    glob = global_view(m, per)
    res["model"] = {"version": m["version"], "fitted": m["fitted"], "active": bool(m.get("active")), "gates": m["gates"], "bands": m["bands"],
                    "theatres": per, "global": glob, "blend_active": bool(m.get("blend_active"))}
    for t, v in per.items():
        r = res["theatres"][t]
        r.update(p=v["p"], p_lo=v["lo"], p_hi=v["hi"], p_why=v["contrib"], p_aftermath=v["aftermath"], level_composite=r["level"])
        if m.get("active"):
            p_head = v["p_blend"] if m.get("blend_active") and v.get("p_blend") is not None else v["p"]
            r["p_alert"] = max(p_head, recent.get(t, 0.0))
            r["level"] = level_of(r["p_alert"], m["bands"])
    if m.get("active"):
        res["regions"], g = engine.rollup(res["theatres"], C.REGIONS)
        g["level_composite"] = res["global"]["level"]
        g.update(p_any=glob["p_any"], p_market_moving=glob["p_market_moving"])
        g["level"] = glob["level"]
        res["global"] = g
    else:
        res["global"].update(p_any=glob["p_any"], p_market_moving=glob["p_market_moving"])
    return res


def shadow(res, today=None, model_path=None, log_path=None):
    """Hidden armed-force model: predicts every theatre with the model trained on onset, strike and maritime events only and appends to its own
    forward record (forward/log_armed.csv). It never touches the page, the levels or the main record. Returns rows appended."""
    m = load(model_path or ARMED_MODEL)
    if not m or "model" not in res:
        return 0
    today = today or dt.date.today()
    events = load_events(types=ARMED_TYPES)
    per = {t: predict(m, res["series"], t, events, today) for t in TH if t in res["theatres"]}
    fake = {"model": {"theatres": per, "global": global_view(m, per), "active": False, "version": m["version"] + "-armed"}, "theatres": res["theatres"]}
    return forward_append(fake, path=log_path or FORWARD_ARMED)


# ------------------------------------------------------------------ forward record
FIELDS = ["date", "theatre", "p", "lo", "hi", "raw", "base", "level", "composite_level", "p_market", "active", "model", "prev_hash", "hash"]


def _digest(prev, row):
    body = "|".join(str(row[k]) for k in FIELDS[:-2])
    return hashlib.sha256((prev + "|" + body).encode()).hexdigest()


def forward_rows(res, day):
    m = res.get("model")
    if not m:
        return []
    rows = []
    for t, v in m["theatres"].items():
        pm = v.get("p_market")
        rows.append({"date": day, "theatre": t, "p": f"{v['p']:.5f}", "lo": f"{v['lo']:.5f}", "hi": f"{v['hi']:.5f}", "raw": f"{v['raw']:.5f}", "base": f"{v['base']:.5f}",
                     "level": v["level"], "composite_level": res["theatres"][t].get("level_composite", res["theatres"][t]["level"]),
                     "p_market": "" if pm is None else f"{pm:.5f}", "active": int(m["active"]), "model": m["version"]})
    g = m["global"]
    rows.append({"date": day, "theatre": "_any", "p": f"{g['p_any']:.5f}", "lo": "", "hi": "", "raw": "", "base": f"{g['clim']:.5f}", "level": g["level"],
                 "composite_level": "", "p_market": "", "active": int(m["active"]), "model": m["version"]})
    return rows


def forward_append(res, day=None, path=None):
    """Append today's probabilities to the hash-chained record, once per UTC day (the first build of the day: forecasts are logged
    before their outcome can be known). Each row's hash covers the previous row's, so an edit anywhere breaks the chain from there on."""
    path = path or FORWARD
    day = day or dt.datetime.now(dt.timezone.utc).date().isoformat()
    rows = forward_rows(res, day)
    if not rows:
        return 0
    old = []
    try:
        with open(path, newline="") as f:
            old = list(csv.DictReader(f))
    except OSError:
        pass
    if old and old[-1]["date"] >= day:
        return 0
    prev = old[-1]["hash"] if old else "0" * 64
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not old
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            r["prev_hash"] = prev
            r["hash"] = prev = _digest(r["prev_hash"], r)
            w.writerow(r)
    return len(rows)


def forward_verify(path=None):
    """-> (ok, first bad row number or None, rows)."""
    prev = "0" * 64
    rows = []
    if not os.path.exists(path or FORWARD):
        return True, None, rows   # nothing logged yet
    with open(path or FORWARD, newline="") as f:
        for i, r in enumerate(csv.DictReader(f), 1):
            if r["prev_hash"] != prev or _digest(prev, r) != r["hash"]:
                return False, i, rows
            prev = r["hash"]
            rows.append(r)
    return True, None, rows
