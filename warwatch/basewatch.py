#!/usr/bin/env python3
"""Satellite base watch (docs/BASEWATCH_PLAN.md, B2): radar and optical change at the bases in data/bases.json.

Runs in imagery.yml (numpy, scipy, rasterio, Pillow); the dashboard build only reads the caches it writes:

    history/basewatch_scenes.csv      one row per Sentinel-1 scene and site part: scene, site, date, orbit, part, area, metric values
    history/basewatch_optical.csv     one row per clear Sentinel-2 scene and site: scene, site, date, clear share, objects, change, burn
    history/cache/base_<id>.csv       per site and day: z of the radar metric against the same orbit's recent scenes
    history/cache/base_state.csv      per site: state (out, in, changed, normal, nodata, optical), latest dates, note
    history/cache/bases_out_<t>.csv   per theatre and day: sites in state "out" (far fewer bright objects than usual, two passes)
    history/cache/bases_in_<t>.csv    ... in state "in"
    history/cache/base_chips.csv      per site and chip: kind, date, scene
    chips/bases/<id>_{a,b,r,rb}.jpg   latest and earlier optical and radar chips (pushed to the imagery branch)

    python3 warwatch/basewatch.py                       # new scenes since the last run (budget per run)
    python3 warwatch/basewatch.py --backfill-from 2022-01-01 --site al_udeid
    python3 warwatch/basewatch.py --dry-run

The radar metric and threshold are frozen from the feasibility test (docs/BASESPIKE.md). Until it says GO, ALERTS is
False: the job still writes scenes, chips and z values for people to look at, but no site enters "out" or "in", and the
theatre counts stay empty, so the tell and alerts cannot fire.
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.dirname(HERE)
BASES = os.path.join(HERE, "data", "bases.json")
HIST = os.environ.get("WARWATCH_HISTORY", os.path.join(HERE, "history"))
SCENES = os.path.join(HIST, "basewatch_scenes.csv")
OPTICAL = os.path.join(HIST, "basewatch_optical.csv")
CACHE = os.path.join(HIST, "cache")

# ---- frozen by the feasibility test (docs/BASESPIKE.md) ----
ALERTS = False          # NO-GO on 2026-10-15 (2 of 3 cases, 10.3% false alarms against a 10% limit): a viewer, no states or alerts
METRIC = "blobs"        # radar metric chosen by the test: groups of 3 to 150 pixels with VV >= T_DB
T_DB = -3.0             # VV threshold in dB chosen by the test
# ------------------------------------------------------------
THRESHOLDS = (-6.0, -3.0, 0.0, 3.0)
BLOB_MIN, BLOB_MAX = 3, 150
PIER_PX = 6             # piers widened by 60 m: ships lie alongside
MARGIN_KM = 0.3
Z_AT = 2.5
MIN_PREV, MAX_PREV, PREV_DAYS = 8, 20, 240
OPT_DIFF = 0.06         # reflectance difference that counts an apron pixel as an object, or a pixel as changed
SCENE_COLS = ["scene_id", "site", "date", "orbit", "part", "area_m2"] + [f"bright_m2@{t:g}" for t in THRESHOLDS] + [f"blobs@{t:g}" for t in THRESHOLDS]
OPT_COLS = ["scene_id", "site", "date", "clear", "objects", "chg_ha", "burn_ha"]


# ---------------------------------------------------------------- pure functions (tested)
def radar_metrics(db, region, thresholds=THRESHOLDS):
    """{f"bright_m2@{T}": area of region pixels with VV >= T dB, f"blobs@{T}": groups of BLOB_MIN..BLOB_MAX such pixels}."""
    import numpy as np
    from scipy import ndimage as ndi
    ok = region & np.isfinite(db)
    out = {}
    for t in thresholds:
        b = ok & (db >= t)
        out[f"bright_m2@{t:g}"] = float(b.sum()) * 100.0
        lab, k = ndi.label(b, structure=np.ones((3, 3)))
        if k:
            sizes = np.bincount(lab.ravel())[1:]
            out[f"blobs@{t:g}"] = float(((sizes >= BLOB_MIN) & (sizes <= BLOB_MAX)).sum())
        else:
            out[f"blobs@{t:g}"] = 0.0
    return out


def zscore(prev, x, counts=False):
    """Robust z of x against earlier values of the same orbit; None with fewer than MIN_PREV of them."""
    prev = list(prev)[-MAX_PREV:]
    if len(prev) < MIN_PREV:
        return None
    s = sorted(prev)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    dev = sorted(abs(v - med) for v in s)
    mad = dev[n // 2] if n % 2 else (dev[n // 2 - 1] + dev[n // 2]) / 2
    floor = max(0.05 * abs(med), 1.0 if counts else 200.0)
    return (x - med) / max(1.4826 * mad, floor)


def scene_z(rows, metric, part=None):
    """rows: dicts with date, orbit, part and the metric -> [(date, orbit, value, z)] in date order; z against the same
    part and orbit's previous scenes within PREV_DAYS."""
    out = []
    hist = {}
    for r in sorted(rows, key=lambda r: r["date"]):
        if part and r["part"] != part:
            continue
        if r.get(metric) in (None, ""):
            continue
        key = (r["part"], r["orbit"])
        x = float(r[metric])
        d = dt.date.fromisoformat(r["date"])
        prev = [v for dd, v in hist.get(key, []) if (d - dd).days <= PREV_DAYS]
        out.append((r["date"], r["orbit"], x, zscore(prev, x, counts=metric.startswith("blobs"))))
        hist.setdefault(key, []).append((d, x))
    return out


def state(zs, today, alerts=ALERTS):
    """zs: [(date, z)] scored scenes, newest last -> (state, dates used). 'out'/'in' need the last two scored scenes within
    7 days to agree beyond Z_AT; 'changed' when only the latest does; 'nodata' when nothing was scored in 10 days."""
    sc = [(d, z) for d, z in zs if z is not None]
    if not sc or (today - dt.date.fromisoformat(sc[-1][0])).days > 10:
        return "nodata", []
    d1, z1 = sc[-1]
    if len(sc) >= 2:
        d0, z0 = sc[-2]
        close = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days <= 7
        if close and z0 <= -Z_AT and z1 <= -Z_AT:
            return ("out" if alerts else "changed"), [d0, d1]
        if close and z0 >= Z_AT and z1 >= Z_AT:
            return ("in" if alerts else "changed"), [d0, d1]
    if abs(z1) >= Z_AT:
        return "changed", [d1]
    return "normal", [d1]


def theatre_counts(states, sites, day):
    """{theatre: (n out, n in)} for one day; every theatre of a watched site gets a row (zeros included)."""
    out = {}
    for s in sites:
        for t in s["theatres"]:
            o, i = out.get(t, (0, 0))
            st = states.get(s["id"], "nodata")
            out[t] = (o + (st == "out"), i + (st == "in"))
    return out


def load_bases(path=BASES):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return []


def site_bbox(rec, margin_km=MARGIN_KM):
    pts = [p for part in ("aprons", "harbour", "piers") for g in rec.get(part, []) for p in g]
    if not pts:
        pts = [p for g in rec.get("outline", []) for p in g] or [[rec["lon"], rec["lat"]]]
    lo0, lo1 = min(p[0] for p in pts), max(p[0] for p in pts)
    la0, la1 = min(p[1] for p in pts), max(p[1] for p in pts)
    dla = margin_km / 110.574
    dlo = margin_km / (111.320 * max(0.05, math.cos(math.radians((la0 + la1) / 2))))
    return (lo0 - dlo, la0 - dla, lo1 + dlo, la1 + dla)


def part_masks(rec, bbox, w, h):
    """{"apron": mask, "harbour": mask} for the parts the site has (harbour = harbour polygons + piers widened by 60 m)."""
    import imagery as I
    out = {}
    if rec.get("aprons"):
        out["apron"] = I.mask(rec["aprons"], bbox, w, h)
    if rec.get("harbour") or rec.get("piers"):
        m = I.mask(rec.get("harbour", []), bbox, w, h) if rec.get("harbour") else None
        p = I.mask(rec.get("piers", []), bbox, w, h, buffer_px=PIER_PX) if rec.get("piers") else None
        out["harbour"] = m | p if m is not None and p is not None else (m if m is not None else p)
    return {k: v for k, v in out.items() if v is not None and v.any()}


# ---------------------------------------------------------------- reading scenes
def radar_rows(rec, start, end, budget, done=frozenset(), log=print):
    """Rows for new Sentinel-1 RTC scenes over a site (oldest first, at most `budget`)."""
    import imagery as I
    import numpy as np
    bbox = site_bbox(rec)
    w, h = I.grid(bbox, 10)
    masks = part_masks(rec, bbox, w, h)
    if not masks:
        return []
    rows = []
    for it in I.stac_search("sentinel-1-rtc", bbox, start, end):
        if budget <= 0:
            break
        if (it["id"], rec["id"]) in done or not I.has(it, "vv"):
            continue
        try:
            dbv = I.db(I.read(I.href(it, "vv"), bbox, w, h, "nearest"))
        except Exception as e:
            log(rec["id"], it["id"][:40], "read failed:", repr(e)[:120])
            continue
        budget -= 1
        for part, m in masks.items():
            valid = m & np.isfinite(dbv)
            if valid.sum() < 0.5 * m.sum():
                continue
            r = {"scene_id": it["id"], "site": rec["id"], "date": I.day(it), "orbit": I.orbit(it), "part": part, "area_m2": float(valid.sum()) * 100.0}
            r.update(radar_metrics(dbv, m))
            rows.append(r)
        rows and rows[-1]["scene_id"] == it["id"] and log(rec["id"], I.day(it), I.orbit(it), {k: rows[-1][k] for k in (f"bright_m2@{T_DB:g}", f"blobs@{T_DB:g}")})
    return rows


def optical_rows(rec, start, end, budget, done=frozenset(), log=print, min_clear=0.9, latest=False):
    """Rows for new clear Sentinel-2 scenes over a site's aprons (or outline): object pixels, changed area, burn area.
    latest=True reads only the newest `budget` scenes of the window (live runs: the newest image matters most)."""
    import imagery as I
    import numpy as np
    bbox = site_bbox(rec)
    w, h = I.grid(bbox, 10)
    w2, h2 = I.grid(bbox, 20)
    geoms = rec.get("aprons") or rec.get("outline") or []
    if not geoms:
        return []
    m10, m20 = I.mask(geoms, bbox, w, h), I.mask(geoms, bbox, w2, h2)
    rows, prev = [], []
    items = I.stac_search("sentinel-2-l2a", bbox, start, end)
    if latest:
        items = items[-budget:]
    for it in items:
        if budget <= 0:
            break
        if (it["id"], rec["id"]) in done or not I.has(it, "SCL"):
            continue
        if it["properties"].get("eo:cloud_cover", 0) > 80:
            continue
        try:
            cl = I.clear_share(it, bbox, m20)
            budget -= 1
            if cl < min_clear:
                continue
            b = I.s2_bands(it, bbox, ("B02", "B04", "B08", "B11"), 10)
            b12 = I.read(I.href(it, "B12"), bbox, w, h, "bilinear") / 10000.0
        except Exception as e:
            log(rec["id"], it["id"][:40], "optical read failed:", repr(e)[:120])
            continue
        red = b["B04"]
        med = float(np.nanmedian(red[m10])) if np.isfinite(red[m10]).any() else float("nan")
        objects = float((np.abs(red - med) > OPT_DIFF)[m10].sum())
        stack = np.stack([b["B02"], b["B04"], b["B08"], b["B11"]])
        nbr = (b["B08"] - b12) / np.maximum(b["B08"] + b12, 1e-6)
        chg = burn = 0.0
        if len(prev) >= 3:
            ref = np.nanmedian(np.stack([p[0] for p in prev[-3:]]), axis=0)
            chg = float((np.nanmax(np.abs(stack - ref), axis=0) > OPT_DIFF).sum()) * 100.0 / 1e4
        if prev:
            burn = float(((prev[-1][1] - nbr) >= 0.27).sum()) * 100.0 / 1e4
        prev.append((stack, nbr))
        rows.append({"scene_id": it["id"], "site": rec["id"], "date": I.day(it), "clear": round(cl, 3), "objects": objects, "chg_ha": round(chg, 2), "burn_ha": round(burn, 2),
                     "_item": it})
        log(rec["id"], I.day(it), "clear", round(cl, 2), "objects", objects, "chg_ha", round(chg, 1))
    return rows


# ---------------------------------------------------------------- files
def read_csv(path):
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def append_csv(path, cols, rows):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.1f}" if isinstance(r.get(k), float) else r.get(k, "")) for k in cols})


def save_series(name, pts):
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, f"{name}.csv"), "w", newline="") as f:
        f.write("".join(f"{d},{float(v)!r}\r\n" for d, v in pts))


def save_rows(name, header, rows):
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, f"{name}.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- chips
def chips(rec, optical, radar_items, log=print):
    """Latest clear optical chip and one 25 to 60 days earlier; latest radar chip and one from the same orbit 25 to 60 days earlier."""
    import imagery as I
    bbox = site_bbox(rec)
    out = []
    path = lambda k: os.path.join(I.CHIPS, "bases", f"{rec['id']}_{k}.jpg")    # noqa: E731
    if optical:
        a = optical[-1]
        da = dt.date.fromisoformat(a["date"])
        older = [o for o in optical if 25 <= (da - dt.date.fromisoformat(o["date"])).days <= 60]
        for k, o in (("a", a), ("b", older[-1] if older else None)):
            if o and o.get("_item"):
                try:
                    I.chip_s2(o["_item"], bbox, path(k))
                    out.append([rec["id"], k, o["date"], o["scene_id"]])
                except Exception as e:
                    log(rec["id"], "chip failed:", repr(e)[:100])
    if radar_items:
        r = radar_items[-1]
        dr = dt.date.fromisoformat(I.day(r))
        older = [x for x in radar_items if I.orbit(x) == I.orbit(r) and 25 <= (dr - dt.date.fromisoformat(I.day(x))).days <= 60]
        w, h = I.grid(bbox, 10)
        for k, it in (("r", r), ("rb", older[-1] if older else None)):
            if it:
                try:
                    I.chip_radar(I.db(I.read(I.href(it, "vv"), bbox, w, h, "nearest")), path(k))
                    out.append([rec["id"], k, I.day(it), it["id"]])
                except Exception as e:
                    log(rec["id"], "radar chip failed:", repr(e)[:100])
    return out


# ---------------------------------------------------------------- run
def rebuild(sites, today=None):
    """Recomputes z per site, states, theatre counts and the state table from the scene files."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    rows = read_csv(SCENES)
    opt = read_csv(OPTICAL)
    metric = f"{METRIC}@{T_DB:g}"
    states, table = {}, []
    by_site = {}
    for r in rows:
        by_site.setdefault(r["site"], []).append(r)
    for s in sites:
        main = "harbour" if s["kind"] in ("naval", "port") else "apron"
        sr = by_site.get(s["id"], [])
        if not any(r["part"] == main for r in sr):
            main = "harbour" if any(r["part"] == "harbour" for r in sr) else "apron"
        zs = [(d, z) for d, _, _, z in scene_z(sr, metric, main)]
        per_day = {}
        for d, z in zs:
            if z is not None:
                per_day.setdefault(d, []).append(z)
        save_series(f"base_{s['id']}", [(d, sum(v) / len(v)) for d, v in sorted(per_day.items())])
        st, used = state(zs, today)
        so = sorted((o for o in opt if o["site"] == s["id"]), key=lambda o: o["date"])
        note = ""
        if len(so) >= 4:
            ch = [float(o["chg_ha"] or 0) for o in so]
            med = sorted(ch[:-1])[len(ch[:-1]) // 2]
            if ch[-1] >= max(2.0, 3 * med):
                note = f"New construction or earthworks seen on {so[-1]['date']} ({ch[-1]:.0f} ha changed)."
        if so and float(so[-1]["burn_ha"] or 0) >= 1:
            note = (note + " " if note else "") + f"Burn scars seen on {so[-1]['date']} ({float(so[-1]['burn_ha']):.1f} ha)."
        if not sr and so:
            st = "optical"
        states[s["id"]] = st
        last_r = max((r["date"] for r in sr), default="")
        last_o = so[-1]["date"] if so else ""
        zl = next((z for d, z in reversed(zs) if z is not None), None)
        table.append([s["id"], st, ";".join(used), last_r, last_o, "" if zl is None else f"{zl:.2f}", main, note])
    save_rows("base_state", ["site", "state", "dates", "last_radar", "last_optical", "z", "part", "note"], table)
    # theatre counts per day: replay the state day by day over the last 400 days
    if ALERTS:
        days = [today - dt.timedelta(days=k) for k in range(400, -1, -1)]
        series = {}
        site_z = {s["id"]: [(d, z) for d, _, _, z in scene_z(by_site.get(s["id"], []), metric,
                                                             "harbour" if s["kind"] in ("naval", "port") else "apron")] for s in sites}
        for d in days:
            iso = d.isoformat()
            st = {sid: state([x for x in zs if x[0] <= iso], d)[0] for sid, zs in site_z.items()}
            for t, (o, i) in theatre_counts(st, sites, d).items():
                if any(x[0] <= iso and (d - dt.date.fromisoformat(x[0])).days <= 10 for s in sites if t in s["theatres"] for x in site_z[s["id"]] if x[1] is not None):
                    series.setdefault(t, []).append((iso, o, i))
        for t, pts in series.items():
            save_series(f"bases_out_{t}", [(d, o) for d, o, _ in pts])
            save_series(f"bases_in_{t}", [(d, i) for d, _, i in pts])
    return states


def main(argv=None):
    import imagery as I
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="")
    ap.add_argument("--days", type=int, default=30, help="look back this many days for new scenes")
    ap.add_argument("--backfill-from", default="")
    ap.add_argument("--budget", type=int, default=120, help="radar scene reads per run")
    ap.add_argument("--no-optical", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    sites = [s for s in load_bases() if not a.site or s["id"] in a.site.split(",")]
    today = dt.datetime.now(dt.timezone.utc).date()
    start = a.backfill_from or (today - dt.timedelta(days=a.days)).isoformat()
    done_r = {(r["scene_id"], r["site"]) for r in read_csv(SCENES)}
    done_o = {(r["scene_id"], r["site"]) for r in read_csv(OPTICAL)}
    per = max(1, a.budget // max(1, len(sites)))
    chip_rows = {(r[0], r[1]): r for r in _chip_rows()}
    for s in sites:
        try:
            rr = radar_rows(s, start, today.isoformat(), per, done_r)
        except Exception as e:
            print(s["id"], "radar search failed:", repr(e)[:160], flush=True)
            rr = []
        oo = []
        if not a.no_optical:
            try:
                # optical needs the previous clear scenes for its change measure: read 90 days, keep only new rows
                oo = optical_rows(s, (today - dt.timedelta(days=90)).isoformat() if not a.backfill_from else start, today.isoformat(), max(8, per // 2),
                                  latest=not a.backfill_from)
            except Exception as e:
                print(s["id"], "optical search failed:", repr(e)[:160], flush=True)
        if a.dry_run:
            continue
        append_csv(SCENES, SCENE_COLS, rr)
        append_csv(OPTICAL, OPT_COLS, [o for o in oo if (o["scene_id"], s["id"]) not in done_o])
        if not a.backfill_from:
            try:
                ri = [it for it in I.stac_search("sentinel-1-rtc", site_bbox(s), (today - dt.timedelta(days=70)).isoformat(), today.isoformat()) if I.has(it, "vv")]
                for r in chips(s, oo, ri):
                    chip_rows[(r[0], r[1])] = r
            except Exception as e:
                print(s["id"], "chips failed:", repr(e)[:160], flush=True)
    if not a.dry_run:
        save_rows("base_chips", ["site", "kind", "date", "scene_id"], sorted(chip_rows.values()))
        st = rebuild(load_bases(), today)
        print("states:", st, flush=True)


def _chip_rows():
    p = os.path.join(CACHE, "base_chips.csv")
    try:
        with open(p, newline="") as f:
            return [r for r in csv.reader(f) if r and r[0] != "site"]
    except OSError:
        return []


# ---------------------------------------------------------------- for the dashboard build (standard library only)
STATE_WHY = {
    "out": "Radar shows far fewer bright objects {where} than usual on two passes ({dates}). {what} may have left.",
    "in": "Radar shows far more bright objects {where} than usual on two passes ({dates}). {what} may have arrived.",
    "changed": "One radar pass ({dates}) differed from usual {where}; waiting for the next pass to confirm.",
    "normal": "In its usual range on the latest radar pass ({dates}).",
    "nodata": "No usable radar pass in the last 10 days.",
    "optical": "No radar coverage here: optical images only.",
}


def layer(path=BASES):
    """Map items for the base layer: site facts, state, a plain sentence, the last 30 radar z values and chip paths."""
    sites = load_bases(path)
    if not sites:
        return []
    st = {r["site"]: r for r in read_csv(os.path.join(CACHE, "base_state.csv"))}
    chips_ = {}
    for r in _chip_rows():
        if len(r) >= 3:
            chips_.setdefault(r[0], {})[r[1]] = r[2]
    out = []
    for s in sites:
        r = st.get(s["id"], {})
        state_ = r.get("state") or "nodata"
        part = r.get("part") or ("harbour" if s["kind"] in ("naval", "port") else "apron")
        where = "in the harbour" if part == "harbour" else "on the aprons"
        what = "Ships" if part == "harbour" else "Aircraft"
        dates = " and ".join(x for x in (r.get("dates") or "").split(";") if x) or r.get("last_radar", "")
        pts = []
        try:
            with open(os.path.join(CACHE, f"base_{s['id']}.csv"), newline="") as f:
                pts = [round(float(x[1]), 2) for x in csv.reader(f) if len(x) == 2][-30:]
        except OSError:
            pass
        c = chips_.get(s["id"], {})
        img = {}
        for k in ("a", "b", "r", "rb"):
            if k in c:
                img[k] = f"img/bases/{s['id']}_{k}.jpg"
                img[k + "d"] = c[k]
        if not ALERTS and state_ in ("out", "in", "changed", "normal"):
            zt = f"{float(r['z']):+.1f}" if r.get("z") else "n/a"
            state_ = "viewer"
            why_ = (f"Latest radar pass {r.get('last_radar') or 'n/a'}: z {zt} against this orbit's usual count of bright objects {where}. "
                    "Shown for looking only: the automated check did not pass its test (docs/BASESPIKE.md).")
        else:
            why_ = STATE_WHY.get(state_, "").format(where=where, what=what, dates=dates)
        out.append({"id": s["id"], "n": s["name"], "lat": s["lat"], "lon": s["lon"], "k": s["kind"], "side": s["side"], "ths": s["theatres"],
                    "st": state_, "z": float(r["z"]) if r.get("z") else None, "last": r.get("last_radar", ""), "lo": r.get("last_optical", ""),
                    "pts": pts, "why": why_, "note": r.get("note", ""),
                    "wy": s.get("why", ""), "img": img})
    return out


if __name__ == "__main__":
    main()
