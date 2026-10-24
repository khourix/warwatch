"""Civil flights from the adsb.lol daily traces: diversions, turnbacks and holding at theatre airports, airport traffic and
business-jet departures (docs/FLIGHTS.md). Standard library only; backfill/sources_adsb.py feeds it every trace of the day
while it counts military aircraft, so the archive is still read once.

Each trace is cut into legs, from a take-off to a landing. A take-off or landing is a switch between ground and air reports,
or, where the receivers lose the aircraft low down, the first or last point below 3,000 ft within 15 km of an airport. A gap in
coverage while the aircraft is high (over Iran or the open sea, say) does not end the leg, so a Doha-London flight stays one leg.

    departure   an airline flight (ICAO airline callsign on an airliner) seen taking off from a theatre airport
    diversion   came down below 20,000 ft within 150 km of the airport its route goes to, then landed at least 50 km away at an
                airport not on the route (routes from github.com/vradarserver/standing-data, CC0, updated daily)
    turnback    an airline flight that landed back where it took off after 20 minutes to 4 hours in the air, in view throughout
    holding     an airline flight that circled at least twice (720 degrees of turning) within 60 km of where it landed, below 20,000 ft

Training flights, helicopters and private flights are not judged, even under an airline-style callsign. A diversion needs the route
table, so an unknown callsign is skipped rather than guessed. Business jets are counted, never listed, and aircraft whose owners
asked not to be shown (LADD and PIA flags) never appear by name in anything this writes.
"""
import csv
import io
import math
import os
import re
import tarfile
import urllib.request

ROUTES_TAR = "https://codeload.github.com/vradarserver/standing-data/tar.gz/refs/heads/main"

# ICAO type designators of business jets (Doc 8643). Airliner-based VIP jets (BBJ, ACJ) share airliner codes and are not counted.
BIZJET = {
    "GLF2", "GLF3", "GLF4", "GLF5", "GLF6", "GA5C", "GA6C", "GA7C", "GA8C", "GALX", "G150", "G280", "GLEX", "GL5T", "GL6T", "GL7T", "GL8T",
    "CL30", "CL35", "CL60", "F2TH", "F900", "FA7X", "FA8X", "FA6X", "FA50", "FA10", "FA20", "C25A", "C25B", "C25C", "C25M", "C500",
    "C501", "C510", "C525", "C550", "C551", "C560", "C56X", "C650", "C680", "C68A", "C700", "C750", "LJ31", "LJ35", "LJ40", "LJ45",
    "LJ55", "LJ60", "LJ70", "LJ75", "E35L", "E545", "E550", "E50P", "E55P", "H25A", "H25B", "H25C", "HA4T", "PRM1", "BE40", "PC24",
    "HDJT", "SF50", "EA50", "ASTR", "WW24", "GLF7",
}
# Airport country (ISO 3166-1 alpha-2, as standing-data gives it) -> the theatre its airports count for. Russia's western
# airports count for Ukraine (the Moscow business-jet exodus of 2022 is the case people cite); the rest of Russia does not.
THEATRE_ISO = {
    "QA": "gulf", "AE": "gulf", "BH": "gulf", "KW": "gulf", "SA": "gulf", "OM": "gulf", "IQ": "iraq", "IR": "iran", "IL": "israel",
    "JO": "israel", "CY": "israel", "LB": "lebanon", "SY": "syria", "YE": "yemen", "DJ": "yemen", "ER": "yemen", "UA": "ukraine",
    "BY": "ukraine", "MD": "ukraine", "PL": "europe_east", "LT": "europe_east", "LV": "europe_east", "EE": "europe_east",
    "FI": "europe_east", "RO": "europe_east", "TW": "taiwan", "KR": "korea", "KP": "korea", "PH": "scs", "VN": "scs",
    "IN": "southasia", "PK": "southasia", "LY": "libya", "SD": "sudan", "SS": "sudan", "CD": "drc", "VE": "venezuela", "GY": "venezuela",
}
DONE = "flights_legs"  # airline legs seen touching a theatre airport each day: coverage, and the mark that a day was read
AIRPORT_HEAD = ["date", "icao", "dep", "arr", "div_away", "div_in", "turnback", "hold", "bizjet_dep", "bizjet_out"]
EVENT_HEAD = ["date", "time", "kind", "call", "type", "from", "planned", "landed", "lat", "lon"]
POINT = re.compile(rb"\[-?[\d.]+,\s*(-?\d+\.\d+),\s*(-?\d+\.\d+),")
RU_WEST = ("UU", "UL", "UR", "UW")   # ICAO prefixes of Moscow, St Petersburg, the south and the Volga
GAP_S = 1800          # a gap this long while low (or with a new callsign after it) ends a leg
MAX_GAP_S = 5 * 3600  # any gap longer than this ends a leg
LOW_FT = 3000         # first or last point below this, near an airport, stands for a take-off or landing out of view
NEAR_GROUND_KM = 5
NEAR_LOW_KM = 15
MIN_AIR_S = 300
TURNBACK_S, TURNBACK_MAX_S = 1200, 4 * 3600
SEEN_GAP_S = 600      # a turnback must have no gap longer than this
HOLD_KM, HOLD_FT, HOLD_DEG = 60, 20000, 720
APPROACH_KM, APPROACH_FT, DIVERT_KM = 150, 20000, 50
# Airliner type designators, for legs whose emitter category is missing: Airbus, Boeing, Embraer and Bombardier jets, ATR, Dash 8,
# Superjet, A220, MD-80/90/11, COMAC, Ilyushin, Antonov, Tupolev, Fokker, BAe 146 and the larger turboprops.
AIRLINER = re.compile(r"^(A3\d[\dA-Z]|A2[01]N|A3[45][\dK]|A388|A30B|A31\d|B7[1-8][\dA-Z]|B3[789XM]M|B3XM|E1[79]\d|E2[79]\d|E7[05][\dLS]|"
                      r"E29\d|CRJ\d|AT[47]\d|DH8[A-D]|SU95|BCS[13]|MD[89]\d|MD11|C919|ARJ21|IL[679]\d|AN\d{2,3}|T20\d|F100|F70|B46\d|RJ[0-9]{2}|SF34|J328)$")


def km(la1, lo1, la2, lo2):
    p = math.pi / 180
    a = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(min(1.0, math.sqrt(a)))


class Airports:
    """Airports with an ICAO and an IATA code (so heliports and strips drop out), with a 1-degree grid for nearest lookups.
    `near` holds the grid cells within a cell of a theatre airport, so traces that never come close are skipped cheaply."""
    def __init__(self, rows):
        self.info, self.grid, self.near = {}, {}, set()
        for icao, name, iso, la, lo in rows:
            self.info[icao] = (name, iso, la, lo)
            cell = (int(math.floor(la)), int(math.floor(lo)))
            self.grid.setdefault(cell, []).append(icao)
            if self.theatre(icao):
                self.near.update((cell[0] + dy, cell[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1))

    def touches(self, trace, step=20):
        """True when any sampled point of the trace lies near a theatre airport."""
        near = self.near
        for p in trace[::step] + trace[-1:]:
            if p[1] is not None and p[2] is not None and (int(math.floor(p[1])), int(math.floor(p[2]))) in near:
                return True
        return False

    def maybe_near(self, raw, samples=160):
        """The same test on the raw trace bytes before they are parsed: reads about 160 points spread through the file."""
        i = raw.find(b'"trace"')
        if i < 0:
            return False
        near, n = self.near, len(raw)
        for pos in list(range(i, n, max(1, (n - i) // samples))) + [max(i, n - 1500)]:
            m = POINT.search(raw, pos, pos + 1500)
            if m and (int(math.floor(float(m.group(1)))), int(math.floor(float(m.group(2))))) in near:
                return True
        return False

    def nearest(self, la, lo, max_km):
        best, bd = None, max_km
        gy, gx = int(math.floor(la)), int(math.floor(lo))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for icao in self.grid.get((gy + dy, gx + dx), ()):
                    _, _, a, o = self.info[icao]
                    d = km(la, lo, a, o)
                    if d <= bd:
                        best, bd = icao, d
        return best

    def theatre(self, icao):
        if not icao or icao not in self.info:
            return None
        if icao.startswith(RU_WEST):
            return "ukraine"
        return THEATRE_ISO.get(self.info[icao][1])


def read_standing_data(fileobj):
    """The standing-data repository tarball -> (Airports, {callsign: [icao, ...]})."""
    apt, routes = [], {}
    with tarfile.open(fileobj=fileobj, mode="r|gz") as tf:
        for m in tf:
            if not m.isfile() or not m.name.endswith(".csv"):
                continue
            part = "/airports/" in m.name and "airports" or "/routes/" in m.name and "routes"
            if not part:
                continue
            text = tf.extractfile(m).read().decode("utf-8-sig", "replace")
            for r in csv.DictReader(io.StringIO(text)):
                if part == "airports":
                    icao, iata = (r.get("ICAO") or "").strip(), (r.get("IATA") or "").strip()
                    if len(icao) == 4 and iata:
                        try:
                            apt.append((icao, r.get("Name", ""), r.get("CountryISO2", ""), float(r["Latitude"]), float(r["Longitude"])))
                        except (KeyError, ValueError):
                            pass
                else:
                    codes = [c for c in (r.get("AirportCodes") or "").split("-") if c]
                    if r.get("Callsign") and len(codes) >= 2:
                        routes[r["Callsign"].strip()] = codes
    return Airports(apt), routes


def fetch_standing_data(url=ROUTES_TAR):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "warwatch"}), timeout=300) as r:
        return read_standing_data(io.BytesIO(r.read()))


def _alt(p):
    a = p[3]
    return 0 if a == "ground" else a if isinstance(a, (int, float)) else None


def _call(p):
    d = p[8] if len(p) > 8 else None
    return d["flight"].strip() if isinstance(d, dict) and d.get("flight") else ""


def legs(trace, airports, t0=0.0):
    """One aircraft's day of trace points -> legs: dict(dep, arr, t0, t1, call, hold). dep or arr is None when unseen."""
    out, cur, prev = [], None, None

    def low_airport(p):
        alt = _alt(p)
        return airports.nearest(p[1], p[2], NEAR_LOW_KM) if alt is not None and alt < LOW_FT else None

    def finish(arr):
        pts = cur["pts"]
        if pts[-1][0] - pts[0][0] < MIN_AIR_S or len(pts) < 5:
            return
        calls, cats = {}, {}
        for q in pts:
            c = _call(q)
            if c:
                calls[c] = calls.get(c, 0) + 1
            d = q[8] if len(q) > 8 else None
            if isinstance(d, dict) and d.get("category"):
                cats[d["category"]] = cats.get(d["category"], 0) + 1
        out.append({"dep": cur["dep"], "arr": arr, "t0": t0 + pts[0][0], "t1": t0 + pts[-1][0],
                    "call": max(calls, key=calls.get) if calls else "", "cat": max(cats, key=cats.get) if cats else "",
                    "hold": _holding(pts, airports, arr), "gap": cur["gap"], "path": [(q[1], q[2], _alt(q)) for q in pts[::4]] + [(pts[-1][1], pts[-1][2], _alt(pts[-1]))]})

    for p in trace:
        if p[1] is None or p[2] is None:
            continue
        gap = prev is not None and p[0] - prev[0] > GAP_S
        c1 = _call(p)
        if cur is not None and cur["call"] and c1 and c1 != cur["call"]:
            finish(None)       # a new flight number: the aircraft landed somewhere we did not see
            cur = None
        if cur is not None and gap:
            landed = low_airport(prev)
            if landed or p[0] - prev[0] > MAX_GAP_S:
                finish(landed)
                cur = None
            else:
                cur["gap"] = max(cur["gap"], p[0] - prev[0])
        if p[3] == "ground":
            if cur is not None:
                finish(airports.nearest(p[1], p[2], NEAR_GROUND_KM))
                cur = None
        else:
            if cur is None:
                if prev is not None and prev[3] == "ground" and not gap:
                    dep = airports.nearest(prev[1], prev[2], NEAR_GROUND_KM)
                else:
                    dep = low_airport(p)
                cur = {"dep": dep, "pts": [], "call": "", "gap": 0}
            elif cur["pts"]:
                cur["gap"] = max(cur["gap"], p[0] - cur["pts"][-1][0])
            cur["pts"].append(p)
            cur["call"] = c1 or cur["call"]
        prev = p
    if cur is not None:
        finish(low_airport(prev))
    return out


def _holding(pts, airports, arr):
    """Degrees of turning within HOLD_KM of the landing airport below HOLD_FT."""
    if not arr:
        return 0.0
    _, _, la, lo = airports.info[arr]
    turn, prev = 0.0, None
    for p in pts:
        alt = _alt(p)
        if p[5] is None or alt is None or alt > HOLD_FT or km(p[1], p[2], la, lo) > HOLD_KM:
            prev = None
            continue
        if prev is not None:
            turn += abs((p[5] - prev + 180) % 360 - 180)
        prev = p[5]
    return turn


def airline(leg, typ=""):
    """An airline flight: an ICAO airline callsign (three letters, then a digit) on an airliner. The emitter category says
    airliner (A2 small to A5 heavy) for most; when it is missing or 'no information' (A0), the type designator decides.
    Flight schools and helicopter operators also use airline callsigns, which is why the aircraft is checked too."""
    call = leg["call"]
    if len(call) < 4 or not call[:3].isalpha() or not call[3].isdigit():
        return False
    cat = leg.get("cat") or ""
    if cat in ("A2", "A3", "A4", "A5"):
        return True
    return cat in ("", "A0") and bool(AIRLINER.match(typ or ""))


def judge(leg, routes, airports):
    """-> 'diversion', 'turnback', 'normal' or None (cannot be judged: take-off or landing unseen, or a route that cannot be trusted).
    A diversion needs the flight to have come down below 20,000 ft within 150 km of the airport its route goes to, then landed at
    least 50 km away: route tables go stale (charters, cargo and reused flight numbers), and a flight that never started its
    descent into the planned airport may never have been going there. Flights turned away far out (a closure announced en route)
    are missed by this rule; they show in the departures and turnbacks instead."""
    dep, arr, call = leg["dep"], leg["arr"], leg["call"]
    if not dep or not arr:
        return None
    r = routes.get(call)
    if dep == arr:
        # Out and back with a landing elsewhere looks the same when coverage drops, so a turnback needs the whole leg in view.
        if not TURNBACK_S <= leg["t1"] - leg["t0"] <= TURNBACK_MAX_S or leg["gap"] > SEEN_GAP_S or \
                (r and dep in r and r.index(dep) + 1 < len(r) and r[r.index(dep) + 1] == dep):
            return None
        return "turnback"
    if not r or dep not in r or r.index(dep) == len(r) - 1:
        return "normal"
    planned = r[r.index(dep) + 1]
    if arr in r or planned not in airports.info:
        return "normal"
    _, _, pla, plo = airports.info[planned]
    _, _, ala, alo = airports.info[arr]
    near = [a for la, lo, a in leg["path"] if a is not None and km(la, lo, pla, plo) <= APPROACH_KM]
    if km(ala, alo, pla, plo) < DIVERT_KM or not near or min(near) > APPROACH_FT:
        return None
    return "diversion"


class Day:
    """Accumulates one UTC day of traces into per-theatre counts, per-airport rows and a list of diversions."""
    def __init__(self, airports, routes):
        self.ap, self.routes = airports, routes
        self.apt = {}          # icao -> counters
        self.events = []       # diversions and turnbacks touching a theatre airport
        self.th = {}           # (theatre, name) -> count
        self.legs = 0          # airline legs touching a theatre airport

    def _a(self, icao):
        return self.apt.setdefault(icao, {"dep": 0, "arr": 0, "div_away": 0, "div_in": 0, "turnback": 0, "hold": 0, "bizjet_dep": 0, "bizjet_out": 0})

    def _t(self, th, name, n=1):
        if th:
            self.th[(th, name)] = self.th.get((th, name), 0) + n

    def add(self, header, trace):
        t = header.get("t") or ""
        biz = t in BIZJET
        hidden = int(header.get("dbFlags") or 0) & (4 | 8)
        if int(header.get("dbFlags") or 0) & 1 or not self.ap.touches(trace):
            return    # military aircraft are counted elsewhere
        for lg in legs(trace, self.ap, float(header.get("timestamp") or 0)):
            dep, arr = lg["dep"], lg["arr"]
            tdep, tarr = self.ap.theatre(dep), self.ap.theatre(arr)
            if not tdep and not tarr:
                continue
            if biz and tdep:
                self._a(dep)["bizjet_dep"] += 1
                self._t(tdep, "bizjet_dep")
                if arr and tarr != tdep:
                    self._a(dep)["bizjet_out"] += 1
                    self._t(tdep, "bizjet_out")
            if biz or not airline(lg, t):
                continue
            self.legs += 1
            if tdep:
                self._a(dep)["dep"] += 1
                self._t(tdep, "dep")
            if tarr:
                self._a(arr)["arr"] += 1
            kind = judge(lg, self.routes, self.ap)
            if not kind:
                continue
            if tarr and lg["hold"] >= HOLD_DEG:
                self._a(arr)["hold"] += 1
                self._t(tarr, "hold")
            if kind == "diversion":
                r = self.routes[lg["call"]]
                planned = r[r.index(dep) + 1]
                tpl = self.ap.theatre(planned)
                if tpl:
                    self._a(planned)["div_away"] += 1
                    self._t(tpl, "div")
                if tarr:
                    self._a(arr)["div_in"] += 1
                if (tpl or tarr) and not hidden:
                    self.events.append(self._event(lg, header, "diversion", planned))
            elif kind == "turnback" and tdep:
                self._a(dep)["turnback"] += 1
                self._t(tdep, "turnback")
                if not hidden:
                    self.events.append(self._event(lg, header, "turnback", None))

    def _event(self, lg, header, kind, planned):
        la, lo = self.ap.info[lg["arr"]][2:4]
        return {"t": int(lg["t1"]), "kind": kind, "call": lg["call"], "type": header.get("t") or "", "from": lg["dep"], "planned": planned or "",
                "landed": lg["arr"], "lat": round(la, 4), "lon": round(lo, 4)}

    def airport_rows(self, iso):
        return [[iso, k] + [v[h] for h in AIRPORT_HEAD[2:]] for k, v in sorted(self.apt.items())]

    def event_rows(self, iso):
        return [[iso, str(e["t"]), e["kind"], e["call"], e["type"], e["from"], e["planned"], e["landed"], e["lat"], e["lon"]]
                for e in sorted(self.events, key=lambda e: e["t"])]

    def summary(self):
        tot = {}
        for (_, name), v in self.th.items():
            tot[name] = tot.get(name, 0) + v
        return tot

    def series(self):
        """-> {series id: value} for every theatre with airports: departures, diversions, turnbacks, holding, business jets."""
        out = {}
        for th in sorted(set(THEATRE_ISO.values())):
            for name, sid in (("dep", "flights_dep"), ("div", "flights_div"), ("turnback", "flights_turnback"), ("hold", "flights_hold"),
                              ("bizjet_dep", "bizjet_dep"), ("bizjet_out", "bizjet_out")):
                out[f"{sid}_{th}"] = float(self.th.get((th, name), 0))
        out[DONE] = float(self.legs)
        return out


def write_rows(path, day, rows, header):
    """Rewrites one day's rows in a yearly CSV (date first), keeping every other day."""
    keep = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            keep = [r for r in csv.reader(f) if r and r[0] != day and r[0] != header[0]]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(sorted(keep + rows))


def write_places(path, day):
    """Name, country and position of every theatre airport seen so far, for the map (which never reads the route table)."""
    have = {}
    if os.path.exists(path):
        with open(path, newline="") as f:
            have = {r[0]: r for r in csv.reader(f) if r and r[0] != "icao"}
    for k in day.apt:
        if k in day.ap.info and k not in have:
            name, iso, la, lo = day.ap.info[k]
            have[k] = [k, name, iso, f"{la:.4f}", f"{lo:.4f}"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["icao", "name", "iso", "lat", "lon"])
        w.writerows(v for _, v in sorted(have.items()))


def _rows(folder, prefix, months):
    out = []
    for m in months:
        try:
            with open(os.path.join(folder, f"{prefix}-{m}.csv"), newline="") as f:
                out += [r for r in csv.DictReader(f)]
        except OSError:
            pass
    return out


def map_items(folder, today=None, days=7, base=28):
    """-> (airports, events) for the map from the archive tables: each theatre airport's departures on the newest day against its
    median over the 28 days before, with its diversions, turnbacks, holds and business-jet departures in the last 7 days; and the
    last 7 days' diversions and turnbacks."""
    import datetime as dt
    import statistics
    try:
        with open(os.path.join(folder, "places.csv"), newline="") as f:
            places = {r["icao"]: r for r in csv.DictReader(f)}
    except OSError:
        return [], []
    today = today or dt.datetime.now(dt.timezone.utc).date()
    months = sorted({(today - dt.timedelta(days=i)).isoformat()[:7] for i in range(days + base + 2)})
    rows = _rows(folder, "airports", months)
    if not rows:
        return [], []
    last = max(r["date"] for r in rows)
    d_last = dt.date.fromisoformat(last)
    recent = (d_last - dt.timedelta(days=days - 1)).isoformat()
    first = (d_last - dt.timedelta(days=days + base - 1)).isoformat()
    by = {}
    for r in rows:
        if r["date"] >= first:
            by.setdefault(r["icao"], []).append(r)
    airports = []
    for k, rs in by.items():
        p = places.get(k)
        if not p:
            continue
        th = THEATRE_ISO.get(p["iso"]) or ("ukraine" if k.startswith(RU_WEST) else None)
        if not th:
            continue
        dep = {r["date"]: int(r["dep"]) for r in rs}
        hist = [dep.get((d_last - dt.timedelta(days=i)).isoformat(), 0) for i in range(days, days + base)]
        week = [r for r in rs if r["date"] >= recent]
        tot = {h: sum(int(r[h]) for r in week) for h in ("div_away", "div_in", "turnback", "hold", "bizjet_dep", "bizjet_out")}
        usual = statistics.median(hist) if hist else 0
        if usual < 3 and not any(tot.values()):
            continue
        airports.append({"icao": k, "n": p["name"], "lat": float(p["lat"]), "lon": float(p["lon"]), "th": th, "d": last,
                         "dep": dep.get(last, 0), "usual": usual, **tot})
    events = [{"lat": float(e["lat"]), "lon": float(e["lon"]), "k": e["kind"], "call": e["call"], "type": e["type"], "from": e["from"],
               "planned": e["planned"], "landed": e["landed"], "t": int(e["time"]), "d": e["date"],
               "th": THEATRE_ISO.get((places.get(e["planned"]) or places.get(e["landed"]) or {}).get("iso", ""), "")}
              for e in _rows(folder, "events", months) if e["date"] >= recent]
    return airports, events
