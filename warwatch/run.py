#!/usr/bin/env python3
"""Fetch every catalogue series, score, render. Standard library only.

    python3 tools/warwatch/run.py --out site/index.html
    python3 tools/warwatch/run.py --demo buildup --out site/index.html
    python3 tools/warwatch/run.py --only us_boots_awards,brent

A failed or key-less series is shown as such; it never turns into a calm score.
"""
import argparse
import csv
import datetime as dt
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import config as C  # noqa: E402
import dashboard  # noqa: E402
import engine  # noqa: E402
import extras  # noqa: E402
import geo  # noqa: E402
import model  # noqa: E402
import scoring  # noqa: E402
import stats  # noqa: E402
import store  # noqa: E402


def _fetch(s, rec):
    every = s.get("every")
    if every and not os.environ.get("WARWATCH_FORCE"):
        age = store.cache_age_hours(s["id"])
        old = store.cache_load(s["id"]) if age is not None and age < every else []
        if old:   # fetched recently enough: the source does not change faster than this
            rec["points"] = old[:-s["drop"]] if s["drop"] else old
            return
    pts = s["fetch"]()
    if not pts:
        raise RuntimeError("source returned no data")
    store.cache_save(s["id"], pts, stamp=bool(s.get("every")))
    rec["points"] = pts[:-s["drop"]] if s["drop"] else pts


def collect(only=None):
    """Fetch every series. A failed fetch is retried once at the end of the
    run (rate limits clear), then falls back to the last good copy, shown as
    stale. No copy and no data means the series is an error, never a guess."""
    out, failed = [], []
    for s in catalog.SERIES:
        if only and s["id"] not in only:
            continue
        rec = {k: v for k, v in s.items() if k != "fetch"}
        rec.update(points=[], score=None, status="ok", error="", stale="")
        missing = [k for k in s["needs"] if not os.environ.get(k)]
        if missing:
            rec.update(status="awaiting_key", error="needs " + ", ".join(missing))
        else:
            try:
                _fetch(s, rec)
            except Exception as e:
                rec.update(status="error", error=str(e)[:200])
                failed.append((s, rec))
        out.append(rec)
        print(f"{rec['status']:13} {s['id']:28} n={len(rec['points'])} {rec['error'][:80]}", flush=True)
    retry = [(s, r) for s, r in failed if "refresh pending" not in r["error"]]
    if retry and not os.environ.get("WARWATCH_NO_RETRY"):
        time.sleep(60)
        for s, rec in retry:
            try:
                _fetch(s, rec)
                rec.update(status="ok", error="")
                print(f"retry ok      {s['id']:28} n={len(rec['points'])}", flush=True)
            except Exception as e:
                rec["error"] = str(e)[:200]
                time.sleep(20)
    for s, rec in failed:
        if rec["status"] == "error":
            old = store.cache_load(s["id"])
            if old:
                rec.update(status="ok", stale=old[-1][0],
                           points=old[:-s["drop"]] if s["drop"] else old)
                print(f"stale         {s['id']:28} n={len(rec['points'])} last good {old[-1][0]}", flush=True)
    return out


def score(series):
    for s in series:
        if s["status"] != "ok":
            continue
        s["score"] = stats.score_series(s["points"], s["kind"], transform=s.get("transform"), scale=s.get("scale"))
        if s["score"] is None:
            s["status"] = "collecting"
    return series


def evaluate(series):
    series = score(series)
    res = engine.evaluate(series)
    res["series"] = series
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", choices=["calm", "buildup"])
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="site/index.html")
    ap.add_argument("--fetch-only", action="store_true", help="fetch and cache, do not render")
    a = ap.parse_args()
    if a.demo:
        import demo
        series = demo.scenario(a.demo)
    else:
        series = collect(set(filter(None, a.only.split(","))))
        if a.fetch_only:
            return
    res = evaluate(series)
    ex = None if a.demo else extras.collect()
    if not a.demo:
        try:   # the probability model must never break the build; without it the page keeps the composite levels
            res = model.apply(res, markets=(ex or {}).get("markets"))
            print("forward record: appended", model.forward_append(res), "rows")
            try:   # hidden armed-force model, own record, never shown
                print("armed-force shadow record: appended", model.shadow(res), "rows")
            except Exception as e:
                print("shadow model skipped:", str(e)[:200])
        except Exception as e:
            print("model skipped:", str(e)[:200])
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    static = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")   # tab icons and the link-preview image, served next to the page
    for fn in os.listdir(static) if os.path.isdir(static) else []:
        shutil.copyfile(os.path.join(static, fn), os.path.join(os.path.dirname(os.path.abspath(a.out)), fn))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(dashboard.render(res, now, demo=bool(a.demo), extras=ex, topo=geo.load()))
    summ = {"generated": now, "demo": a.demo, "weights_version": res["weights_version"], "global": res["global"],
            "theatres": {t: {k: v[k] for k in ("level", "score", "zc", "index", "imbalance", "worst", "confidence", "conf_label", "firing", "scorable", "basis")}
                         for t, v in res["theatres"].items()},
            "series": {s["id"]: {"status": s["status"], "z": (s["score"] or {}).get("z"), "error": s["error"]}
                       for s in res["series"]}}
    if res.get("model"):
        mo = res["model"]
        summ["model"] = {"version": mo["version"], "active": mo["active"], "gates_pass": mo["gates"]["pass"], "any_theatre": round(mo["global"]["p_any"], 4),
                         "market_moving": round(mo["global"]["p_market_moving"], 4),
                         "theatres": {t: {"p": round(v["p"], 4), "lo": round(v["lo"], 4), "hi": round(v["hi"], 4), "level": v["level"], "why": v["contrib"],
                                          "history": v["history"], "aftermath": v["aftermath"]} for t, v in mo["theatres"].items()}}
    with open(os.path.splitext(a.out)[0] + ".json", "w") as f:
        json.dump(summ, f, indent=1)
    with open(os.path.join(os.path.dirname(os.path.abspath(a.out)), "audit.json"), "w") as f:
        json.dump({"generated": now, "weights_version": res["weights_version"], "theatres": res["audit"],
                   "series": {s["id"]: {k: (s["score"] or {}).get(k) for k in ("z", "z_raw", "value", "label", "miss", "filled", "base_med", "base_sd", "base_n", "method")}
                              for s in res["series"] if s["score"]}}, f, separators=(",", ":"))
    print("--- scores (direction-adjusted z) ---")
    for s in sorted(res["series"], key=lambda s: -(abs(s["score"]["z"]) if s["score"] else -1)):
        z = "%+.1f" % scoring.directed(s["score"]["z"], s["direction"]) if s["score"] else s["status"]
        print(f"{z:>10}  {s['theatre']:12} {s['domain']:15} {s['id']}")
    for t, v in summ["theatres"].items():
        print(t, v["level"], v["score"], v["firing"], v["basis"], "scorable", v["scorable"], "conf", v["conf_label"])
    print("global", res["global"])


if __name__ == "__main__":
    main()
