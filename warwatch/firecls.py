"""Classes for satellite fire detections: anomaly, industrial, seasonal farm burning and so on (docs/FIRECLASS_PLAN.md, F2).

Standard library only, so the dashboard build can run it. The reference tables it reads are built by fireref.py from the
NASA FIRMS VIIRS S-NPP archive (2012 to last year) and from public site lists (OpenStreetMap, World Bank GGFR, WRI):

    data/fire_cells_<box>.csv.gz   ~1 km cells that burn often or carry NASA's static/volcano/offshore type
    data/fire_first_<box>.bin.gz   first year each ~1 km cell of the box burned (0 = never)
    data/fire_coarse_<box>.csv.gz  ~11 km cells: per year, a 12-bit mask of the months with farm or grass fires
    data/fire_sites.csv            industrial and sensitive sites (flares, refineries, bases, depots, ports...)

Each detection gets c (class), a (score 0 to 100), why (plain reason) and site (name, or "").
Classes: anom (unusual), hot (much hotter than usual at an industrial site), unex (unexplained), seas (seasonal farm or
grass fire), ind (routine industrial heat), volc (volcano), off (offshore platform or flare).
"""
import calendar
import csv
import datetime as dt
import gzip
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402

DATA = os.path.join(HERE, "data")
REPLAY_DIR = os.path.join(os.path.dirname(HERE), "backfill", "data", "firecls")   # fireref.py replay: archive history of the unusual-fire counts
FINE = 0.01           # degrees, ~1.1 km
COARSE = 0.1          # degrees, ~11 km
Y0 = 2012             # first archive year (VIIRS S-NPP)
EXPLAINED = ("seas", "ind", "volc", "off")
ANOMALY = ("anom", "hot")
INDUSTRIAL = ("flare", "oilgas", "steel", "power", "cement")
SENSITIVE = ("military", "airfield", "port", "fuel", "substation")
KIND_NAME = {"flare": "Gas flare", "oilgas": "Oil and gas plant", "steel": "Steel works", "power": "Power plant", "cement": "Cement works",
             "military": "military site", "airfield": "airfield", "port": "port", "fuel": "fuel depot", "substation": "power substation"}
ANOM_AT = 60          # an unexplained detection with this score or more is an anomaly
# Starting weights (FIRECLASS_PLAN F2). Tuned only on 2018-2021 and frozen before the 2022+ test (docs/FIREANOM_PLAN.md).
W = {"base": 30, "novel": 20, "rare_season": 10, "sensitive": 25, "frp50": 10, "frp200": 10, "cluster": 10, "night": 5, "seasonal": -15,
     "static_t2": 5, "static_days": 60, "static_years": 2, "seas_p": 0.4, "rare_p": 0.1, "sens_km": 2.0, "ind_km": 1.0}


def fine(lat, lon):
    return round(lat / FINE), round(lon / FINE)


def coarse(lat, lon):
    return round(lat / COARSE), round(lon / COARSE)


def km(la1, lo1, la2, lo2):
    x = math.radians(lo2 - lo1) * math.cos(math.radians((la1 + la2) / 2))
    return 6371.0 * math.hypot(x, math.radians(la2 - la1))


def path(name):
    return os.path.join(DATA, name)


# ---------------------------------------------------------------- reference tables
CELL_COLS = ("i", "j", "t1", "t2", "t3", "frp95", "frpmax", "n95", "last")


class Ref:
    """Reference tables for one box. cells: {(i, j): row dict}; first: grid of first years; coarse: {(I, J): {year: mask}}."""
    def __init__(self, box, cells, years, grid, coarse, cyears, sites):
        self.box, self.cells, self.years, self.coarse, self.cyears, self.sites = box, cells, years, coarse, cyears, sites
        self.grid = grid       # (i0, j0, rows, cols, bytes) or None

    def first_year(self, i, j):
        """First archive year the fine cell burned, 0 for never, None when outside the grid."""
        if not self.grid:
            return None
        i0, j0, rows, cols, b = self.grid
        r, c = i - i0, j - j0
        if 0 <= r < rows and 0 <= c < cols:
            v = b[r * cols + c]
            return 2000 + v if v else 0
        return None


def read_cells(fh):
    """fire_cells CSV -> ({(i, j): {t1, t2, t3, frp95, frpmax, n95, last, d: {year: days}}}, [years])."""
    rd = csv.reader(fh)
    head = next(rd)
    years = [int(h[1:]) for h in head if h.startswith("d") and h[1:].isdigit()]
    out = {}
    for r in rd:
        if not r or r[0].startswith("#"):
            continue
        d = dict(zip(head, r))
        out[(int(d["i"]), int(d["j"]))] = {"t1": int(d["t1"]), "t2": int(d["t2"]), "t3": int(d["t3"]), "frp95": float(d["frp95"]), "frpmax": float(d["frpmax"]),
                                           "n95": float(d["n95"]), "last": d["last"], "d": {y: int(d[f"d{y}"]) for y in years}}
    return out, years


def write_cells(fh, cells, years):
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(list(CELL_COLS) + [f"d{y}" for y in years])
    for (i, j), c in sorted(cells.items()):
        w.writerow([i, j, c["t1"], c["t2"], c["t3"], f"{c['frp95']:.1f}", f"{c['frpmax']:.1f}", f"{c['n95']:.1f}", c["last"]] + [c["d"].get(y, 0) for y in years])


def read_coarse(fh):
    rd = csv.reader(fh)
    head = next(rd)
    years = [int(h[1:]) for h in head if h.startswith("m") and h[1:].isdigit()]
    out = {}
    for r in rd:
        if r:
            out[(int(r[0]), int(r[1]))] = {y: int(v) for y, v in zip(years, r[2:]) if int(v)}
    return out, years


def write_coarse(fh, cells, years):
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["I", "J"] + [f"m{y}" for y in years])
    for (I, J), m in sorted(cells.items()):
        w.writerow([I, J] + [m.get(y, 0) for y in years])


def grid_dims(box):
    la0, la1, lo0, lo1 = C.FIRMS_BOX[box]
    i0, j0 = round(la0 / FINE), round(lo0 / FINE)
    return i0, j0, round(la1 / FINE) - i0 + 1, round(lo1 / FINE) - j0 + 1


def read_grid(raw):
    head, _, body = raw.partition(b"\n")
    i0, j0, rows, cols = (int(x) for x in head.split())
    if len(body) != rows * cols:
        raise ValueError("fire_first grid has the wrong size")
    return i0, j0, rows, cols, body


def write_grid(i0, j0, rows, cols, body):
    return f"{i0} {j0} {rows} {cols}\n".encode() + bytes(body)


SITE_COLS = ("id", "name", "kind", "lat", "lon", "src")


def read_sites(fh):
    out = []
    for r in csv.DictReader(line for line in fh if not line.startswith("#")):
        try:
            out.append({"name": r["name"], "kind": r["kind"], "lat": float(r["lat"]), "lon": float(r["lon"]), "src": r.get("src", "")})
        except (KeyError, ValueError):
            continue
    return out


class Sites:
    """Sites bucketed by 0.05 degrees for nearest lookups within a few km."""
    B = 0.05

    def __init__(self, rows):
        self.b = {}
        for s in rows:
            self.b.setdefault((math.floor(s["lat"] / self.B), math.floor(s["lon"] / self.B)), []).append(s)

    def near(self, lat, lon, kinds, r_km):
        """Nearest site of one of `kinds` within r_km -> (site, km) or (None, None)."""
        bi, bj = math.floor(lat / self.B), math.floor(lon / self.B)
        span = 1 + int(r_km / (111 * self.B * max(0.2, math.cos(math.radians(lat)))))
        best = (None, None)
        for di in range(-1, 2):
            for dj in range(-span, span + 1):
                for s in self.b.get((bi + di, bj + dj), ()):
                    if s["kind"] in kinds:
                        d = km(lat, lon, s["lat"], s["lon"])
                        if d <= r_km and (best[1] is None or d < best[1]):
                            best = (s, d)
        return best


_SITES = {}
_REF = {}


def load_sites():
    if "all" not in _SITES:
        try:
            with open(path("fire_sites.csv"), newline="", encoding="utf-8") as f:
                _SITES["all"] = read_sites(f)
        except OSError:
            _SITES["all"] = []
    return _SITES["all"]


def load(box):
    """The box's Ref, or None when its reference tables have not been built."""
    if box in _REF:
        return _REF[box]
    ref = None
    try:
        with gzip.open(path(f"fire_cells_{box}.csv.gz"), "rt", newline="") as f:
            cells, years = read_cells(f)
        with gzip.open(path(f"fire_coarse_{box}.csv.gz"), "rt", newline="") as f:
            co, cyears = read_coarse(f)
        try:
            with gzip.open(path(f"fire_first_{box}.bin.gz"), "rb") as f:
                grid = read_grid(f.read())
        except OSError:
            grid = None
        la0, la1, lo0, lo1 = C.FIRMS_BOX[box]
        sites = Sites([s for s in load_sites() if la0 - 0.1 <= s["lat"] <= la1 + 0.1 and lo0 - 0.1 <= s["lon"] <= lo1 + 0.1])
        ref = Ref(box, cells, years, grid, co, cyears, sites)
    except (OSError, ValueError, KeyError):
        ref = None
    _REF[box] = ref
    return ref


# ---------------------------------------------------------------- rules
def _nb(ref, i, j):
    return [ref.cells[(i + a, j + b)] for a in (-1, 0, 1) for b in (-1, 0, 1) if (i + a, j + b) in ref.cells]


def static_row(row, year):
    """Burns on one day in six or more, year after year, or NASA flags it as a static land source."""
    return row["t2"] >= W["static_t2"] or persistent(row, year)


def persistent(row, year):
    """Burned on at least static_days days in each of static_years of the five years before `year`."""
    return sum(1 for y in range(year - 5, year) if row["d"].get(y, 0) >= W["static_days"]) >= W["static_years"]


def burn_pct(rows, year):
    """Share of days the busiest neighbouring cell burned over the 3 years before `year`, in percent."""
    best = 0.0
    for r in rows:
        ys = [r["d"].get(y, 0) for y in range(year - 3, year) if y in r["d"]]
        if ys:
            best = max(best, sum(ys) / len(ys) / 365.0)
    return round(100 * min(1.0, best))


def months_for(day):
    """The detection's month plus the adjacent month when it is within 10 days of a month boundary (1-based)."""
    m = {day.month}
    if day.day <= 10:
        m.add(12 if day.month == 1 else day.month - 1)
    if day.day > calendar.monthrange(day.year, day.month)[1] - 10:
        m.add(1 if day.month == 12 else day.month + 1)
    return m


def base_years(box, year, available):
    y0, y1 = C.FIRE_CLIM_YEARS.get(box, (Y0, year - 1))
    return [y for y in available if y0 <= y <= min(y1, year - 1)]


def seasonal_p(ref, lat, lon, day):
    """Share of baseline years in which this ~11 km area (or a neighbour) had fires in this part of the year; None with < 4 years."""
    ys = base_years(ref.box, day.year, ref.cyears)
    if len(ys) < 4:
        return None
    bits = 0
    for m in months_for(day):
        bits |= 1 << (m - 1)
    I, J = coarse(lat, lon)
    hit = 0
    for y in ys:
        if any(ref.coarse.get((I + a, J + b), {}).get(y, 0) & bits for a in (-1, 0, 1) for b in (-1, 0, 1)):
            hit += 1
    return hit / len(ys)


def novel(ref, i, j, year):
    """True when no cell of the 3 x 3 neighbourhood burned in any archive year before `year`; None outside the grid."""
    seen = None
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            f = ref.first_year(i + a, j + b)
            if f is None:
                continue
            seen = seen or False
            if f and f < year:
                return False
    return None if seen is None else True


def _same_pass(pts):
    """{id(p): number of detections in the same pass within 2 km, itself included}."""
    by = {}
    for p in pts:
        by.setdefault(p.get("ts") or p.get("date"), []).append(p)
    out = {}
    for grp in by.values():
        cell = {}
        for p in grp:
            cell.setdefault((math.floor(p["lat"] / 0.02), math.floor(p["lon"] / 0.02)), []).append(p)
        for p in grp:
            bi, bj = math.floor(p["lat"] / 0.02), math.floor(p["lon"] / 0.02)
            n = 0
            for a in (-1, 0, 1):
                for b in (-2, -1, 0, 1, 2):
                    n += sum(1 for q in cell.get((bi + a, bj + b), ()) if km(p["lat"], p["lon"], q["lat"], q["lon"]) <= 2.0)
            out[id(p)] = n
    return out


def _name(s):
    return s["name"] or KIND_NAME.get(s["kind"], "an industrial site")


def _set(p, c, a, why, site=""):
    p["c"], p["a"], p["why"], p["site"] = c, int(max(0, min(100, round(a)))), why, site
    p["routine"] = c in EXPLAINED
    return p


def classify_one(p, ref, near_n, day):
    lat, lon, frp = p["lat"], p["lon"], float(p.get("frp") or 0)
    sat = frp == 0 and float(p.get("bright_ti4") or 0) >= 367      # saturated pixel: very hot
    i, j = fine(lat, lon)
    rows = _nb(ref, i, j)
    year = day.year
    if any(r["t1"] >= 3 for r in rows):
        return _set(p, "volc", 5, "Volcano: NASA marks this spot as an active volcano.")
    sens, sens_km = ref.sites.near(lat, lon, SENSITIVE, W["sens_km"])
    # offshore = a persistent source over water (a platform). NASA's type 3 marks any detection over water, so reed fires in
    # river deltas and shelling along a river front would otherwise be hidden as "offshore".
    # Waterside plants (steel works on a river or a bay) also get some type 3 pixels, so water must outnumber land.
    if any(r["t3"] >= 3 and r["t3"] > r["t2"] and persistent(r, year) for r in rows) and not (sens and sens["kind"] in ("port", "military")):
        return _set(p, "off", 5, "Offshore platform or flare: NASA marks this spot as an offshore heat source.")
    stat = [r for r in rows if static_row(r, year)]
    ind, _ = ref.sites.near(lat, lon, INDUSTRIAL, W["ind_km"])
    if stat or ind:
        name = _name(ind) if ind else ""
        f95 = max([r["frp95"] for r in stat or rows] or [0.0])
        n95 = max([r["n95"] for r in stat or rows] or [0.0])
        if stat or rows:
            hotter = frp >= max(3 * f95, f95 + 100) or near_n >= 3 * n95 + 3 or sat
        else:
            hotter = frp >= 300 or sat          # a listed plant with no fire record: only a very large fire counts
        if hotter:
            usual = f"{f95:.0f} MW" if f95 else "no usual fire"
            what = f"{frp:.0f} MW" if not sat else "a saturated (very hot) pixel"
            return _set(p, "hot", 75, f"Much more heat than usual at {name or 'this industrial site'}: {what} against a usual {usual}.", name)
        kind = KIND_NAME.get(ind["kind"], "Industrial heat") if ind else "Industrial heat"
        where = f" at {ind['name']}" if ind and ind["name"] else ""
        pct = burn_pct(stat or rows, year)
        tail = f": this spot burns on {pct}% of days." if pct else "."
        return _set(p, "ind", 10, f"{kind}{where}{tail}", name)
    sp = seasonal_p(ref, lat, lon, day)
    month = day.strftime("%B")
    if sp is not None and sp >= W["seas_p"] and not sens and frp < 100:
        return _set(p, "seas", 15, f"This area burns in most years in {month} (farm and grass fires).")
    a, why = W["base"], []
    nv = novel(ref, i, j, year)
    if nv:
        a += W["novel"]
        why.append(f"No fire here in {year - Y0} years of records")
    if sp is not None and sp < W["rare_p"]:
        a += W["rare_season"]
        why.append(f"this area rarely burns in {month}")
    if sens:
        a += W["sensitive"]
        why.append(f"{sens_km:.1f} km from {sens['name'] or KIND_NAME[sens['kind']]}")
    if frp >= 50 or sat:
        a += W["frp50"]
    if frp >= 200 or sat:
        a += W["frp200"]
    if near_n >= 3:
        a += W["cluster"]
        why.append(f"{near_n} hot spots together")
    if p.get("daynight") == "N":
        a += W["night"]
    if sp is not None and sp >= W["seas_p"]:
        a += W["seasonal"]
        why.append(f"this area often burns in {month}")
    heat = "a saturated (very hot) pixel" if sat else f"{frp:.0f} MW"
    night = " at night" if p.get("daynight") == "N" else ""
    lead = "; ".join(why)
    text = (lead[0].upper() + lead[1:] + f", {heat}{night}." if lead else f"Not a known industrial site or farm-burning area, {heat}{night}.")
    c = "anom" if a >= ANOM_AT else "unex"
    return _set(p, c, a, text, sens["name"] if sens else "")


def _fallback(pts):
    """No reference tables for this box: the old 7-day rule (a cell burning on 3 of the days read is routine)."""
    import osint
    osint.mark_routine(pts)
    for p in pts:
        if p["routine"]:
            _set(p, "ind", 10, "Burns on most days this week (gas flare or industry).")
        else:
            _set(p, "unex", 40, "Does not burn here every day.")
    return pts


def classify(pts, box, today=None, ref=None):
    """Sets c, a, why, site (and routine = explained) on each detection dict of one box. Returns pts."""
    ref = ref if ref is not None else load(box)
    if ref is None:
        return _fallback(pts)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    near = _same_pass(pts)
    for p in pts:
        try:
            day = dt.date.fromisoformat(p["date"])
        except (KeyError, ValueError):
            day = today
        classify_one(p, ref, near.get(id(p), 1), day)
    econ_check(pts, box)
    assign_clusters(pts, box)
    review(pts)
    return pts


def assign_clusters(pts, box):
    """Gives every unexplained or anomalous detection a cluster id: the id of the highest-scoring such detection of the same
    day within 2 km. The imagery review (F5) works per cluster."""
    todo = sorted((p for p in pts if p.get("c") not in EXPLAINED), key=lambda p: -p.get("a", 0))
    grid = {}
    for p in todo:
        bi, bj = math.floor(p["lat"] / 0.02), math.floor(p["lon"] / 0.02)
        hit = None
        for a in (-1, 0, 1):
            for b in (-2, -1, 0, 1, 2):
                for q in grid.get((p["date"], bi + a, bj + b), ()):
                    if km(p["lat"], p["lon"], q["lat"], q["lon"]) <= 2.0:
                        hit = q
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            p["cid"] = hit["cid"]
        else:
            p["cid"] = cluster_id(box, p)
            grid.setdefault((p["date"], bi, bj), []).append(p)
    return pts


# ---------------------------------------------------------------- satellite image review (FIRECLASS F5)
def cluster_id(box, p):
    i, j = fine(p["lat"], p["lon"])
    return f"{box}_{i}_{j}_{p['date']}"


def load_review(path_=None):
    import store
    out = {}
    for r in store.cache_rows("fire_review") if path_ is None else _rows(path_):
        if len(r) >= 9 and r[0] != "cid":
            out[r[0]] = {"verdict": r[1], "ha": float(r[2] or 0), "lc": r[3], "bd": r[4], "ad": r[5]}
    return out


def _rows(p):
    with open(p, newline="") as f:
        return [r for r in csv.reader(f) if r]


def review(pts, rev=None):
    """Adjusts classes with the Sentinel-2 check written by firereview.py, matched on p['cid']."""
    rev = rev if rev is not None else load_review()
    if not rev:
        return pts
    for p in pts:
        r = rev.get(p.get("cid", ""))
        if not r:
            continue
        p["rv"] = r
        if r["verdict"] == "scar" and r["lc"] == "cropland" and p["c"] in ("anom", "unex"):
            _set(p, "seas", 15, "The satellite image shows a burnt field. " + p["why"], p.get("site", ""))
        elif r["verdict"] == "scar":
            _set(p, p["c"], p["a"] + 10 if p["c"] in ("anom", "unex", "hot") else p["a"], p["why"] + f" The satellite image shows a burn scar ({r['ha']:.1f} ha) on {r['ad']}.", p.get("site", ""))
            if p["c"] == "unex" and p["a"] >= ANOM_AT:
                p["c"] = "anom"
        elif r["verdict"] == "none":
            _set(p, p["c"], p["a"] - 10 if p["c"] in ("anom", "unex") else p["a"], p["why"] + f" No burn scar visible on {r['ad']}.", p.get("site", ""))
            if p["c"] == "anom" and p["a"] < ANOM_AT:
                p["c"] = "unex"
        elif r["verdict"] in ("wait", "cloud"):
            p["why"] += " Waiting for a clear satellite image." if r["verdict"] == "wait" else " No clear satellite image yet (cloud)."
    return pts


# ---------------------------------------------------------------- caches written by the build
ANOMS = "fire_anoms"          # clusters with an anomaly, for the imagery review (FIRECLASS F5)
DAILY = "firms_anom_events"   # [date, box, count of S-NPP anom + hot detections]
KEEP_DAYS = 21


def save_anoms(pts, today=None):
    """Merges this run's anomalous clusters into history/cache/fire_anoms.csv: cid, box, lat, lon, first_ts, last_ts, max_frp, score, class."""
    import store
    today = today or dt.datetime.now(dt.timezone.utc).date()
    cut = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    rows = {r[0]: r for r in store.cache_rows(ANOMS) if len(r) == 9 and r[0] != "cid" and r[4][:10] >= cut}
    for p in pts:
        if p.get("c") not in ANOMALY or not p.get("cid"):
            continue
        ts = p.get("ts") or p["date"]
        r = rows.get(p["cid"])
        if r is None:
            rows[p["cid"]] = [p["cid"], p.get("box", ""), f"{p['lat']:.4f}", f"{p['lon']:.4f}", ts, ts, f"{p['frp']:.1f}", str(p["a"]), p["c"]]
        else:
            r[4], r[5] = min(r[4], ts), max(r[5], ts)
            if p["frp"] > float(r[6]):
                r[6] = f"{p['frp']:.1f}"
            if p["a"] > int(r[7]):
                r[7], r[8] = str(p["a"]), p["c"]
    out = sorted(rows.values(), key=lambda r: r[4])
    store.cache_rows_save(ANOMS, [["cid", "box", "lat", "lon", "first_ts", "last_ts", "max_frp", "score", "c"]] + out)
    return len(out)


def save_daily(pts, today=None, days=7):
    """Daily S-NPP anomaly counts per box for the firms_anom_<box> series. The last `days` full days are recounted each run
    (later passes and clusters can change a class); older days are kept as they were."""
    import store
    today = today or dt.datetime.now(dt.timezone.utc).date()
    window = {(today - dt.timedelta(days=k)).isoformat() for k in range(1, days + 1)}
    boxes = {p.get("box") for p in pts if p.get("box")}
    cnt = {(d, b): 0 for d in window for b in boxes}
    for p in pts:
        if p.get("sat", "SNPP") == "SNPP" and p.get("c") in ANOMALY and p["date"] in window and p.get("box"):
            cnt[(p["date"], p["box"])] += 1
    keep = [r for r in store.cache_rows(DAILY) if len(r) == 3 and (r[0], r[1]) not in cnt]
    rows = sorted(keep + [[d, b, str(n)] for (d, b), n in cnt.items()])
    store.cache_rows_save(DAILY, rows)
    return len(rows)


def daily_series(box):
    import store
    return sorted((d, float(n)) for d, b, n in (r for r in store.cache_rows(DAILY) if len(r) == 3) if b == box)


def archive_series(box):
    """Replayed archive counts (fireref.py replay) for the days before the live cache starts -> [(date, count)]."""
    try:
        with open(os.path.join(REPLAY_DIR, f"firms_anom_{box}.csv"), newline="") as f:
            return [(r[0], float(r[1])) for r in csv.reader(f) if len(r) == 2 and r[0][:1].isdigit()]
    except OSError:
        return []


def series(box):
    """Archive replay, then the live daily counts: the firms_anom_<box> series."""
    live = daily_series(box)
    first = live[0][0] if live else "9999"
    return [(d, v) for d, v in archive_series(box) if d < first] + live


# ---------------------------------------------------------------- second opinion for Ukraine (FIRECLASS F3)
ECON_URL = "https://raw.githubusercontent.com/TheEconomist/the-economist-war-fire-model/master/output-data/ukraine_war_fires.csv"
ECON = "econ_war_fires"       # cache: date, lat, lon of fires The Economist's model calls war-related (last 21 days)


def econ_refresh(today=None, url=ECON_URL):
    """Streams The Economist's war-fire file (CC BY 4.0, ~70 MB, updated several times a day) and keeps the last 21 days of
    fires it marks war-related. Runs in imagery.yml every 6 hours, not in the 30-minute build."""
    import store
    import urllib.request
    today = today or dt.datetime.now(dt.timezone.utc).date()
    cut = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    req = urllib.request.Request(url, headers={"User-Agent": "warwatch (github.com/khourix/warwatch)"})
    out = []
    with urllib.request.urlopen(req, timeout=300) as f:
        rd = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        head = next(rd)
        ix = {h: k for k, h in enumerate(head)}
        la, lo, d, w = ix["LATITUDE"], ix["LONGITUDE"], ix["date"], ix["war_fire"]
        for r in rd:
            try:
                if r[w] == "1" and r[d] >= cut:
                    out.append([r[d], f"{float(r[la]):.4f}", f"{float(r[lo]):.4f}"])
            except (IndexError, ValueError):
                continue
    store.cache_rows_save(ECON, sorted(out))
    return len(out)


_ECON = {}


def econ_index():
    if "s" not in _ECON:
        import store
        rows = [{"name": "", "kind": "econ", "lat": float(r[1]), "lon": float(r[2]), "date": r[0]} for r in store.cache_rows(ECON) if len(r) == 3]
        _ECON["s"] = Sites(rows) if rows else None
    return _ECON["s"]


def econ_check(pts, box):
    """Ukraine only: a detection within 1 km and 1 day of a fire The Economist's model calls war-related gets +15 and a note.
    A 'seasonal' one becomes unexplained: their model already allows for the farm-burning season."""
    if box != "ukraine":
        return pts
    idx = econ_index()
    if idx is None:
        return pts
    for p in pts:
        if p.get("c") not in ("anom", "unex", "seas"):
            continue
        try:
            day = dt.date.fromisoformat(p["date"])
        except (KeyError, ValueError):
            continue
        bi, bj = math.floor(p["lat"] / Sites.B), math.floor(p["lon"] / Sites.B)
        near = [s for a in (-1, 0, 1) for b in (-1, 0, 1) for s in idx.b.get((bi + a, bj + b), ())]
        if any(abs((dt.date.fromisoformat(s["date"]) - day).days) <= 1 and km(p["lat"], p["lon"], s["lat"], s["lon"]) <= 1.0 for s in near):
            if p["c"] == "seas":
                p["c"], p["a"], p["routine"] = "unex", 40, False   # their flag alone does not make it unusual (40 + 15 < 60)
            p["a"] = min(100, p["a"] + 15)
            if p["c"] == "unex" and p["a"] >= ANOM_AT:
                p["c"] = "anom"
            p["why"] += " The Economist's war-fire model also marks this fire as war-related."
            p["econ"] = 1
    return pts
