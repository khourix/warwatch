"""The series catalogue: one entry per watched indicator.

Fields: id, label, domain, theatre, kind (monthly|daily), lag (published
late), direction (up|down|both: which way is a warning), why, needs (env var
names), fetch (callable returning [(label, value)]).
"""
import os

import config as C
import sources as S
import store

SERIES = []
DOD = 4   # USAspending: current month plus the 3-month DoD publication delay


def add(id, label, domain, theatre, kind, lag, why, fetch, direction="up", needs=(), drop=None, url=""):
    """drop: newest months to discard before scoring because they are still
    incomplete. Default: 1 (the current partial month) for monthly series."""
    if drop is None:
        drop = 1 if kind == "monthly" else 0
    SERIES.append(dict(id=id, label=label, domain=domain, theatre=theatre, kind=kind, lag=lag, why=why,
                       fetch=fetch, direction=direction, needs=list(needs), drop=drop, url=url))


def _slow(sid, fn):
    """Rate-limited sources run in their own workflow (slow.yml) and cache the
    result; the dashboard run reads the cache so it never waits on them."""
    def go():
        if os.environ.get("WARWATCH_LIVE"):
            return fn()
        pts = store.cache_load(sid)
        if not pts:
            raise RuntimeError("first refresh pending (rate-limited source; slow job fills it)")
        return pts
    return go


def _key(name):
    return os.environ.get(name, "")


# ---- troop kit: boots and armor ---------------------------------------------
add("us_boots_awards", "US boot and footwear contract awards (PSC 8430)", "kit", "global", "monthly", True,
    "DoD data is published ~90 days late: confirms, never leads.", lambda: S.fetch_usaspending(psc=["8430"]), drop=DOD)
add("us_footwear_naics", "US footwear manufacturing awards (NAICS 316210)", "kit", "global", "monthly", True,
    "Catches boot orders coded by industry rather than product.", lambda: S.fetch_usaspending(naics=["316210"]), drop=DOD)
add("us_armor_awards", "US body armor and protective gear awards (PSC 8470)", "kit", "global", "monthly", True,
    "Companion to boots in troop readiness.", lambda: S.fetch_usaspending(psc=["8470"]), drop=DOD)
add("us_kit_tenders", "US boot and armor tenders (SAM.gov, PSC 8430, 8470)", "kit", "global", "monthly", False,
    "Tenders are posted before awards, so this leads the award series.",
    _slow("us_kit_tenders", lambda: S.fetch_sam(["8430", "8470"], _key("SAM_API_KEY"))), needs=["SAM_API_KEY"])
add("eu_kit_tenders", "EU protective footwear tenders (TED, CPV 18830000, 18800000)", "kit", "global", "monthly", False,
    "EU tenders appear within days of publication.", lambda: S.fetch_ted(["18830000", "18800000"]))
for th, lbl in (("ukraine", "Ukraine"), ("mideast", "Middle East")):
    add(f"eu_boots_to_{th}", f"EU footwear exports to {lbl} (HS 6403)", "kit", th, "monthly", True,
        "Eurostat trade is ~2 months late.", (lambda t=th: S.fetch_comext("6403", C.PARTNERS[t]["iso"])))
    add(f"us_boots_to_{th}", f"US footwear exports to {lbl} (HS 640391, 640399)", "kit", th, "monthly", True,
        "Census trade is ~2 months late.",
        (lambda t=th: S.fetch_census(["640391", "640399"], C.PARTNERS[t]["names"], _key("CENSUS_API_KEY"))),
        needs=["CENSUS_API_KEY"])

# ---- vehicles: Toyota-class pickups ----------------------------------------------
for th, lbl in (("ukraine", "Ukraine"), ("mideast", "Middle East"), ("europe_east", "eastern flank")):
    add(f"eu_trucks_to_{th}", f"EU goods-vehicle exports to {lbl} (HS 8704)", "vehicles", th, "monthly", True,
        "HS 8704 holds pickups such as the Hilux; Comext is ~2 months late.",
        (lambda t=th: S.fetch_comext("8704", C.PARTNERS[t]["iso"])))
for th, lbl in (("ukraine", "Ukraine"), ("mideast", "Middle East")):
    add(f"us_pickups_to_{th}", f"US pickup exports to {lbl} (HS 870421, 870431, 870422, 870432)", "vehicles", th,
        "monthly", True, "Census trade is ~2 months late.",
        (lambda t=th: S.fetch_census(["870421", "870431", "870422", "870432"], C.PARTNERS[t]["names"], _key("CENSUS_API_KEY"))),
        needs=["CENSUS_API_KEY"])
add("us_tactical_vehicle_awards", "US truck and tactical vehicle awards (PSC 2310, 2320, 2330)", "vehicles", "global",
    "monthly", True, "DoD lag ~90 days.", lambda: S.fetch_usaspending(psc=["2310", "2320", "2330"]), drop=DOD)
add("eu_vehicle_tenders", "EU 4x4 and special vehicle tenders (TED, CPV 34113000, 34114000)", "vehicles", "global",
    "monthly", False, "Tenders lead awards.", lambda: S.fetch_ted(["34113000", "34114000"]))

# ---- medical: blood and trauma -------------------------------------------------------
add("us_medical_awards", "US medical supply awards (PSC 6510, 6515, 6545)", "medical", "global", "monthly", True,
    "Dressings, equipment, kits. DoD lag ~90 days.", lambda: S.fetch_usaspending(psc=["6510", "6515", "6545"]), drop=DOD)
add("us_biologics_naics", "US biological product awards (NAICS 325414: blood derivatives, plasma)", "medical",
    "global", "monthly", True, "Nearest free proxy for blood-product buying.",
    lambda: S.fetch_usaspending(naics=["325414"]), drop=DOD)
add("us_medical_tenders", "US medical tenders (SAM.gov, PSC 6510, 6515, 6505)", "medical", "global", "monthly", False,
    "Tenders lead awards.", _slow("us_medical_tenders", lambda: S.fetch_sam(["6510", "6515", "6505"], _key("SAM_API_KEY"))), needs=["SAM_API_KEY"])
add("eu_medical_tenders", "EU medical consumable tenders (TED, CPV 33140000, 33141000)", "medical", "global", "monthly",
    False, "Covers blood bags, dressings, hemostatics and tourniquets.",
    lambda: S.fetch_ted(["33140000", "33141000"]))
for th, lbl in (("ukraine", "Ukraine"), ("mideast", "Middle East")):
    add(f"eu_bandages_to_{th}", f"EU dressing and blood-fraction exports to {lbl} (HS 3005, 3002)", "medical", th,
        "monthly", True, "Gauze and bandages (3005) and blood fractions (3002).",
        (lambda t=th: _sum_series([S.fetch_comext("3005", C.PARTNERS[t]["iso"]), S.fetch_comext("3002", C.PARTNERS[t]["iso"])])))


def _sum_series(lst):
    tot = {}
    for s in lst:
        for k, v in s:
            tot[k] = tot.get(k, 0.0) + v
    return sorted(tot.items())


# ---- infrastructure -------------------------------------------------------------------
add("us_fencing_bridging_awards", "US fencing and bridging awards (PSC 5660, 5420)", "infrastructure", "global",
    "monthly", True, "Border works also hit this: expect noise.", lambda: S.fetch_usaspending(psc=["5660", "5420"]), drop=DOD)
add("eu_fencing_tenders", "EU fencing and bridge tenders (TED, CPV 44312000, 45221110)", "infrastructure", "global",
    "monthly", False, "Civil works dominate: low weight.", lambda: S.fetch_ted(["44312000", "45221110"]))

# ---- flows: sea (PortWatch) and air (ADS-B) -------------------------------------------
for frag, th in C.CHOKEPOINTS.items():
    add(f"portwatch_{frag.lower()}", f"Daily ship transits: {frag} (IMF PortWatch)", "flows", th, "daily", False,
        "A fall in transits signals disruption; data posts weekly.",
        (lambda f=frag: S.fetch_portwatch(f)), direction="down")


def _adsb(theatre, which):
    def go():
        tot, lift = S.adsb_counts(S.fetch_adsb(), C.BOXES[theatre])
        sid = f"adsb_{theatre}_{which}"
        store.append(sid, tot if which == "mil" else lift)
        return store.daily(sid)
    return go


for th in C.BOXES:
    add(f"adsb_{th}_mil", f"Military aircraft visible, {C.THEATRES[th]} (adsb.lol)", "flows", th, "daily", False,
        "ADS-B only: military flights with transponders off are invisible. History builds from first run.",
        _adsb(th, "mil"), direction="both")
    add(f"adsb_{th}_lift", f"Airlift and tanker aircraft visible, {C.THEATRES[th]}", "flows", th, "daily", False,
        "Transports and tankers surge before operations.", _adsb(th, "lift"))

# ---- airspace and navigation: snapshot signals, history builds from the first run -------
import extras  # noqa: E402


def _snap(sid, fn):
    def go():
        v = fn()
        if v is not None:
            store.append(sid, v)
        return store.daily(sid)
    return go


def _gnss(theatre):
    def f():
        n, bad = extras.hub_stats(theatre)
        return 100.0 * bad / n if n >= 8 else None   # too few aircraft to read a percentage
    return f


for th in C.HUBS:
    add(f"gnss_{th}", f"Aircraft reporting degraded GPS, {C.THEATRES[th]} (% of traffic)", "airspace", th, "daily", False,
        "Jamming shows up as poor navigation accuracy (NACp below 8) in airliners' own broadcasts, "
        "often before a strike or deployment. Snapshots start now.",
        _snap(f"gnss_{th}", _gnss(th)), url="https://api.adsb.lol/")
    add(f"civil_{th}", f"Airliners in the air near the theatre, {C.THEATRES[th]}", "airspace", th, "daily", False,
        "A fall means airspace is being closed or avoided. Snapshots start now.",
        _snap(f"civil_{th}", lambda t=th: float(extras.hub_stats(t)[0]) or None), direction="down", url="https://api.adsb.lol/")
    add(f"nga_{th}", f"New naval and air hazard warnings, last 30 days, {C.THEATRES[th]} (NGA)", "airspace", th, "daily",
        False, "Missile firing, exercises, mines and GPS interference notices to mariners and pilots; "
        "exercises are announced before they happen.",
        _snap(f"nga_{th}", lambda t=th: extras.nga_recent(t)), url="https://msi.nga.mil/")

def _news(th):
    sid = f"news_{th}"

    def go():
        if os.environ.get("WARWATCH_LIVE"):
            return S.fetch_gnews(sid, C.GNEWS[th], days=150)
        pts = store.cache_load(sid)
        if not pts:
            raise RuntimeError("first refresh pending (news history fills from the news job)")
        return pts
    return go


for th in C.GNEWS:
    add(f"news_{th}", f"Headlines with warning language per day, {C.THEATRES[th]} (Google News)", "attention", th,
        "daily", False, "Counts headlines pairing the theatre with mobilization, evacuation, airspace-closure or "
        "troop-build-up wording. Fast, free and backfilled from the news archive; it also reacts to events, so it is "
        "read together with the other groups.", _news(th), url="https://news.google.com/")
add("easa_czib_updates", "Airspace risk bulletins revised in last 30 days (EASA)", "airspace", "global", "daily", False,
    "EASA revises its conflict-zone bulletins when it sees rising danger to airliners. Snapshots start now.",
    _snap("easa_czib_updates", lambda: extras.czib_recent()), url="https://www.easa.europa.eu/en/domains/air-operations/czibs")
for th, slugs in C.FCDO.items():
    add(f"fcdo_{th}", f"UK travel-advice updates: {C.THEATRES[th]}", "attention", th, "daily", False,
        "A cluster of advisory rewrites precedes evacuations.", (lambda s=slugs: S.fetch_fcdo(s)))


def _state(theatre):
    def go():
        v = S.state_levels(S.fetch_state(), C.STATE_ISO[theatre])
        sid = f"state_{theatre}"
        store.append(sid, v)
        return store.daily(sid)
    return go


for th in C.STATE_ISO:
    add(f"state_{th}", f"US advisory level sum: {C.THEATRES[th]}", "attention", th, "daily", False,
        "Any step change in a flat series is flagged. History builds from first run.", _state(th))

# ---- markets ---------------------------------------------------------------------------
add("brent", "Brent crude, USD (FRED)", "markets", "mideast", "daily", False, "Oil prices react to Gulf risk.",
    lambda: S.fetch_fred("DCOILBRENTEU", _key("FRED_API_KEY")), needs=["FRED_API_KEY"])
add("vix", "VIX (FRED)", "markets", "global", "daily", False, "Equity fear gauge.",
    lambda: S.fetch_fred("VIXCLS", _key("FRED_API_KEY")), needs=["FRED_API_KEY"])


# ---- added after reading AJ Signal (ajsignalnotnoise.substack.com) ----------------
# The author's public posts name: pork-free MRE rations and ration ceilings, hot-weather
# boots, blood-bank drawdowns, Toyota-class pickup shipments, diesel and jet-fuel stress,
# and Gulf shipping chokepoints. Boots, pickups and chokepoints were already covered.
add("us_rations_awards", "US composite food package (MRE ration) awards (PSC 8970)", "kit", "global", "monthly", True,
    "Field rations are bought ahead of ground operations; DoD data is ~90 days late, so it confirms.",
    lambda: S.fetch_usaspending(psc=["8970"]), drop=DOD, url="https://www.usaspending.gov/")
add("us_shelter_awards", "US tents, tarpaulins and shelter awards (PSC 8340)", "kit", "global", "monthly", True,
    "Forward-deployed forces need shelter; confirms rather than leads.",
    lambda: S.fetch_usaspending(psc=["8340"]), drop=DOD, url="https://www.usaspending.gov/")
add("us_individual_equipment_awards", "US individual equipment awards (PSC 8465)", "kit", "global", "monthly", True,
    "Packs, helmets-adjacent kit and field gear; confirms rather than leads.",
    lambda: S.fetch_usaspending(psc=["8465"]), drop=DOD, url="https://www.usaspending.gov/")
add("us_blood_bank_naics", "US blood and organ bank contract awards (NAICS 621991)", "medical", "global", "monthly", True,
    "Blood-bank contracting is one of the author's three headline indicators; confirms rather than leads.",
    lambda: S.fetch_usaspending(naics=["621991"]), drop=DOD, url="https://www.usaspending.gov/")
add("diesel_nyh", "Diesel, New York Harbor, USD per gallon (FRED)", "markets", "global", "daily", False,
    "Diesel stress shows up before crude when refineries and shipping lanes are hit.",
    lambda: S.fetch_fred("DDFUELNYH", _key("FRED_API_KEY")), needs=["FRED_API_KEY"],
    url="https://fred.stlouisfed.org/series/DDFUELNYH")
add("jet_fuel_gulf", "Jet fuel, US Gulf Coast, USD per gallon (FRED)", "markets", "global", "daily", False,
    "Military and airlift demand moves jet fuel before civil demand does.",
    lambda: S.fetch_fred("DJFUELUSGULF", _key("FRED_API_KEY")), needs=["FRED_API_KEY"],
    url="https://fred.stlouisfed.org/series/DJFUELUSGULF")
