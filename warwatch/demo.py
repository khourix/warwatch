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


HOT = {"logistics", "behavioral", "information"}


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


def extras(name):
    """Synthetic map layers for the demo render: fires of every class (and bases, once basewatch has demo rows). No network."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    def ts(h):
        t = now - dt.timedelta(hours=h)
        return t.strftime("%Y-%m-%d"), t.strftime("%Y-%m-%dT%H:%MZ")
    rows = [  # lat, lon, hours ago, MW, theatre, class, score, reason, site
        (32.75, 51.86, 3, 86, "iran", "anom", 85, "No fire here in 14 years of records; 1.2 km from Isfahan air base, 86 MW at night.", "Isfahan air base"),
        (35.65, 51.32, 5, 410, "iran", "anom", 90, "1.0 km from Shahran fuel depot; 6 hot spots together, 410 MW.", "Shahran fuel depot"),
        (25.93, 49.68, 8, 640, "gulf", "hot", 75, "Much more heat than usual at Abqaiq processing plant: 640 MW against a usual 40 MW.", "Abqaiq processing plant"),
        (14.80, 42.95, 20, 120, "yemen", "anom", 70, "0.8 km from Hodeidah port; 3 hot spots together, 120 MW.", "Hodeidah port"),
        (48.10, 37.70, 2, 35, "ukraine", "unex", 45, "This area rarely burns in October, 35 MW.", ""),
        (47.50, 35.10, 30, 22, "ukraine", "unex", 40, "Not a known industrial site or farm-burning area, 22 MW.", ""),
        (30.40, 47.40, 4, 18, "iraq", "ind", 10, "Gas flare at Rumaila field: this spot burns on 93% of days.", "Rumaila field"),
        (27.48, 52.61, 6, 25, "iran", "ind", 10, "Gas flare at South Pars: this spot burns on 97% of days.", "South Pars"),
        (35.53, 44.36, 9, 30, "iraq", "ind", 10, "Oil and gas plant at Baba Gurgur: this spot burns on 99% of days.", "Baba Gurgur"),
        (36.40, 40.90, 50, 12, "syria", "seas", 15, "This area burns in most years in October (farm and grass fires).", ""),
        (46.90, 33.20, 80, 9, "ukraine", "seas", 15, "This area burns in most years in October (farm and grass fires).", ""),
        (13.40, 41.70, 100, 6, "yemen", "volc", 5, "Volcano: NASA marks this spot as an active volcano.", ""),
        (26.50, 52.80, 12, 40, "iran", "off", 5, "Offshore platform or flare: NASA marks this spot as an offshore heat source.", ""),
    ]
    fires = []
    for la, lo, h, mw, th, c, a, why, site in rows:
        d, t = ts(h)
        fires.append({"lat": la, "lon": lo, "date": d, "ts": t, "frp": float(mw), "th": th, "c": c, "a": a, "why": why, "site": site,
                      "routine": c in ("seas", "ind", "volc", "off"), "daynight": "N" if h % 2 else "D"})
    return {"fires": fires, "bases": demo_bases()}


def demo_bases():
    """Synthetic base states for the demo render (no chips: the page shows "No image yet")."""
    import datetime as dt
    d = lambda k: (dt.date.today() - dt.timedelta(days=k)).isoformat()   # noqa: E731
    rows = [("al_udeid", "Al Udeid Air Base, Qatar", 25.117, 51.315, "air", "US/Qatar", ["iran", "gulf"], "out", -3.4,
             f"Radar shows far fewer bright objects on the aprons than usual on two passes ({d(6)} and {d(1)}). Aircraft may have left."),
            ("nsa_bahrain", "NSA Bahrain and Mina Salman port", 26.205, 50.61, "naval", "US", ["iran", "gulf"], "changed", -2.8,
             f"One radar pass ({d(2)}) differed from usual in the harbour; waiting for the next pass to confirm."),
            ("nevatim", "Nevatim Air Base", 31.208, 35.012, "air", "Israel", ["israel", "iran"], "in", 3.1,
             f"Radar shows far more bright objects on the aprons than usual on two passes ({d(5)} and {d(2)}). Aircraft may have arrived."),
            ("isfahan_8tab", "Isfahan 8th Tactical Air Base", 32.751, 51.861, "air", "Iran", ["iran"], "normal", 0.4, f"In its usual range on the latest radar pass ({d(3)})."),
            ("engels", "Engels-2 Air Base", 51.481, 46.2, "air", "Russia", ["ukraine"], "normal", -0.9, f"In its usual range on the latest radar pass ({d(4)})."),
            ("diego_garcia", "Diego Garcia", -7.313, 72.411, "air+naval", "US/UK", ["iran", "yemen"], "optical", None, "No radar coverage here: optical images only.")]
    return [{"id": i, "n": n, "lat": la, "lon": lo, "k": k, "side": sd, "ths": th, "st": st, "z": z, "last": d(1), "lo": d(3),
             "pts": [round(((j * 7) % 5 - 2) * 0.4, 2) for j in range(28)] + ([z, z] if z is not None else []), "why": why, "note": "", "wy": "", "img": {}}
            for i, n, la, lo, k, sd, th, st, z, why in rows]
