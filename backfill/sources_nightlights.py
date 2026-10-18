"""Night lights per place, daily: NASA Black Marble VNP46A2 (VIIRS day/night band, moonlight- and angle-corrected).

For every reference point on the map (config.CITIES) this keeps the mean radiance of the good pixels in a 0.1-degree box
around it (about 11 km across), in nW/cm2/sr, and the share of the box's pixels that were good that night. Only pixels
whose Mandatory_Quality_Flag is 0 or 1 (high quality) count; the gap-filled layer is not used, because it would fill a
blackout night with an older lit night. A cloudy night shows as a low good share, not as a dark place.

Why: the People group asks whether daily life is being disrupted. Lights out together with an internet outage reads as a
power cut, a physical event; lights on during an outage reads as a network cut, often censorship. This collector only
starts the history; nothing reads it yet.

Needs an Earthdata token (EARTHDATA_TOKEN, https://urs.earthdata.nasa.gov) and h5py + numpy, which the rest of the
back-fill does not use: the workflow installs them. Files come from NASA LAADS, one 10x10-degree tile per file.
Output: backfill/data/nightlights/<year>.csv, one row per day and place. A day whose tiles are all held is skipped.
"""
import csv
import datetime as dt
import os
import sys
import tempfile

import common as K

sys.path.insert(0, os.path.join(os.path.dirname(K.HERE), "warwatch"))
import config as C  # noqa: E402

PRODUCT = os.environ.get("NTL_PRODUCT", "VNP46A2")
COLLECTIONS = ("5200", "5000")      # Collection 2 first, then Collection 1
ARCHIVE = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/{coll}/{prod}/{y}/{doy:03d}"
OUT = os.path.join(K.DATA, "nightlights")
HALF = 0.05                         # half the box side, degrees
PX = 240                            # pixels per degree (15 arc-seconds); a tile is 2400 x 2400
COLS = ["day", "theatre", "place", "lat", "lon", "rad", "good", "tile"]


def places():
    """[(theatre, name, lat, lon)] from the map's reference points, each place once per theatre."""
    out = []
    for t, pts in C.CITIES.items():
        for name, lat, lon in pts:
            out.append((t, name, lat, lon))
    return out


def tile_of(lat, lon):
    """Black Marble tile id hHHvVV: h counts 10-degree columns east from 180W, v counts rows south from 90N."""
    return f"h{int((lon + 180) // 10):02d}v{int((90 - lat) // 10):02d}"


def box_px(lat, lon):
    """(row0, row1, col0, col1) of the box inside its tile, end-exclusive, clipped to the tile."""
    top = 90 - 10 * int((90 - lat) // 10)
    left = -180 + 10 * int((lon + 180) // 10)
    r0, r1 = int((top - (lat + HALF)) * PX), int((top - (lat - HALF)) * PX) + 1
    c0, c1 = int(((lon - HALF) - left) * PX), int(((lon + HALF) - left) * PX) + 1
    clip = lambda v: max(0, min(10 * PX, v))
    return clip(r0), clip(r1), clip(c0), clip(c1)


def _find(h5, suffix):
    hit = []
    h5.visititems(lambda n, o: hit.append(n) if n.split("/")[-1] == suffix and hasattr(o, "shape") else None)
    if not hit:
        raise KeyError(suffix)
    return h5[hit[0]]


def read_tile(path, pts):
    """{(theatre, place): (rad, good share)} for the points in this tile's file. rad is None when no pixel was good."""
    import h5py
    import numpy as np
    out = {}
    with h5py.File(path, "r") as h5:
        ds, qf = _find(h5, "DNB_BRDF-Corrected_NTL"), _find(h5, "Mandatory_Quality_Flag")
        scale = float(np.ravel(ds.attrs.get("scale_factor", [0.1]))[0])
        offset = float(np.ravel(ds.attrs.get("add_offset", [0.0]))[0])
        fill = int(np.ravel(ds.attrs.get("_FillValue", [65535]))[0])
        for t, name, lat, lon in pts:
            r0, r1, c0, c1 = box_px(lat, lon)
            v, q = ds[r0:r1, c0:c1].astype("float64"), qf[r0:r1, c0:c1]
            ok = ((q == 0) | (q == 1)) & (ds[r0:r1, c0:c1] != fill)
            n = ok.size
            good = float(ok.sum()) / n if n else 0.0
            out[(t, name)] = (round(float((v[ok] * scale + offset).mean()), 2) if ok.any() else None, round(good, 3))
    return out


def _listing(day, token):
    """(collection, {tile: file name}) for the day, or (None, {}) when the day is not published yet."""
    for coll in COLLECTIONS:
        url = ARCHIVE.format(coll=coll, prod=PRODUCT, y=day.year, doy=day.timetuple().tm_yday) + ".json"
        try:
            j = K.get(url, headers={"Authorization": f"Bearer {token}"}, retries=2)
        except RuntimeError:
            continue
        items = j.get("content", []) if isinstance(j, dict) else j
        names = [x.get("name", "") if isinstance(x, dict) else str(x) for x in items]
        files = {n.split(".")[2]: n for n in names if n.startswith(PRODUCT + ".") and n.endswith(".h5") and len(n.split(".")) > 3}
        if files:
            return coll, files
    return None, {}


def _read(path):
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        return {(r["day"], r["theatre"], r["place"]): r for r in csv.DictReader(f)}


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def cmd_nightlights(token, start, end):
    pts = places()
    by_tile = {}
    for p in pts:
        by_tile.setdefault(tile_of(p[2], p[3]), []).append(p)
    for year in range(start.year, end.year + 1):
        path = os.path.join(OUT, f"{year}.csv")
        rows = _read(path)
        got = 0
        for d in K.days(max(start, dt.date(year, 1, 1)), min(end, dt.date(year, 12, 31))):
            iso = d.isoformat()
            if all((iso, t, n) in rows for t, n, _, _ in pts):
                continue
            coll, files = _listing(d, token)
            if not files:
                K.log(iso, "not published yet or not found")
                continue
            for tile, ps in sorted(by_tile.items()):
                if all((iso, t, n) in rows for t, n, _, _ in ps) or tile not in files:
                    continue
                url = ARCHIVE.format(coll=coll, prod=PRODUCT, y=d.year, doy=d.timetuple().tm_yday) + "/" + files[tile]
                with tempfile.NamedTemporaryFile(suffix=".h5") as tmp:
                    try:
                        tmp.write(K.get(url, headers={"Authorization": f"Bearer {token}"}, raw=True, timeout=300, retries=3))
                        tmp.flush()
                        vals = read_tile(tmp.name, ps)
                    except Exception as e:
                        K.log("skip", iso, tile, str(e)[:160])
                        continue
                for t, name, lat, lon in ps:
                    rad, good = vals[(t, name)]
                    rows[(iso, t, name)] = {"day": iso, "theatre": t, "place": name, "lat": lat, "lon": lon,
                                            "rad": "" if rad is None else rad, "good": good, "tile": tile}
            got += 1
            _write(path, rows)
            K.log(iso, coll, len(files), "tiles listed")
        K.log(year, "done:", got, "days read")
