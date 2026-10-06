"""Synthetic series for tests and the labelled demo page. Not data."""
import datetime as dt
import math
import random

import catalog


def monthly(seed, spike, years=5, end=(2026, 8)):
    rnd = random.Random(seed)
    out, y, m = [], end[0] - years, end[1]
    for _ in range(years * 12):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        out.append((f"{y:04d}-{m:02d}", 100 * (1 + 0.5 * (m == 9)) * rnd.lognormvariate(0, 0.12)))
    lab, v = out[-1]
    out[-1] = (lab, v * (1 + spike))
    return out


def daily(seed, spike, days=300):
    rnd = random.Random(seed)
    end = dt.date(2026, 10, 5)
    out = []
    for i in range(days):
        d = end - dt.timedelta(days=days - 1 - i)
        v = 1000 * (1 + 0.1 * math.sin(i / 7 * 2 * math.pi)) * rnd.lognormvariate(0, 0.08)
        if i >= days - 7:
            v *= 1 + spike
        out.append((d.isoformat(), v))
    return out


HOT = {"kit", "medical", "attention"}


def scenario(name):
    out = []
    for i, s in enumerate(catalog.SERIES):
        hot = name == "buildup" and s["domain"] in HOT and s["theatre"] in ("global", "ukraine")
        spike = 1.0 if hot else 0.0
        if s["direction"] == "down" and hot:
            spike = -0.6
        pts = monthly(i, spike) if s["kind"] == "monthly" else daily(i, spike)
        rec = {k: v for k, v in s.items() if k != "fetch"}
        rec.update(points=pts, score=None, status="ok", error="")
        out.append(rec)
    return out
