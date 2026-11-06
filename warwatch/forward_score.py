#!/usr/bin/env python3
"""Scores the forward record (forward/log.csv): every probability the live build logged, checked against what happened. Standard library only.

    python3 warwatch/forward_score.py     # verify the hash chain, score matured forecasts, write docs/FORWARD.md

A forecast matures 30 days after it was made, once the events file is complete through that day (warwatch/data/events_through.txt: whoever adds
events moves it). Days within 30 days after an event are left out, as in validation. Run quarterly by .github/workflows/forward-score.yml.

The two hidden models are scored the same way on their own records: the armed-force model (forward/log_armed.csv) on armed-force events, and
the 7-day strike-wave model (forward/log_wave.csv) on the strike waves its feeds show, 7 days ahead, and the model without the conflict-history
terms (forward/log_nohist.csv, candidate S1 of docs/PREDSTUDY_NEXT_PLAN.md) on the page's events, as is the free LLM forecaster
(forward/log_llm.csv, warwatch/llmcast.py). Each report ends with the forward gates;
the first target to pass them on 90 or more matured days is the one to promote (docs/METHODOLOGY.md, Phase C).
"""
import datetime as dt
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model  # noqa: E402

DOCS = os.path.join(os.path.dirname(HERE), "docs")


def auc(pairs):
    """Mann-Whitney AUC by ranks (ties count half): O(n log n), so the shuffled-timing control stays quick on a year of days."""
    xs = sorted(pairs, key=lambda x: x[0])
    n1 = sum(1 for _, y in xs if y)
    n0 = len(xs) - n1
    if not n1 or not n0:
        return None
    rank_sum, i = 0.0, 0
    while i < len(xs):
        j = i
        while j < len(xs) and xs[j][0] == xs[i][0]:
            j += 1
        r = (i + j + 1) / 2                     # mean rank of the tie block (1-based)
        rank_sum += r * sum(1 for k in range(i, j) if xs[k][1])
        i = j
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0)


FORWARD_DAYS = 90     # matured forecast days before the first interim report
READ_DAYS = 365       # the one read that can promote a target, fixed in advance (docs/PREDSTUDY_PLAN.md and the prediction study)
TARGETS = 5           # forecasts read (main, armed, wave, the no-history candidate, and the LLM forecaster): the shuffled-timing p must beat 0.05 / TARGETS
SHIFTS = 1000


def score(rows, events, through, bands, horizon=30, after=None):
    """-> dict of results over matured theatre forecasts: positive when an event follows within `horizon` days; days within `after`
    days after an event are left out."""
    after = model.AFTERMATH if after is None else after
    by = {}
    for t, d in events:
        by.setdefault(t, []).append(d)
    out, anyrows = [], {}
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        if d + dt.timedelta(days=horizon) > through:
            continue
        if r["theatre"] == "_any":
            hit = any(0 < (e - d).days <= horizon for ds in by.values() for e in ds)
            anyrows[r["date"]] = (float(r["p"]), hit)
            continue
        ds = by.get(r["theatre"], [])
        if any(0 <= (d - e).days <= after for e in ds):
            continue
        out.append((float(r["p"]), float(r["base"]), any(0 < (e - d).days <= horizon for e in ds), r))
    return out, anyrows


def _within_auc(scored):
    """Positives-weighted mean of each theatre's own AUC: does the forecast rank a theatre's days, not just the theatres?"""
    by = {}
    for p, _, y, r in scored:
        by.setdefault(r["theatre"], []).append((p, y))
    num = den = 0.0
    for v in by.values():
        a = auc(v)
        if a is not None:
            n1 = sum(y for _, y in v)
            num += n1 * a
            den += n1
    return num / den if den else None


def shuffled_timing(scored, n=SHIFTS, seed=2):
    """The backtest's control (validate.shifted_control) on the forward record: each theatre's probabilities are shifted circularly in time
    against its outcomes, which keeps which theatres run hot and how the forecast moves, and breaks its timing. -> (p for AUC, p for
    within-theatre AUC), the share of shifts that score at least as well."""
    by = {}
    for p, _, y, r in sorted(scored, key=lambda x: x[3]["date"]):
        by.setdefault(r["theatre"], []).append((p, y, r))
    a0 = auc([(p, y) for p, _, y, _ in scored])
    w0 = _within_auc(scored)
    if a0 is None:
        return None, None
    rng, ge_a, ge_w = random.Random(seed), 0, 0
    for _ in range(n):
        sh = []
        for v in by.values():
            k = len(v)
            m = max(1, min(30, k // 4))
            off = rng.randint(m, k - m) if k > 2 * m else 0
            ps = [x[0] for x in v]
            ps = ps[off:] + ps[:off]
            sh += [(ps[i], 0.0, v[i][1], v[i][2]) for i in range(k)]
        ge_a += (auc([(p, y) for p, _, y, _ in sh]) or 0) >= a0
        ge_w += w0 is not None and (_within_auc(sh) or 0) >= w0
    return ge_a / n, (ge_w / n if w0 is not None else None)


def gates(scored, B=500, seed=1, read_days=READ_DAYS, targets=TARGETS):
    """Forward gates, read once `read_days` days have matured: Brier skill against the base rate above 0, the lower end of the AUC interval
    (resampling theatre-months) above 0.5, and the shuffled-timing control beaten at 0.05 / targets. The first two alone pass as often for a
    forecast with its timing scrambled as for the real one (prediction study, section 2), so the third is what tests timing.
    Before read_days, the same numbers are reported as an interim description that cannot promote. -> dict."""
    days = len({r["date"] for _, _, _, r in scored})
    pos = sum(y for _, _, y, _ in scored)
    if days < FORWARD_DAYS or not pos or pos == len(scored):
        return {"days": days, "ready": False, "final": False, "pass": False}
    bss = 1 - sum((p - y) ** 2 for p, _, y, _ in scored) / sum((b - y) ** 2 for _, b, y, _ in scored)
    cl = {}
    for p, _, y, r in scored:
        cl.setdefault((r["theatre"], r["date"][:7]), []).append((p, y))
    keys, rng, boot = sorted(cl), random.Random(seed), []
    for _ in range(B):
        a = auc([x for k in (rng.choice(keys) for _ in keys) for x in cl[k]])
        if a is not None:
            boot.append(a)
    boot.sort()
    lo = boot[int(0.025 * (len(boot) - 1))] if boot else 0.0
    p_auc, p_within = shuffled_timing(scored)
    alpha = 0.05 / targets
    final = days >= read_days
    ok = bss > 0 and lo > 0.5 and p_auc is not None and p_auc < alpha
    return {"days": days, "ready": True, "final": final, "bss": bss, "auc_lo": lo, "within": _within_auc(scored), "shuffle_p": p_auc,
            "shuffle_p_within": p_within, "alpha": alpha, "would_pass": ok, "pass": ok and final}


KINDS = {   # record, model file, report, title, events, horizon
    "main": (model.FORWARD, None, "FORWARD.md", "", lambda: model.load_events(), 30),
    "armed": (model.FORWARD_ARMED, model.ARMED_MODEL, "FORWARD_ARMED.md", ", armed-force shadow model (hidden from the page)", lambda: model.load_events(types=model.ARMED_TYPES), 30),
    "nohist": (model.FORWARD_NOHIST, model.NOHIST_MODEL, "FORWARD_NOHIST.md", ", model without conflict-history terms (candidate S1, hidden from the page)", lambda: model.load_events(), 30),
    "llm": (os.path.join(model.ROOT, "forward", "log_llm.csv"), None, "FORWARD_LLM.md", ", free LLM forecaster (Gemini, hidden from the page)", lambda: model.load_events(), 30),
    "wave": (model.FORWARD_WAVE, model.WAVE_MODEL, "FORWARD_WAVE.md", ", 7-day strike-wave shadow model (hidden from the page)", lambda: model.wave_events(), model.WAVE_HORIZON),
}


def _through(kind, m, series=None):
    """The last day outcomes are known for: the events file's date, or for the wave record the oldest wave feed's newest day."""
    if kind == "wave":
        ths = m.get("theatres") or list(model.WAVE_FEEDS)
        return min(dt.date.fromisoformat(model.wave_points(model.WAVE_FEEDS[t], series)[-1][0][:10]) for t in ths)
    with open(os.path.join(HERE, "data", "events_through.txt")) as f:
        return dt.date.fromisoformat(f.read().strip())


def _log_loss(pairs):
    return sum(-math.log(min(max(p if y else 1 - p, 1e-6), 1.0)) for p, y in pairs) / len(pairs)


def describe(scored):
    """Descriptions, never gates: the log score next to the Brier score, and, on the days a liquid market was priced, the market and the
    blend the page would publish if the blend were switched on (model.blend; MKT_WEIGHT, MKT_CAL), each against the same days' base rate."""
    L = ["", "Descriptions (not gates):", "", "| Forecast | Days | Events | Brier | Log score | Brier skill vs base |", "|---|---|---|---|---|---|"]

    def line(name, trip):
        n = len(trip)
        if not n:
            return
        bs = sum((p - y) ** 2 for p, _, y in trip) / n
        bb = sum((b - y) ** 2 for _, b, y in trip) / n
        L.append(f"| {name} | {n:,} | {sum(y for _, _, y in trip):,} | {bs:.4f} | {_log_loss([(p, y) for p, _, y in trip]):.4f} | "
                 f"{'n/a' if not bb else f'{1 - bs / bb:+.3f}'} |")
    line("Published probability, all days", [(p, b, y) for p, b, y, _ in scored])
    line("Base rate, all days", [(b, b, y) for _, b, y, _ in scored])
    mk = [(p, b, y, float(r["p_market"])) for p, b, y, r in scored if r.get("p_market") not in (None, "")]
    line("Published probability, days with a market", [(p, b, y) for p, b, y, _ in mk])
    line("Market, calibrated", [(q, b, y) for _, b, y, q in mk])
    line(f"Blend ({model.MKT_WEIGHT:.0%} market in log-odds)", [(model.blend(p, q), b, y) for p, b, y, q in mk])
    return L


def evaluate(kind, series=None):
    """One record verified and scored. -> dict(ok, bad, rows, scored, anyrows, through, gates, horizon, bands)."""
    path, mpath, _, _, events, horizon = KINDS[kind]
    ok, bad, rows = model.forward_verify(path)
    m = model.load(mpath) or {"bands": [0.05, 0.10, 0.25]}
    through = _through(kind, m, series)
    ev = model.wave_events(series) if kind == "wave" else events()
    scored, anyrows = score(rows, ev, through, m["bands"], horizon, horizon) if ok else ([], {})
    return {"ok": ok, "bad": bad, "rows": rows, "scored": scored, "anyrows": anyrows, "through": through, "gates": gates(scored), "horizon": horizon, "bands": m["bands"]}


NAMES = {"main": "Any qualifying event within 30 days (the page's model)", "armed": "Armed force within 30 days (hidden)",
         "wave": "A new strike wave within 7 days, wars under way (hidden)"}


def scorecard(series=None):
    """The page's track-record panel: each target's forward record and its forward gates, numbers only once FORWARD_DAYS days have matured."""
    out = []
    for k in ("main", "armed", "wave"):
        try:
            e = evaluate(k, series)
        except Exception as x:       # a missing feed or model file must not break the page
            out.append({"k": k, "name": NAMES[k], "err": str(x)[:120]})
            continue
        g = e["gates"]
        out.append({"k": k, "name": NAMES[k], "h": e["horizon"], "chain": e["ok"], "first": e["rows"][0]["date"] if e["rows"] else None,
                    "logged": len({r["date"] for r in e["rows"]}), "days": g["days"], "need": FORWARD_DAYS, "through": e["through"].isoformat(),
                    "ready": g["ready"], "pass": g["pass"], "bss": round(g["bss"], 4) if g["ready"] else None, "auc_lo": round(g["auc_lo"], 3) if g["ready"] else None,
                    "shuffle_p": round(g["shuffle_p"], 3) if g["ready"] and g["shuffle_p"] is not None else None, "final": g.get("final", False), "read": READ_DAYS,
                    "auc": round(auc([(p, y) for p, _, y, _ in e["scored"]]) or 0, 3) if g["ready"] else None})
    return out


def main(kind="main"):
    path, mpath, name, title, _, horizon = KINDS[kind]
    os.makedirs(DOCS, exist_ok=True)
    e = evaluate(kind)
    ok, bad, rows, scored, anyrows, through, g, bands = (e[k] for k in ("ok", "bad", "rows", "scored", "anyrows", "through", "gates", "bands"))
    src = "the newest day of its alert-wave feeds" if kind == "wave" else "`warwatch/data/events_through.txt`"
    what = "a strike wave" if kind == "wave" else "an event"
    L = ["# Forward record" + title, "",
         f"Every day the live build appends its probabilities for every theatre it covers to `{os.path.relpath(path, model.ROOT)}` before any outcome is known. Each row carries the hash of the row before it, so a "
         f"later edit anywhere breaks the chain from that row on; `python3 warwatch/forward_score.py` checks it. This report scores the forecasts that have matured: made at least {horizon} days before "
         f"{src} ({through}), outside the {horizon} days after {what}.", "",
         f"Chain: **{'intact' if ok else f'BROKEN at row {bad}'}**, {len(rows):,} rows" + (f", {rows[0]['date']} to {rows[-1]['date']}." if rows else "."), ""]
    if len(scored) < 100:
        L += [f"Matured forecasts so far: {len(scored)}. Too few to score; the first report with numbers needs about a quarter of daily forecasts.", ""]
    else:
        n = len(scored)
        pos = sum(y for _, _, y, _ in scored)
        bs = sum((p - y) ** 2 for p, _, y, _ in scored) / n
        bb = sum((b - y) ** 2 for _, b, y, _ in scored) / n
        a = auc([(p, y) for p, _, y, _ in scored])
        L += [f"Matured forecasts: {n:,} theatre-days, {pos:,} followed by {what} within {horizon} days ({pos / n:.1%}).", "",
              "| Measure | Value |", "|---|---|", f"| Brier score of the published probability | {bs:.4f} |", f"| Brier score of each theatre's base rate | {bb:.4f} |",
              f"| Brier skill against the base rate | {1 - bs / bb:+.3f} |", f"| AUC | {'n/a' if a is None else f'{a:.3f}'} |", "",
              "| Level | Forecasts | Mean probability | Event rate that followed |", "|---|---|---|---|"]
        cuts = [0] + bands + [2]
        for i, nm in enumerate(model.LEVELS):
            sub = [(p, y) for p, _, y, _ in scored if cuts[i] <= p < cuts[i + 1]]
            L.append(f"| {nm} | {len(sub):,} | " + (f"{sum(p for p, _ in sub) / len(sub):.1%} | {sum(y for _, y in sub) / len(sub):.1%} |" if sub else "n/a | n/a |"))
        if anyrows:
            mp = sum(p for p, _ in anyrows.values()) / len(anyrows)
            fr = sum(h for _, h in anyrows.values()) / len(anyrows)
            L += ["", f"Chance of {what} in any theatre within {horizon} days: mean forecast {mp:.0%}, followed by one {fr:.0%} of days (an upper bound is expected, as theatres move together)."]
        L += describe(scored)
        L += ["", f"Compare with the validation report (`docs/{name.replace('FORWARD', 'MODEL')}`): the backtest can be tuned, this cannot."]
    L += ["", "## Forward gates", "",
          f"Read once, when {READ_DAYS} days have matured: Brier skill against the base rate above 0, the lower end of the AUC interval (resampling theatre-months) "
          f"above 0.5, and the AUC beating a shuffled-timing control (each theatre's probabilities shifted in time against its outcomes, {SHIFTS:,} shifts) at "
          f"p < 0.05 / {TARGETS} = {0.05 / TARGETS:.4f}, one share for each forecast read (any event in 30 days, armed force in 30 days, a strike wave in 7 days, any event in 30 days without the conflict-history terms, and the LLM forecaster's any event in 30 days). "
          f"The first two alone pass as often for a forecast with its timing scrambled as for the real one, so the third is what tests timing. "
          f"From {FORWARD_DAYS} matured days the same numbers are shown as an interim description; only the read at {READ_DAYS} days can promote a target.", ""]
    if not g["ready"]:
        L.append(f"Not read yet: {g['days']} of {FORWARD_DAYS} matured days for the first interim report, {READ_DAYS} for the read.")
    else:
        w = "n/a" if g["within"] is None else f"{g['within']:.3f}"
        sp = "n/a" if g["shuffle_p"] is None else f"{g['shuffle_p']:.3f}"
        head = (f"**{'PASS' if g['pass'] else 'FAIL'}**" if g["final"] else f"Interim ({g['days']} of {READ_DAYS} days, cannot promote): would {'pass' if g['would_pass'] else 'fail'}")
        L.append(f"{head}: Brier skill {g['bss']:+.3f}, AUC interval lower end {g['auc_lo']:.3f}, shuffled-timing p {sp}, within-theatre AUC {w}, on {g['days']} matured days.")
    with open(os.path.join(DOCS, name), "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote docs/" + name + ";", "chain intact" if ok else f"CHAIN BROKEN at row {bad}")
    return 0 if ok else 1


if __name__ == "__main__":
    rc = main()
    for k in ("armed", "wave", "nohist", "llm"):
        if os.path.exists(KINDS[k][0]):
            rc = main(k) or rc
    sys.exit(rc)
