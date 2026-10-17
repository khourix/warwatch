#!/usr/bin/env python3
"""Satellite base watch (docs/BASEWATCH_PLAN.md, B2): radar and optical change at the bases in data/bases.json.

Runs in imagery.yml (numpy, scipy, rasterio, Pillow); the dashboard build only reads the caches it writes:

    history/basewatch_scenes.csv      one row per Sentinel-1 scene and site part: scene, site, date, orbit, part, area, metric values
    history/basewatch_optical.csv     one row per Sentinel-2 scene checked and site: scene, site, date, clear share, objects, change, burn
                                      (under 90% clear: the clear share only; change and burn blank without a clear scene in 30 days)
    history/cache/base_<id>.csv       per site and day: z of the radar metric against the same orbit's recent scenes
    history/cache/base_state.csv      per site: state (out, in, changed, normal, nodata, optical), latest dates, note
    history/cache/bases_out_<t>.csv   per theatre and day: sites in state "out" (far fewer bright objects than usual, two passes)
    history/cache/bases_in_<t>.csv    ... in state "in"
    history/cache/base_chips.csv      per site and chip: kind, date, scene
    chips/bases/<id>_{a,b,r,rb}.jpg   latest and earlier optical and radar chips (pushed to the imagery branch)

    python3 warwatch/basewatch.py                       # new scenes since the last run (budget per run)
    python3 warwatch/basewatch.py --backfill-from 2022-01-01 --site al_udeid
    python3 warwatch/basewatch.py --dry-run

The radar metric and threshold are frozen from the feasibility test (docs/BASESPIKE.md). Since 2026-10-17 the map shows
movement: a site whose last two radar passes within a week both read far fewer (or far more) bright objects than usual is
"out" (or "in"), with a note that the check has not passed its test. ALERTS still gates the theatre counts
(bases_out_<t>, bases_in_<t>), so the tell and the model only see them once the backfill test passes
(docs/BASEWATCH_STUDY_PLAN.md, run by basestudy.py).
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.dirname(HERE)
BASES = os.path.join(HERE, "data", "bases.json")
HIST = os.environ.get("WARWATCH_HISTORY", os.path.join(HERE, "history"))
SCENES = os.path.join(HIST, "basewatch_scenes.csv")
OPTICAL = os.path.join(HIST, "basewatch_optical.csv")
CACHE = os.path.join(HIST, "cache")

# ---- frozen by the feasibility test (docs/BASESPIKE.md) ----
ALERTS = True           # backfill test PASSED on 2026-10-17 (docs/BASEWATCH_STUDY.md; p 0.043, calm firing 11%). The feasibility
                        # test of 2026-10-15 was NO-GO by 0.3 points on single scenes; the two-pass rule is what passed
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
WATER_NIR = 0.05        # near-infrared reflectance below this is water: left out of the change and burn measures
REF_DAYS = 30           # optical change and burns compare with clear scenes of the last 30 days only
VIS = [0, 1]            # blue and red in the optical stack (B02, B04, B08, B11): the bands the change measure reads
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


def state(zs, today, alerts=True):
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


def _bbox(pts, margin_km=MARGIN_KM):
    lo0, lo1 = min(p[0] for p in pts), max(p[0] for p in pts)
    la0, la1 = min(p[1] for p in pts), max(p[1] for p in pts)
    dla = margin_km / 110.574
    dlo = margin_km / (111.320 * max(0.05, math.cos(math.radians((la0 + la1) / 2))))
    return (lo0 - dlo, la0 - dla, lo1 + dlo, la1 + dla)


def site_bbox(rec, margin_km=MARGIN_KM, part=None):
    """Window around a part ("apron": aprons, else the outline; "harbour": piers and harbour polygons). With no part: the
    aprons or outline, else the harbour; naval sites the other way round (the view used for optical change and chips)."""
    apron = [p for g in rec.get("aprons", []) for p in g] or [p for g in rec.get("outline", []) for p in g]
    harbour = [p for k in ("harbour", "piers") for g in rec.get(k, []) for p in g]
    naval = rec.get("kind") in ("naval", "port")      # a naval site's view is its harbour, not the (often small) base compound
    ground = [p for g in rec.get("outline", []) for p in g]
    pts = {"apron": apron, "harbour": harbour, "ground": ground}.get(part) if part else ((harbour or apron) if naval else (apron or harbour))
    return _bbox(pts or [[rec["lon"], rec["lat"]]], margin_km)


GROUND_MAX_KM = 15      # the "ground" part (vehicles and equipment) is read only on outlines up to 15 x 15 km


def windows(rec, only=None):
    """[(bbox, [parts])]: one window for the parts that lie together, one each when they are far apart (a naval harbour
    18 km from its air base). Parts: apron (aircraft), harbour (ships), ground (the rest of the base: vehicles, launchers,
    equipment yards). `only` limits the parts read."""
    parts = [k for k, have in (("apron", rec.get("aprons")), ("harbour", rec.get("harbour") or rec.get("piers")), ("ground", _ground_ok(rec))) if have]
    parts = [k for k in parts if not only or k in only]
    if not parts:
        return []
    boxes = {k: site_bbox(rec, part=k) for k in parts}
    u = (min(b[0] for b in boxes.values()), min(b[1] for b in boxes.values()), max(b[2] for b in boxes.values()), max(b[3] for b in boxes.values()))
    wide_km = (u[2] - u[0]) * 111.32 * math.cos(math.radians((u[1] + u[3]) / 2))
    high_km = (u[3] - u[1]) * 110.574
    if len(parts) == 1 or (wide_km <= 12 and high_km <= 12):
        return [(u, parts)]
    return [(boxes[k], [k]) for k in parts]


def _ground_ok(rec):
    if not rec.get("outline"):
        return False
    lo0, la0, lo1, la1 = site_bbox(rec, part="ground", margin_km=0)
    return (lo1 - lo0) * 111.32 * math.cos(math.radians((la0 + la1) / 2)) <= GROUND_MAX_KM and (la1 - la0) * 110.574 <= GROUND_MAX_KM


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
    if _ground_ok(rec):
        g = I.mask(rec["outline"], bbox, w, h)
        if g is not None:
            for k in ("apron", "harbour"):
                if out.get(k) is not None:
                    g = g & ~out[k]
            out["ground"] = g
    return {k: v for k, v in out.items() if v is not None and v.any()}


# ---------------------------------------------------------------- reading scenes
def search_chunks(collection, bbox, start, end, days=60):
    """STAC items over a long range, searched 60 days at a time (one search returns at most 250 items), oldest first."""
    import imagery as I
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    seen = set()
    while d0 <= d1:
        e = min(d1, d0 + dt.timedelta(days=days - 1))
        for it in I.stac_search(collection, bbox, d0.isoformat(), e.isoformat()):
            if it["id"] not in seen:
                seen.add(it["id"])
                yield it
        d0 = e + dt.timedelta(days=1)


def radar_rows(rec, start, end, budget, done=frozenset(), log=print, parts=None):
    """Rows for new Sentinel-1 RTC scenes over a site (oldest first, at most `budget` scenes); each part is measured in its
    own window when the parts lie far apart."""
    import imagery as I
    import numpy as np
    wins = []
    for bbox, ps in windows(rec, parts):
        w, h = I.grid(bbox, 10)
        masks = {k: v for k, v in part_masks(rec, bbox, w, h).items() if k in ps}
        if masks:
            wins.append((bbox, w, h, masks))
    if not wins:
        return []
    union = (min(b[0][0] for b in wins), min(b[0][1] for b in wins), max(b[0][2] for b in wins), max(b[0][3] for b in wins))
    rows = []
    for it in search_chunks("sentinel-1-rtc", union, start, end):
        if budget <= 0:
            break
        if (it["id"], rec["id"]) in done or not I.has(it, "vv"):
            continue
        budget -= 1
        n0 = len(rows)
        for bbox, w, h, masks in wins:
            try:
                dbv = I.db(I.read(I.href(it, "vv"), bbox, w, h, "nearest"))
            except Exception as e:
                log(rec["id"], it["id"][:40], "read failed:", repr(e)[:120])
                continue
            for part, m in masks.items():
                valid = m & np.isfinite(dbv)
                if valid.sum() < 0.5 * m.sum():
                    continue
                r = {"scene_id": it["id"], "site": rec["id"], "date": I.day(it), "orbit": I.orbit(it), "part": part, "area_m2": float(valid.sum()) * 100.0}
                r.update(radar_metrics(dbv, m))
                rows.append(r)
        if len(rows) > n0:
            log(rec["id"], I.day(it), I.orbit(it), {f"{r['part']}": r[f"{METRIC}@{T_DB:g}"] for r in rows[n0:]})
    return rows


def optical_rows(rec, start, end, budget, done=frozenset(), log=print, min_clear=0.9, latest=False, seen=None):
    """Rows for new clear Sentinel-2 scenes over a site's aprons (or outline): object pixels, changed area, burn area.
    latest=True reads only the newest `budget` scenes of the window (live runs: the newest image matters most). With `seen`
    (scene ids already read for this site) it returns None when the newest usable scene is among them."""
    import imagery as I
    import numpy as np
    bbox = site_bbox(rec)
    w, h = I.grid(bbox, 10)
    w2, h2 = I.grid(bbox, 20)
    geoms = rec.get("aprons") or rec.get("outline") or []
    if not geoms:
        return []
    m10, m20 = I.mask(geoms, bbox, w, h), I.mask(geoms, bbox, w2, h2)
    base = I.mask(rec.get("outline") or geoms, bbox, w, h)      # change and burns are measured on the base itself
    rows, prev = [], []
    items = I.stac_search("sentinel-2-l2a", bbox, start, end)
    if seen is not None:
        # live runs: nothing to do when the newest usable scene was already read (most sites, most runs)
        usable = [it for it in items if I.has(it, "SCL") and it["properties"].get("eo:cloud_cover", 0) <= 80]
        if not usable or usable[-1]["id"] in seen:
            return None
    if latest and items:
        # the newest scenes, plus the least cloudy few from 25 to 60 days before the newest: the "before" chip comes from them
        new = items[-budget:]
        d1 = dt.date.fromisoformat(I.day(new[-1]))
        old = sorted((it for it in items[:-budget] if 25 <= (d1 - dt.date.fromisoformat(I.day(it))).days <= 60),
                     key=lambda it: it["properties"].get("eo:cloud_cover", 100))[:3]
        items = sorted(old, key=I.day) + new
        budget += len(old)
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
                # kept as checked (clear share only), so live runs do not read it again
                rows.append({"scene_id": it["id"], "site": rec["id"], "date": I.day(it), "clear": round(cl, 3)})
                continue
            b = I.s2_bands(it, bbox, ("B02", "B04", "B08", "B11"), 10)
            b12 = I.read(I.href(it, "B12"), bbox, w, h, "bilinear") / 10000.0
        except Exception as e:
            log(rec["id"], it["id"][:40], "optical read failed:", repr(e)[:120])
            continue
        red = b["B04"]
        med = float(np.nanmedian(red[m10])) if np.isfinite(red[m10]).any() else float("nan")
        objects = float((np.abs(red - med) > OPT_DIFF)[m10].sum())
        # cloud, shadow and haze pixels (scene classification) are blanked, so they never count as change or burn
        ok = np.isin(np.nan_to_num(I.read(I.href(it, "SCL"), bbox, w, h, "nearest"), nan=0), I.CLEAR_SCL)
        stack = np.where(ok, np.stack([b["B02"], b["B04"], b["B08"], b["B11"]]), np.nan)
        nbr = np.where(ok, (b["B08"] - b12) / np.maximum(b["B08"] + b12, 1e-6), np.nan)
        base_clear = float(ok[base].mean()) if base.any() else 0.0
        # against clear scenes of the last REF_DAYS only (a scene weeks older differs by season), on the base's land only
        # (sun glint on water reads as change), and blank when there is no such reference
        d = dt.date.fromisoformat(I.day(it))
        recent = [x for x in prev if 0 < (d - x[2]).days <= REF_DAYS]
        chg = burn = None
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)      # all-blank pixels: nanmedian / nanmax of nothing
            if len(recent) >= 3 and base_clear >= min_clear:
                ref = np.nanmedian(np.stack([x[0] for x in recent[-3:]]), axis=0)
                # take out each band's overall shift on the base first: haze, sun angle and the satellites' calibration move a
                # whole scene, and a bright desert base would otherwise "change" everywhere at once
                # visible bands only (blue, red): bare ground and concrete show there, while near and short-wave infrared follow
                # grass and crops through the season
                off = np.array([np.nanmedian((stack[k] - ref[k])[base]) for k in VIS])
                # brighter only: new concrete and earthworks brighten the ground, while cloud shadows the scene mask misses darken it
                diff = stack[VIS] - ref[VIS] - np.nan_to_num(off)[:, None, None]
                chg = round(float(((np.nanmax(diff, axis=0) > OPT_DIFF) & base & (ref[2] > WATER_NIR)).sum()) * 100.0 / 1e4, 2)
            if recent and base_clear >= min_clear:
                # a burn scar is dark char: the burn ratio drops and red does not brighten (a harvested field's bare soil does)
                dark = stack[1] <= recent[-1][0][1] + 0.01
                burn = round(float((((recent[-1][1] - nbr) >= 0.27) & dark & base & (recent[-1][0][2] > WATER_NIR)).sum()) * 100.0 / 1e4, 2)
        prev.append((stack, nbr, d))
        rows.append({"scene_id": it["id"], "site": rec["id"], "date": I.day(it), "clear": round(cl, 3), "objects": objects, "chg_ha": chg, "burn_ha": burn,
                     "_item": it})
        log(rec["id"], I.day(it), "clear", round(cl, 2), "objects", objects, "chg_ha", chg)
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
    optical = [o for o in optical if o.get("_item")]       # clear scenes only (cloudy ones are kept as checked, without an image)
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
    import basestudy as S
    rows = S.load_scenes(live=SCENES)      # backfilled scenes plus the live ones, so each part's usual range starts full
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
        # every part on its own: aircraft on the aprons, ships in the harbour, vehicles and equipment on the rest of the base
        parts = []
        for part in PARTS:
            if part == main or not any(r["part"] == part for r in sr):
                pz, pst, pu = zs, st, used
            else:
                pz = [(d, z) for d, _, _, z in scene_z(sr, metric, part)]
                pst, pu = state(pz, today)
            if any(r["part"] == part for r in sr):
                pl = next((z for d, z in reversed(pz) if z is not None), None)
                parts.append(f"{part}:{pst}:{'' if pl is None else f'{pl:.2f}'}:{'/'.join(pu)}")
        so = sorted((o for o in opt if o["site"] == s["id"] and float(o.get("clear") or 0) >= 0.9), key=lambda o: o["date"])
        note = ""
        # one value per day (two tiles or satellites can image the same day), only measured ones
        byday = {}
        for o in so:
            if o.get("chg_ha") not in (None, "", "None"):
                byday[o["date"]] = max(byday.get(o["date"], 0.0), float(o["chg_ha"]))
        ch = sorted(byday.items())
        if len(ch) >= 5:
            # two clear images on different days must both show the change: one image with haze or shadow often does
            base_ = sorted(v for _, v in ch[:-2])
            med = base_[len(base_) // 2]
            if min(v for _, v in ch[-2:]) >= max(5.0, 3 * med):
                note = f"New construction or earthworks seen on {ch[-2][0]} and {ch[-1][0]} ({ch[-1][1]:.0f} ha of the base changed)."
        burns = [o for o in so if o.get("burn_ha") not in (None, "", "None")]
        if burns and float(burns[-1]["burn_ha"]) >= 1:
            note = (note + " " if note else "") + f"Burn scars seen on {burns[-1]['date']} ({float(burns[-1]['burn_ha']):.1f} ha)."
        if not sr and so:
            st = "optical"
        states[s["id"]] = st
        last_r = max((r["date"] for r in sr), default="")
        last_o = so[-1]["date"] if so else ""
        zl = next((z for d, z in reversed(zs) if z is not None), None)
        table.append([s["id"], st, ";".join(used), last_r, last_o, "" if zl is None else f"{zl:.2f}", main, note, ";".join(parts)])
    save_rows("base_state", ["site", "state", "dates", "last_radar", "last_optical", "z", "part", "note", "parts"], table)
    # theatre counts per day, replayed from 2022 over the backfilled scenes and the live ones (the history the model scores
    # against); a theatre has a row on days where at least one of its sites has a scored pass in the last 10 days
    if ALERTS:
        passes = S.site_passes(S.load_scenes(), sites)
        series = {}
        d = S.START
        while d <= today:
            st = {sid: S.state_on(p, d) for sid, p in passes.items()}
            cnt = {}
            for s in sites:
                v = st.get(s["id"])
                if v is None:
                    continue
                for t in s["theatres"]:
                    o, i = cnt.get(t, (0, 0))
                    cnt[t] = (o + (v == "out"), i + (v == "in"))
            for t, (o, i) in cnt.items():
                series.setdefault(t, []).append((d.isoformat(), o, i))
            d += dt.timedelta(days=1)
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
    ap.add_argument("--until", default="", help="backfill: last day to read (default today)")
    ap.add_argument("--parts", default="", help="backfill: read only these parts (apron,harbour,ground)")
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
            rr = radar_rows(s, start, a.until or today.isoformat(), per, done_r, parts=a.parts.split(",") if a.parts else None)
        except Exception as e:
            print(s["id"], "radar search failed:", repr(e)[:160], flush=True)
            rr = []
        oo = []
        if not a.no_optical:
            try:
                # optical needs the previous clear scenes for its change measure: read 90 days, keep only new rows
                seen = None if a.backfill_from else {sid for sid, site in done_o if site == s["id"]}
                oo = optical_rows(s, (today - dt.timedelta(days=90)).isoformat() if not a.backfill_from else start, today.isoformat(), max(8, per // 2),
                                  latest=not a.backfill_from, seen=seen) or []
            except Exception as e:
                print(s["id"], "optical search failed:", repr(e)[:160], flush=True)
        if a.dry_run:
            continue
        append_csv(SCENES, SCENE_COLS, rr)
        append_csv(OPTICAL, OPT_COLS, [o for o in oo if (o["scene_id"], s["id"]) not in done_o])
        have = {r[1] for r in chip_rows.values() if r[0] == s["id"]}
        if not a.backfill_from and (rr or oo or not have):      # chips only where something is new (or none exist yet)
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
PARTS = ("apron", "harbour", "ground")
PART_WHAT = {"apron": ("Aircraft", "on the aprons"), "harbour": ("Ships", "in the harbour"),
             "ground": ("Vehicles and equipment", "on the rest of the base (vehicle parks, launcher and storage yards)")}
GROUND_TESTED = False   # the ground part has not passed its backfill test yet (docs/BASEWATCH_STUDY_PLAN.md, ground amendment)
PART_NOTE = {"out": "fewer than usual", "in": "more than usual", "changed": "one pass off its usual range",
             "normal": "usual", "nodata": "no recent pass"}

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
        what, where = PART_WHAT.get(part, PART_WHAT["apron"])
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
        why_ = STATE_WHY.get(state_, "").format(where=where, what=what, dates=dates)
        if not ALERTS and state_ in ("out", "in", "changed"):
            why_ += " Not yet checked against past events, so it carries no weight in the risk numbers."
        prt = []
        for x in (r.get("parts") or "").split(";"):
            f = x.split(":")
            if len(f) == 4 and f[0] in PART_WHAT:
                prt.append({"p": f[0], "w": PART_WHAT[f[0]][0], "st": f[1], "z": float(f[2]) if f[2] else None,
                            "d": f[3].replace("/", " and "), "s": PART_NOTE.get(f[1], f[1]),
                            "t": f[0] != "ground" or GROUND_TESTED})
        gr = next((x for x in prt if x["p"] == "ground" and x["st"] in ("out", "in")), None)
        if gr and part != "ground":
            why_ += (f" Vehicles and equipment on the rest of the base: {gr['s']} on two passes ({gr['d']})."
                     + ("" if GROUND_TESTED else " That reading is not yet checked against past events and carries no weight."))
        out.append({"id": s["id"], "n": s["name"], "pr": prt, "lat": s["lat"], "lon": s["lon"], "k": s["kind"], "side": s["side"], "ths": s["theatres"],
                    "st": state_, "z": float(r["z"]) if r.get("z") else None, "last": r.get("last_radar", ""), "lo": r.get("last_optical", ""),
                    "pts": pts, "why": why_, "note": r.get("note", ""),
                    "wy": s.get("why", ""), "img": img})
    return out


if __name__ == "__main__":
    main()
