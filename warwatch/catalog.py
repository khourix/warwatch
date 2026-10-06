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


def add(id, label, domain, theatre, kind, lag, why, fetch, direction="up", needs=()):
    SERIES.append(dict(id=id, label=label, domain=domain, theatre=theatre, kind=kind,
                       lag=lag, why=why, fetch=fetch, direction=direction, needs=list(needs)))


def _key(name):
    return os.environ.get(name, "")


# ---- troop kit: boots and armor ---------------------------------------------
add("us_boots_awards", "US boot and footwear contract awards (PSC 8430)", "kit", "global", "monthly", True,
    "DoD data is published ~90 days late: confirms, never leads.", lambda: S.fetch_usaspending(psc=["8430"]))
add("us_footwear_naics", "US footwear manufacturing awards (NAICS 316210)", "kit", "global", "monthly", True,
    "Catches boot orders coded by industry rather than product.", lambda: S.fetch_usaspending(naics=["316210"]))
add("us_armor_awards", "US body armor and protective gear awards (PSC 8470)", "kit", "global", "monthly", True,
    "Companion to boots in troop readiness.", lambda: S.fetch_usaspending(psc=["8470"]))
add("us_kit_tenders", "US boot and armor tenders (SAM.gov, PSC 8430, 8470)", "kit", "global", "monthly", False,
    "Tenders are posted before awards, so this leads the award series.",
    lambda: S.fetch_sam(["8430", "8470"], _key("SAM_API_KEY")), needs=["SAM_API_KEY"])
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
    "monthly", True, "DoD lag ~90 days.", lambda: S.fetch_usaspending(psc=["2310", "2320", "2330"]))
add("eu_vehicle_tenders", "EU 4x4 and special vehicle tenders (TED, CPV 34113000, 34114000)", "vehicles", "global",
    "monthly", False, "Tenders lead awards.", lambda: S.fetch_ted(["34113000", "34114000"]))

# ---- medical: blood and trauma -------------------------------------------------------
add("us_medical_awards", "US medical supply awards (PSC 6510, 6515, 6545)", "medical", "global", "monthly", True,
    "Dressings, equipment, kits. DoD lag ~90 days.", lambda: S.fetch_usaspending(psc=["6510", "6515", "6545"]))
add("us_biologics_naics", "US biological product awards (NAICS 325414: blood derivatives, plasma)", "medical",
    "global", "monthly", True, "Nearest free proxy for blood-product buying.",
    lambda: S.fetch_usaspending(naics=["325414"]))
add("us_medical_tenders", "US medical tenders (SAM.gov, PSC 6510, 6515, 6505)", "medical", "global", "monthly", False,
    "Tenders lead awards.", lambda: S.fetch_sam(["6510", "6515", "6505"], _key("SAM_API_KEY")), needs=["SAM_API_KEY"])
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
    "monthly", True, "Border works also hit this: expect noise.", lambda: S.fetch_usaspending(psc=["5660", "5420"]))
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

# ---- attention: news, pageviews, advisories --------------------------------------------
for th, (sid, q) in C.GDELT.items():
    add(sid, f"News volume: {C.THEATRES[th]} (GDELT)", "attention", th, "daily", False,
        "Fastest signal, also moved by non-military news.", (lambda q=q: S.fetch_gdelt(q)))
for key, arts in C.WIKI.items():
    dom = key if key in C.DOMAINS else "attention"
    th = key if key in C.THEATRES else "global"
    for a in arts:
        add(f"wiki_{a.lower()}", f"Wikipedia readers: {a.replace('_', ' ')}", dom, th, "daily", False,
            "Public curiosity spikes on events and on fear.", (lambda a=a: S.fetch_wiki(a)))
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
