#!/usr/bin/env python3
"""Scores the forward record (forward/log.csv): every probability the live build logged, checked against what happened. Standard library only.

    python3 warwatch/forward_score.py     # verify the hash chain, score matured forecasts, write docs/FORWARD.md

A forecast matures 30 days after it was made, once the events file is complete through that day (warwatch/data/events_through.txt: whoever adds
events moves it). Days within 30 days after an event are left out, as in validation. Run quarterly by .github/workflows/forward-score.yml.

The two hidden models are scored the same way on their own records: the armed-force model (forward/log_armed.csv) on armed-force events, and
the 7-day strike-wave model (forward/log_wave.csv) on the strike waves its feeds show, 7 days ahead. Each report ends with the forward gates;
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
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


FORWARD_DAYS = 90    # matured forecast days before the forward gates are read


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


def gates(scored, B=500, seed=1):
    """Forward gates: Brier skill against the base rate above 0, and the lower end of the AUC interval (resampling theatre-months) above 0.5,
    read once FORWARD_DAYS days have matured. -> dict."""
    days = len({r["date"] for _, _, _, r in scored})
    pos = sum(y for _, _, y, _ in scored)
    if days < FORWARD_DAYS or not pos or pos == len(scored):
        return {"days": days, "ready": False, "pass": False}
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
    return {"days": days, "ready": True, "bss": bss, "auc_lo": lo, "pass": bss > 0 and lo > 0.5}


KINDS = {   # record, model file, report, title, events, horizon
    "main": (model.FORWARD, None, "FORWARD.md", "", lambda: model.load_events(), 30),
    "armed": (model.FORWARD_ARMED, model.ARMED_MODEL, "FORWARD_ARMED.md", ", armed-force shadow model (hidden from the page)", lambda: model.load_events(types=model.ARMED_TYPES), 30),
    "wave": (model.FORWARD_WAVE, model.WAVE_MODEL, "FORWARD_WAVE.md", ", 7-day strike-wave shadow model (hidden from the page)", lambda: model.wave_events(), model.WAVE_HORIZON),
}


def _through(kind, m, series=None):
    """The last day outcomes are known for: the events file's date, or for the wave record the oldest wave feed's newest day."""
    if kind == "wave":
        ths = m.get("theatres") or list(model.WAVE_FEEDS)
        return min(dt.date.fromisoformat(model.wave_points(model.WAVE_FEEDS[t], series)[-1][0][:10]) for t in ths)
    with open(os.path.join(HERE, "data", "events_through.txt")) as f:
        return dt.date.fromisoformat(f.read().strip())


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
        L += ["", f"Compare with the validation report (`docs/{name.replace('FORWARD', 'MODEL')}`): the backtest can be tuned, this cannot."]
    L += ["", "## Forward gates", "",
          f"Brier skill against the base rate above 0, and the lower end of the AUC interval (resampling theatre-months) above 0.5, read once {FORWARD_DAYS} days have matured. "
          "The first of the three targets (any event in 30 days, armed force in 30 days, a strike wave in 7 days) to pass is the one to promote.", "",
          (f"**{'PASS' if g['pass'] else 'FAIL'}**: Brier skill {g['bss']:+.3f}, AUC interval lower end {g['auc_lo']:.3f}, on {g['days']} matured days."
           if g["ready"] else f"Not read yet: {g['days']} of {FORWARD_DAYS} matured days.")]
    with open(os.path.join(DOCS, name), "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote docs/" + name + ";", "chain intact" if ok else f"CHAIN BROKEN at row {bad}")
    return 0 if ok else 1


if __name__ == "__main__":
    rc = main()
    for k in ("armed", "wave"):
        if os.path.exists(KINDS[k][0]):
            rc = main(k) or rc
    sys.exit(rc)
