#!/usr/bin/env python3
"""Sentinel-2 check of unusual fires (docs/FIRECLASS_PLAN.md, F5). Runs in imagery.yml; needs numpy, rasterio, Pillow.

Reads history/cache/fire_anoms.csv (written by the dashboard build), and for each recent cluster with score >= 60 finds a
clear Sentinel-2 image before and after the fire. It measures the burnt area (dNBR >= 0.27 over the central 1 km), reads
the land cover (ESA WorldCover) and cuts three chips: before, after, after in short-wave infrared. Results go to
history/cache/fire_review.csv; firecls.review() uses them on the next build.

Verdicts: scar (>= 1 ha burnt), none (< 0.2 ha), unclear (in between), wait (no clear image after the fire yet),
cloud (still none after 21 days). A burn scar shows that something burned, not what caused it.

    python3 warwatch/firereview.py [--max 25] [--dry-run]
"""
import argparse
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import firecls as F  # noqa: E402
import store  # noqa: E402

REVIEW = "fire_review"
HEAD = ["cid", "verdict", "burn_ha", "landcover", "before_date", "after_date", "before_id", "after_id", "checked_at"]
FINAL = ("scar", "none", "unclear", "cloud")
HALF_KM = 1.28          # chips cover 2.56 km
CORE_KM = 0.5           # burn measured over the central 1 km
MIN_CLEAR = 0.8


def log(*a):
    print(*a, flush=True)


def verdict(burn_ha):
    return "scar" if burn_ha >= 1.0 else "none" if burn_ha < 0.2 else "unclear"


def burn_area(pre, post):
    """Hectares with dNBR >= 0.27 (moderate burn severity) from two {B08, B12} reflectance dicts on one 20 m grid."""
    import numpy as np
    nbr = lambda b: (b["B08"] - b["B12"]) / np.maximum(b["B08"] + b["B12"], 1e-6)    # noqa: E731
    d = nbr(pre) - nbr(post)
    return float(np.nansum(d >= 0.27)) * 0.04


def review_one(row, today, log=log, write_chips=True):
    import imagery as I
    cid, lat, lon, first = row[0], float(row[2]), float(row[3]), row[4][:10]
    t0 = dt.date.fromisoformat(first)
    box = I.box_around(lat, lon, HALF_KM)
    core = I.box_around(lat, lon, CORE_KM)
    items = [it for it in I.stac_search("sentinel-2-l2a", box, (t0 - dt.timedelta(days=60)).isoformat(), today.isoformat()) if I.has(it, "SCL")]
    before = after = None
    for it in reversed([i for i in items if I.day(i) < first]):
        if I.clear_share(it, core) >= MIN_CLEAR:
            before = it
            break
    for it in [i for i in items if I.day(i) > first]:
        if I.clear_share(it, core) >= MIN_CLEAR:
            after = it
            break
    lc = I.worldcover_class(lat, lon)
    if not after:
        v = "cloud" if (today - t0).days > 21 else "wait"
        return [cid, v, "", lc, I.day(before) if before else "", "", before["id"] if before else "", "", today.isoformat()]
    ha = 0.0
    if before:
        w, h = I.grid(core, 20)
        pre = {b: I.read(I.href(before, b), core, w, h) / 10000.0 for b in ("B08", "B12")}
        post = {b: I.read(I.href(after, b), core, w, h) / 10000.0 for b in ("B08", "B12")}
        ha = burn_area(pre, post)
    v = verdict(ha) if before else "unclear"
    if write_chips:
        base = os.path.join(I.CHIPS, "fires", cid)
        try:
            if before:
                I.chip_s2(before, box, base + "_b.jpg")
            I.chip_s2(after, box, base + "_a.jpg")
            I.chip_s2(after, box, base + "_s.jpg", kind="swir")
        except Exception as e:
            log(cid, "chips failed:", repr(e)[:120])
    log(cid, v, f"{ha:.1f} ha", lc, I.day(before) if before else "-", I.day(after))
    return [cid, v, f"{ha:.2f}", lc, I.day(before) if before else "", I.day(after), before["id"] if before else "", after["id"], today.isoformat()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    today = dt.datetime.now(dt.timezone.utc).date()
    cut = (today - dt.timedelta(days=F.KEEP_DAYS)).isoformat()
    old = {r[0]: r for r in store.cache_rows(REVIEW) if len(r) == len(HEAD) and r[0] != "cid" and r[8] >= cut}
    todo = [r for r in store.cache_rows(F.ANOMS) if len(r) == 9 and r[0] != "cid" and r[4][:10] >= cut and int(r[7]) >= F.ANOM_AT
            and (r[0] not in old or old[r[0]][1] not in FINAL)]
    todo.sort(key=lambda r: (-int(r[7]), r[4]))
    for r in todo[:a.max]:
        try:
            out = review_one(r, today, write_chips=not a.dry_run)
        except Exception as e:
            log(r[0], "failed:", repr(e)[:160])
            continue
        old[r[0]] = out
    if not a.dry_run:
        store.cache_rows_save(REVIEW, [HEAD] + sorted(old.values()))
    log("reviewed", min(len(todo), a.max), "of", len(todo), "waiting clusters")


if __name__ == "__main__":
    main()
