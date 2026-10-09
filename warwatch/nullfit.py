"""The calm-world distribution of a single signal's z, measured instead of assumed.

The level thresholds come from simulating a calm world (engine._dom_null). That simulation used to draw each signal from a
mildly heavy-tailed standard normal. Real signals are much heavier-tailed: on calm days the median series is at z >= 2 on
about 10% of days and at z >= 3 on about 5% (a normal gives 2.3% and 0.13%), so the composite crossed Critical on about 12%
of calm days in the replay instead of 1% (docs/INDICATORSTUDY.md). This script pools every scored series' point-in-time z,
turned to its warning direction, on calm days (no event in the theatre within 30 days either side; global series on every
day), 2019 on, and writes 1,001 quantiles to warwatch/data/null_z.json. engine._dom_null draws from them.

Run: WARWATCH_BACKFILL_FIT=1 python3 warwatch/nullfit.py   (uses validate.zhistory, so aircraft, fires, advisories,
warnings and vessel presence are included). Rerun when the catalogue or the scoring changes.
"""
import datetime as dt
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import indicatorstudy as S  # noqa: E402
import validate as V  # noqa: E402

OUT = os.path.join(V.DATA, "null_z.json")
NQ = 1001
FROM = dt.date(2019, 1, 1)


def main():
    H = V.zhistory()
    _, allev = S.events()
    scored = {s["id"] for s in catalog.SERIES if s["scored"]}
    per_series = []
    for sid, s in H.items():
        if sid not in scored:
            continue
        sgn = {"up": 1, "down": -1}.get(s["direction"], 1)    # "both" keeps its sign; the simulation takes |z| for it
        near = set()
        for e in (allev.get(s["theatre"], []) if s["theatre"] != "global" else []):
            near.update(e + dt.timedelta(k) for k in range(-30, 31))
        z = [v * sgn for d, v in s["z"].items() if d >= FROM and d not in near]
        if len(z) < 300:
            continue
        a = np.asarray(z)
        per_series.append(a)
    # every series counts equally, whatever its length: resample each to the same number of draws
    rng = np.random.default_rng(1)
    pooled = np.concatenate([rng.choice(a, 2000) for a in per_series])
    q = np.quantile(pooled, np.linspace(0, 1, NQ))
    out = {"built": dt.date.today().isoformat(), "series": len(per_series), "from": FROM.isoformat(),
           "calm": "no event in the theatre within 30 days either side (events.csv and events_added.csv); global series every day",
           "share_ge2": round(float((pooled >= 2).mean()), 4), "share_ge3": round(float((pooled >= 3).mean()), 4),
           "quantiles": [round(float(x), 4) for x in q]}
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(f"wrote {OUT}: {out['series']} series, z>=2 on {out['share_ge2']:.1%} of calm days, z>=3 on {out['share_ge3']:.1%}")


if __name__ == "__main__":
    main()
