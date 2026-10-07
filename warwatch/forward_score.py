#!/usr/bin/env python3
"""Scores the forward record (forward/log.csv): every probability the live build logged, checked against what happened. Standard library only.

    python3 warwatch/forward_score.py     # verify the hash chain, score matured forecasts, write docs/FORWARD.md

A forecast matures 30 days after it was made, once the events file is complete through that day (warwatch/data/events_through.txt: whoever adds
events moves it). Days within 30 days after an event are left out, as in validation. Run quarterly by .github/workflows/forward-score.yml.
"""
import datetime as dt
import math
import os
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


def score(rows, events, through, bands):
    """-> dict of results over matured theatre forecasts."""
    by = {}
    for t, d in events:
        by.setdefault(t, []).append(d)
    out, anyrows = [], {}
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        if d + dt.timedelta(days=model.AFTERMATH) > through:
            continue
        if r["theatre"] == "_any":
            hit = any(0 < (e - d).days <= 30 for ds in by.values() for e in ds)
            anyrows[r["date"]] = (float(r["p"]), hit)
            continue
        ds = by.get(r["theatre"], [])
        if any(0 <= (d - e).days <= model.AFTERMATH for e in ds):
            continue
        out.append((float(r["p"]), float(r["base"]), any(0 < (e - d).days <= 30 for e in ds), r))
    return out, anyrows


def main():
    ok, bad, rows = model.forward_verify()
    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(HERE, "data", "events_through.txt")) as f:
        through = dt.date.fromisoformat(f.read().strip())
    m = model.load() or {"bands": [0.05, 0.10, 0.25]}
    bands = m["bands"]
    L = ["# Forward record", "",
         "Every day the live build appends its probabilities for all theatres to `forward/log.csv` before any outcome is known. Each row carries the hash of the row before it, so a "
         "later edit anywhere breaks the chain from that row on; `python3 warwatch/forward_score.py` checks it. This report scores the forecasts that have matured: made at least 30 days before "
         f"`warwatch/data/events_through.txt` ({through}), outside the 30 days after an event.", "",
         f"Chain: **{'intact' if ok else f'BROKEN at row {bad}'}**, {len(rows):,} rows" + (f", {rows[0]['date']} to {rows[-1]['date']}." if rows else "."), ""]
    scored, anyrows = score(rows, model.load_events(), through, bands) if ok else ([], {})
    if len(scored) < 100:
        L += [f"Matured forecasts so far: {len(scored)}. Too few to score; the first report with numbers needs about a quarter of daily forecasts.", ""]
    else:
        n = len(scored)
        pos = sum(y for _, _, y, _ in scored)
        bs = sum((p - y) ** 2 for p, _, y, _ in scored) / n
        bb = sum((b - y) ** 2 for _, b, y, _ in scored) / n
        a = auc([(p, y) for p, _, y, _ in scored])
        L += [f"Matured forecasts: {n:,} theatre-days, {pos:,} followed by an event within 30 days ({pos / n:.1%}).", "",
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
            L += ["", f"Chance of an event in any theatre within 30 days: mean forecast {mp:.0%}, followed by an event {fr:.0%} of days (an upper bound is expected, as theatres move together)."]
        L += ["", "Compare with the validation report (`docs/MODEL.md`): the backtest can be tuned, this cannot."]
    with open(os.path.join(DOCS, "FORWARD.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote docs/FORWARD.md;", "chain intact" if ok else f"CHAIN BROKEN at row {bad}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
