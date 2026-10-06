#!/usr/bin/env python3
"""Fetch every catalogue series, score, render. Standard library only.

    python3 tools/warwatch/run.py --out site/index.html
    python3 tools/warwatch/run.py --demo buildup --out site/index.html
    python3 tools/warwatch/run.py --only us_boots_awards,wiki_conscription

A failed or key-less series is shown as such; it never turns into a calm score.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import config as C  # noqa: E402
import dashboard  # noqa: E402
import scoring  # noqa: E402
import stats  # noqa: E402


def collect(only=None):
    out = []
    for s in catalog.SERIES:
        if only and s["id"] not in only:
            continue
        rec = {k: v for k, v in s.items() if k != "fetch"}
        rec.update(points=[], score=None, status="ok", error="")
        missing = [k for k in s["needs"] if not os.environ.get(k)]
        if missing:
            rec.update(status="awaiting_key", error="needs " + ", ".join(missing))
        else:
            try:
                pts = s["fetch"]()
                rec["points"] = pts[:-s["drop"]] if s["drop"] else pts
            except Exception as e:
                rec.update(status="error", error=str(e)[:200])
        out.append(rec)
        print(f"{rec['status']:13} {s['id']:28} n={len(rec['points'])} {rec['error'][:80]}", flush=True)
    return out


def score(series):
    for s in series:
        if s["status"] != "ok":
            continue
        s["score"] = stats.score_series(s["points"], s["kind"])
        if s["score"] is None:
            s["status"] = "collecting"
    return series


def evaluate(series):
    series = score(series)
    th = {}
    for t in C.THEATRES:
        d = scoring.theatre_view(series, t)
        th[t] = {"domains": d, **scoring.level(d)}
    return {"series": series, "theatres": th}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", choices=["calm", "buildup"])
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="site/index.html")
    a = ap.parse_args()
    if a.demo:
        import demo
        series = demo.scenario(a.demo)
    else:
        series = collect(set(filter(None, a.only.split(","))))
    res = evaluate(series)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(dashboard.render(res, now, demo=bool(a.demo)))
    summ = {"generated": now, "demo": a.demo,
            "theatres": {t: {k: v[k] for k in ("level", "firing", "scorable", "basis")} for t, v in res["theatres"].items()},
            "series": {s["id"]: {"status": s["status"], "z": (s["score"] or {}).get("z"), "error": s["error"]}
                       for s in res["series"]}}
    with open(os.path.splitext(a.out)[0] + ".json", "w") as f:
        json.dump(summ, f, indent=1)
    print("--- scores (direction-adjusted z) ---")
    for s in sorted(res["series"], key=lambda s: -(abs(s["score"]["z"]) if s["score"] else -1)):
        z = "%+.1f" % scoring.directed(s["score"]["z"], s["direction"]) if s["score"] else s["status"]
        print(f"{z:>10}  {s['theatre']:12} {s['domain']:15} {s['id']}")
    for t, v in summ["theatres"].items():
        print(t, v["level"], v["firing"], v["basis"], "scorable", v["scorable"])


if __name__ == "__main__":
    main()
