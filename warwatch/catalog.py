"""The series catalogue: one entry per watched indicator.

Fields: id, label, domain (one of five groups), sub (short sub-category chip),
theatre (ukraine, europe_east, iran, yemen, israel or global), kind
(monthly|daily), lag (published late), direction (up|down|both: which way is a
warning), why, needs (env var names), fetch (callable returning [(label, value)]).

A theatre is scored from its own series only; global series are scored under
'global' so every theatre shows indicators that belong to it.
"""
import os

import config as C
import extras
import sources as S
import store

SERIES = []
DOD = 4   # USAspending: current month plus the 3-month DoD publication delay
TH = {t: v["name"] for t, v in C.THEATRES.items()}


# The noise floor each family is scored with (stats.noise_floor): small counts and small shares, where a
# near-empty history otherwise reads one aircraft or a tenth of a percent as a maximal change.
SCALE = (("adsb_", "count"), ("package_", "count"), ("civil_", "count"), ("firms_", "count"), ("gdelt_", "count"),
         ("news_", "count"), ("ports_", "count"), ("portwatch_", "count"), ("fcdo_", "count"),
         ("nga_", "window"), ("notam_", "window"), ("msa_", "window"), ("jcg_", "window"), ("ukmto_", "window"),
         ("czib_", "window"), ("tzeva_", "window"), ("uaair_", "window"),
         ("gpsjam_", ("share", 1.0)), ("gnss_", ("share", 1.0)),        # percent
         ("gdeltshare_", ("share", 10.0)),                               # per 1,000 events
         ("ooni_", ("share", 0.01)))                                     # a fraction


def scale_for(sid):
    return next((v for k, v in SCALE if sid.startswith(k)), None)


def add(id, label, domain, theatre, kind, lag, why, fetch, direction="up", needs=(), drop=None, url="", sub=""):
    """drop: newest months discarded before scoring because still incomplete
    (default 1 for monthly series)."""
    if drop is None:
        drop = 1 if kind == "monthly" else 0
    SERIES.append(dict(id=id, label=label, domain=domain, theatre=theatre, kind=kind, lag=lag, why=why,
                       fetch=fetch, direction=direction, needs=list(needs), drop=drop, url=url, sub=sub, every=None, scored=True,
                       scale=scale_for(id) if kind == "daily" else None))


def _slow(sid, fn):
    """Rate-limited sources run in slow.yml and cache; the build reads the cache."""
    def go():
        if os.environ.get("WARWATCH_LIVE"):
            return fn()
        pts = store.cache_load(sid)
        if not pts:
            raise RuntimeError("first refresh pending (rate-limited source; slow job fills it)")
        return pts
    return go


def _snap(sid, fn):
    """Sources that only expose 'now': append each run to history, score once enough days exist."""
    def go():
        v = fn()
        if v is not None:
            store.append(sid, v)
        return store.daily(sid)
    return go


def _key(name):
    return os.environ.get(name, "")


def _sum(lst):
    tot = {}
    for s in lst:
        for k, v in s:
            tot[k] = tot.get(k, 0.0) + v
    return sorted(tot.items())


# ============ GLOBAL: what the US and EU buy and stock ahead of a war (published late: confirms) ============
USA = "https://www.usaspending.gov/"
for sid, label, why, kw, sub in (
    ("us_boots_awards", "US boot and footwear contract awards (PSC 8430)",
     "Combat boots are bought before troops deploy. DoD data is ~90 days late, so this confirms rather than leads.",
     dict(psc=["8430"]), "Procurement"),
    ("us_footwear_naics", "US footwear manufacturing awards (NAICS 316210)", "Catches boot orders coded by industry.",
     dict(naics=["316210"]), "Procurement"),
    ("us_armor_awards", "US body armor and protective gear awards (PSC 8470)", "Armor plates: companion to boots in readiness.",
     dict(psc=["8470"]), "Procurement"),
    ("us_rations_awards", "US composite food package (MRE ration) awards (PSC 8970)", "Field rations are bought ahead of ground operations.",
     dict(psc=["8970"]), "Procurement"),
    ("us_shelter_awards", "US tents, tarpaulins and shelter awards (PSC 8340)", "Forward-deployed forces need shelter.",
     dict(psc=["8340"]), "Procurement"),
    ("us_individual_equipment_awards", "US individual equipment awards (PSC 8465)", "Packs, field gear and soldier kit.",
     dict(psc=["8465"]), "Procurement"),
    ("us_tactical_vehicle_awards", "US truck and tactical vehicle awards (PSC 2310, 2320, 2330)", "Light and heavy military trucks.",
     dict(psc=["2310", "2320", "2330"]), "Procurement"),
    ("us_lubricant_awards", "US lubricants, oils and fluids awards (PSC 9150)",
     "Bulk lubricants and fluids mean preparation for sustained vehicle uptime.", dict(psc=["9150"]), "Fuel and engines"),
    ("us_fuel_awards", "US fuel and propellant awards (PSC 9130, 9140)", "Fuel stocking ahead of sustained operations.",
     dict(psc=["9130", "9140"]), "Fuel and engines"),
    ("us_medical_awards", "US medical supply awards (PSC 6510, 6515, 6545)", "Dressings, trauma equipment and kits.",
     dict(psc=["6510", "6515", "6545"]), "Medical"),
    ("us_biologics_naics", "US biological product awards (NAICS 325414: blood derivatives, plasma)",
     "Nearest free proxy for blood-product buying.", dict(naics=["325414"]), "Medical"),
    ("us_blood_bank_naics", "US blood and organ bank contract awards (NAICS 621991)",
     "Blood-bank contracting is a headline indicator in the AJ Signal framework.", dict(naics=["621991"]), "Medical"),
    ("us_fencing_bridging_awards", "US fencing and bridging awards (PSC 5660, 5420)",
     "Tactical bridging and barrier material. Border works add noise.", dict(psc=["5660", "5420"]), "Engineering"),
):
    add(sid, label, "logistics", "global", "monthly", True, why, (lambda kw=kw: S.fetch_usaspending(**kw)),
        drop=DOD, url=USA, sub=sub)
add("us_kit_tenders", "US boot and armor tenders posted per day (SAM.gov, PSC 8430, 8470)", "logistics", "global", "daily", False,
    "Tenders are posted before awards, so this leads the award series.",
    _slow("us_kit_tenders", lambda: S.fetch_sam(["8430", "8470"], _key("SAM_API_KEY"))), needs=["SAM_API_KEY"],
    url="https://sam.gov/", sub="Procurement")
add("us_medical_tenders", "US medical tenders posted per day (SAM.gov, PSC 6510, 6515, 6505)", "logistics", "global", "daily", False,
    "Tenders lead awards.", _slow("us_medical_tenders", lambda: S.fetch_sam(["6510", "6515", "6505"], _key("SAM_API_KEY"))),
    needs=["SAM_API_KEY"], url="https://sam.gov/", sub="Medical")
TED = "https://ted.europa.eu/"
for sid, label, why, cpv, sub in (
    ("eu_kit_tenders", "EU protective footwear tenders (TED, CPV 18830000, 18800000)", "EU tenders appear within days of publication.",
     ["18830000", "18800000"], "Procurement"),
    ("eu_vehicle_tenders", "EU 4x4 and special vehicle tenders (TED, CPV 34113000, 34114000)", "Tenders lead awards.",
     ["34113000", "34114000"], "Procurement"),
    ("eu_medical_tenders", "EU medical consumable tenders (TED, CPV 33140000, 33141000)",
     "Blood bags, dressings, hemostatics and tourniquets.", ["33140000", "33141000"], "Medical"),
    ("eu_fencing_tenders", "EU fencing and bridge tenders (TED, CPV 44312000, 45221110)", "Civil works dominate: low weight.",
     ["44312000", "45221110"], "Engineering"),
):
    add(sid, label, "logistics", "global", "monthly", False, why, (lambda c=cpv: S.fetch_ted(c)), url=TED, sub=sub)

FRED = "https://fred.stlouisfed.org/series/"
add("vix", "VIX equity fear gauge (Cboe)", "financial", "global", "daily", False, "Equity markets price in escalation risk.",
    lambda: S.fetch_cboe_vix(), url="https://www.cboe.com/tradable_products/vix/vix_historical_data/", sub="Markets")
add("diesel_nyh", "Diesel, New York Harbor, USD per gallon (FRED)", "financial", "global", "daily", False,
    "Diesel stress shows up before crude when refineries and shipping lanes are hit.",
    lambda: S.fetch_fred("DDFUELNYH", _key("FRED_API_KEY")), needs=["FRED_API_KEY"], url=FRED + "DDFUELNYH", sub="Fuel")
add("jet_fuel_gulf", "Jet fuel, US Gulf Coast, USD per gallon (FRED)", "financial", "global", "daily", False,
    "Military and airlift demand moves jet fuel before civil demand does.",
    lambda: S.fetch_fred("DJFUELUSGULF", _key("FRED_API_KEY")), needs=["FRED_API_KEY"], url=FRED + "DJFUELUSGULF", sub="Fuel")
for sym, name in (("ITA", "US aerospace and defence ETF (ITA)"), ("LMT", "Lockheed Martin"), ("RTX", "RTX (Raytheon)"),
                  ("NOC", "Northrop Grumman")):
    add(f"def_{sym.lower()}", f"{name} share price (Yahoo Finance)", "financial", "global", "daily", False,
        "Defence stocks rally on expected demand; a sharp surge is a strong signal in conflict models.",
        (lambda s=sym: S.fetch_market(s)),
        url="https://finance.yahoo.com/", sub="Defence stocks")
# Finer purchase codes the OSINT community watches: munitions, armour, missiles, charter airlift, sealift, site works
for sid, label, why, kw, sub in (
    ("us_ammo_awards", "US ammunition awards (PSC 1305, 1310, 1315, 1320, 1325, 1330, 1340)",
     "Ammunition buying leads sustained fighting: stocks are replenished ahead of use. Awards publish ~90 days late, so this confirms rather than leads.",
     dict(psc=["1305", "1310", "1315", "1320", "1325", "1330", "1340"]), "Munitions"),
    ("us_ammo_naics", "US ammunition manufacturing awards (NAICS 332992, 332993, 332994)", "Industry-coded munition orders, which PSC filters miss.",
     dict(naics=["332992", "332993", "332994"]), "Munitions"),
    ("us_missile_awards", "US guided missile and rocket awards (PSC 1410, 1420, 1425, 1427)", "Missile replenishment follows heavy interceptor and strike use.",
     dict(psc=["1410", "1420", "1425", "1427"]), "Munitions"),
    ("us_armored_naics", "US armored vehicle manufacturing awards (NAICS 336992)", "Ground-force vehicles for deployment or transfer.",
     dict(naics=["336992"]), "Procurement"),
    ("us_air_charter_naics", "US non-scheduled air charter freight awards (NAICS 481212)",
     "Commercial charter freight chartered by DoD is a surge-airlift signal.", dict(naics=["481212"]), "Airlift"),
    ("us_sealift_naics", "US deep-sea freight awards (NAICS 483111, 483113)", "Sealift charters move heavy equipment ahead of a deployment.",
     dict(naics=["483111", "483113"]), "Sealift"),
    ("us_site_works_naics", "US site preparation and heavy civil works awards (NAICS 237990, 238910, 237310)",
     "Runways, ramps and revetments at forward bases are built before forces arrive.", dict(naics=["237990", "238910", "237310"]), "Engineering"),
    ("us_chem_protective_awards", "US chemical and biological protective gear awards (PSC 4240, 4220)",
     "Masks, suits and decontamination kit are bought when CBRN risk is in the plan.", dict(psc=["4240", "4220"]), "Medical"),
    ("us_aircraft_parts_awards", "US aircraft engine and spare-part awards (PSC 2840, 2915, 1560)",
     "Spares buying ahead of high operating tempo.", dict(psc=["2840", "2915", "1560"]), "Fuel and engines"),
):
    add(sid, label, "logistics", "global", "monthly", True, why, (lambda kw=kw: S.fetch_usaspending(**kw)), drop=DOD, url=USA, sub=sub)

# DoD spending by place of performance: where the money lands moves before the forces do
POP = {"europe_east": ("POL", "LTU", "LVA", "EST", "ROU"), "israel": ("ISR",), "iran": ("KWT", "QAT", "BHR", "ARE", "SAU", "JOR", "OMN", "IRQ"),
       "yemen": ("DJI", "SAU", "OMN"), "ukraine": ("UKR", "MDA", "ROU"),
       "taiwan": ("TWN", "JPN"), "korea": ("KOR",), "scs": ("PHL", "SGP", "THA"), "venezuela": ("COL", "PAN", "HND", "CUB", "GUY")}
BUILD = ["236220", "237990", "237310", "238910", "236210", "238120"]
for th, ccs in POP.items():
    add(f"dod_pop_{th}", f"DoD obligations performed in {TH[th]} region ({', '.join(ccs)})", "logistics", th, "monthly", True,
        "Contract money performed in the host countries rises when forces and supplies are being positioned there. DoD data is ~90 days late.",
        (lambda c=ccs: S.fetch_usaspending(pop=list(c), dod=True)), drop=DOD, url=USA, sub="Procurement")
    add(f"dod_build_{th}", f"DoD construction and site-works obligations in {TH[th]} region", "logistics", th, "monthly", True,
        "Construction at host-nation bases (aprons, ammunition storage, barracks) precedes a surge; it is the slowest to hide.",
        (lambda c=ccs: S.fetch_usaspending(naics=BUILD, pop=list(c), dod=True)), drop=DOD, url=USA, sub="Engineering")

add("pizza_index", "Pentagon pizza index (PizzINT, 0-100)", "behavioral", "global", "daily", False,
    "Crisis staffing shows up as late-night food-delivery demand around the Pentagon. Weak signal from a third-party scrape of Google popular times; snapshots start now.",
    _snap("pizza_index", lambda: extras.pizza_now()[0]), url="https://www.pizzint.watch/", sub="Behaviour")
add("czib_global", "Airspace risk bulletins revised in last 30 days, worldwide (EASA)", "geospatial", "global", "daily", False,
    "EASA revises its conflict-zone bulletins when it sees rising danger to airliners. Snapshots start now.",
    _snap("czib_global", lambda: extras.czib_recent()),
    url="https://www.easa.europa.eu/en/domains/air-operations/czibs", sub="Airspace")

# ============ PER THEATRE ============
EUR = "https://ec.europa.eu/eurostat/comext/newxtweb/"
CEN = "https://www.census.gov/foreign-trade/index.html"
for th in ("ukraine", "europe_east", "israel", "iran"):
    nm = TH[th]
    add(f"eu_trucks_to_{th}", f"EU goods-vehicle exports to {nm} (HS 8704)", "logistics", th, "monthly", True,
        "HS 8704 holds pickups such as the Hilux; Comext is ~2 months late.",
        (lambda t=th: S.fetch_comext("8704", C.PARTNERS[t]["iso"])), url=EUR, sub="Trade")
    add(f"eu_medical_to_{th}", f"EU dressing and blood-fraction exports to {nm} (HS 3005, 3002)", "logistics", th,
        "monthly", True, "Gauze and bandages (3005) and blood fractions (3002).",
        (lambda t=th: _sum([S.fetch_comext("3005", C.PARTNERS[t]["iso"]), S.fetch_comext("3002", C.PARTNERS[t]["iso"])])),
        url=EUR, sub="Trade")
for th in ("ukraine", "europe_east", "israel"):
    nm = TH[th]
    add(f"eu_boots_to_{th}", f"EU footwear exports to {nm} (HS 6403)", "logistics", th, "monthly", True,
        "Eurostat trade is ~2 months late.", (lambda t=th: S.fetch_comext("6403", C.PARTNERS[t]["iso"])), url=EUR, sub="Trade")
    add(f"us_boots_to_{th}", f"US footwear exports to {nm} (HS 640391, 640399)", "logistics", th, "monthly", True,
        "Census trade is ~2 months late.",
        (lambda t=th: S.fetch_census(["640391", "640399"], C.PARTNERS[t]["names"], _key("CENSUS_API_KEY"))),
        needs=["CENSUS_API_KEY"], url=CEN, sub="Trade")
    add(f"us_pickups_to_{th}", f"US pickup exports to {nm} (HS 870421, 870431, 870422, 870432)", "logistics", th,
        "monthly", True, "Census trade is ~2 months late.",
        (lambda t=th: S.fetch_census(["870421", "870431", "870422", "870432"], C.PARTNERS[t]["names"], _key("CENSUS_API_KEY"))),
        needs=["CENSUS_API_KEY"], url=CEN, sub="Trade")

ADS = "https://adsb.lol/"


def _adsb(th, cls):
    def go():
        v = S.adsb_classes(S.fetch_adsb(), C.BOXES[th])[cls]
        sid = f"adsb_{th}_{cls}"
        store.append(sid, v)   # the instant snapshots keep accumulating in history/, but the score reads the archive series
        pts = store.backfill(sid)
        if not pts:
            raise RuntimeError("no archive history yet (the adsb-daily job fills it)")
        return pts
    return go


ADSB_TH = [t for t in C.BOXES if t not in ("sudan", "drc")]   # too little military traffic there to score
for th in ADSB_TH:
    nm = TH[th]
    for cls, label, why in (
        ("mil", "Military aircraft visible over", "Transponding military flights only: aircraft with transponders off are invisible. Counts the different aircraft seen in the box each UTC day, from the adsb.lol daily archives (history from March 2024, one day behind)."),
        ("lift", "Airlift aircraft over", "Transports surge before operations; an 'empty' return leg means cargo was delivered."),
        ("tanker", "Aerial tankers over", "Tankers appearing with fighters and AWACS mean strike packaging, not routine training."),
        ("isr", "Surveillance and AWACS aircraft over", "Reconnaissance and early-warning aircraft orbit before and during operations."),
        ("fighter", "Fighter aircraft over", "Combat aircraft on transponders are usually deployments or air policing; a rise is worth reading."),
    ):
        add(f"adsb_{th}_{cls}", f"{label} {nm} (adsb.lol)", "geospatial", th, "daily", False, why, _adsb(th, cls), url=ADS, sub="Air")


def _gnss(theatre):
    def f():
        n, bad = extras.hub_stats(theatre)
        return 100.0 * bad / n if n >= 8 else None   # too few aircraft to read a percentage
    return f


NGA = "https://msi.nga.mil/"
# Too little civil traffic is visible in public ADS-B near these hubs (Yemen's airspace is nearly empty, Venezuela's is thin),
# so the ADS-B GPS and airliner counts cannot be measured there; GPSJam, ports and Radar cover those theatres instead.
NO_GNSS = {"yemen", "venezuela"}
NO_CIVIL = {"yemen"}
for th in C.HUBS:
    nm = TH[th]
    if th not in NO_GNSS:
        add(f"gnss_{th}", f"Aircraft reporting degraded GPS near {nm} (% of traffic)", "geospatial", th, "daily", False,
            "Jamming shows up as poor navigation accuracy (NACp below 8) in airliners' own broadcasts, often before a strike or deployment. Snapshots start now.",
            _snap(f"gnss_{th}", _gnss(th)), url=ADS, sub="Navigation")
    if th not in NO_CIVIL:
        add(f"civil_{th}", f"Airliners in the air near {nm}", "geospatial", th, "daily", False,
            "A fall means airspace is being closed or avoided. Snapshots start now.",
            _snap(f"civil_{th}", lambda t=th: float(extras.hub_stats(t)[0]) or None), direction="down", url=ADS, sub="Airspace")
    add(f"nga_{th}", f"New naval and air hazard warnings, last 30 days, {nm} (US NGA)", "geospatial", th, "daily", False,
        "Missile firing, exercises, mines, drones and GPS-interference notices to mariners and pilots; exercises are announced before they happen. From NGA's current feed, kept from 1 August 2026 and counted from 31 August.",
        (lambda t=th: extras.nga_series(t)), url=NGA, sub="Warnings")
    add(f"czib_{th}", f"EASA airspace bulletins revised in last 30 days, {nm}", "geospatial", th, "daily", False,
        "EASA revises conflict-zone bulletins when it sees rising danger to airliners. Snapshots start now.",
        _snap(f"czib_{th}", lambda t=th: extras.czib_recent(box=C.BOXES[t])),
        url="https://www.easa.europa.eu/en/domains/air-operations/czibs", sub="Airspace")
for frag, th in C.CHOKEPOINTS.items():
    add(f"portwatch_{frag.lower().replace(' ', '_')}", f"Daily ship transits: {C.CHOKE_XY[frag][2]} (IMF PortWatch)", "geospatial", th, "daily", False,
        "A fall in transits signals disruption or avoidance; data posts weekly.",
        (lambda f=frag: S.fetch_portwatch(f)), direction="down", url="https://portwatch.imf.org/", sub="Sea")

IODA = {"iran": "IR", "ukraine": "UA", "israel": "IL", "yemen": "YE", "europe_east": "PL", "taiwan": "TW", "scs": "PH", "korea": "KR",
        "southasia": "IN", "libya": "LY", "sudan": "SD", "drc": "CD", "venezuela": "VE"}
for th, cc in IODA.items():
    u = f"https://ioda.inetintel.cc.gatech.edu/country/{cc}"
    add(f"ioda_bgp_{th}", f"Internet reachability (routed networks), {cc} (IODA)", "geospatial", th, "daily", False,
        "National blackouts show as a sharp fall in routed networks within minutes; Iran has cut the internet before operations.",
        (lambda c=cc: S.fetch_ioda(c, "bgp")), direction="down", url=u, sub="Network")
    add(f"ioda_ping_{th}", f"Internet reachability (probed networks), {cc} (IODA)", "geospatial", th, "daily", False,
        "Active probing sees disconnections routing data misses, such as power-grid or access-network failure.",
        (lambda c=cc: S.fetch_ioda(c, "ping-slash24")), direction="down", url=u, sub="Network")

for th, cc in IODA.items():
    add(f"ooni_{th}", f"Web-test interference rate, {cc} (OONI)", "information", th, "daily", False,
        "Governments tighten censorship and throttle sites before and during operations; OONI volunteers measure it daily.",
        (lambda c=cc: S.fetch_ooni(c)), url=f"https://explorer.ooni.org/country/{cc}", sub="Censorship")

for th, cc in IODA.items():
    for slug, path, lab, dirn, dom, why in (
            ("http", "http/timeseries", "Web traffic", "down", "geospatial", "Traffic into a country falls when the internet is cut, throttled or the population leaves; Cloudflare sees it across its network."),
            ("flows", "netflows/timeseries", "Network flows", "down", "geospatial", "Backbone traffic volume drops with outages and power loss, often before official confirmation."),
            ("l7", "attacks/layer7/timeseries", "Attack share of web traffic", "up", "information", "Surges in hostile web traffic against a country accompany cyber operations that precede or accompany force.")):
        add(f"cfr_{slug}_{th}", f"{lab}, {cc} (Cloudflare Radar)", dom, th, "daily", False, why,
            (lambda p=path, c=cc: S.fetch_radar(p, c, _key("CLOUDFLARE_API_TOKEN"))), direction=dirn,
            needs=["CLOUDFLARE_API_TOKEN"], url=f"https://radar.cloudflare.com/{cc.lower()}", sub="Network")

add("gas_ua", "Ukraine gas in storage (GIE AGSI+)", "logistics", "ukraine", "daily", False,
    "Storage draw-down ahead of winter, or strikes on gas infrastructure, show before shortages; published daily.",
    (lambda: S.fetch_agsi("UA", _key("GIE_API_KEY"))), direction="down", needs=["GIE_API_KEY"], url="https://agsi.gie.eu/", sub="Energy")
add("gas_eu", "EU gas in storage (GIE AGSI+)", "logistics", "europe_east", "daily", False,
    "Low or falling EU storage raises exposure to supply coercion; published daily.",
    (lambda: S.fetch_agsi("eu", _key("GIE_API_KEY"))), direction="down", needs=["GIE_API_KEY"], url="https://agsi.gie.eu/", sub="Energy")
for bzn, th, nm in (("PL", "europe_east", "Poland"), ("LT", "europe_east", "Lithuania")):
    add(f"power_{bzn.lower()}", f"Day-ahead power price, {nm} (Energy-Charts)", "financial", th, "daily", False,
        "Power prices jump on grid sabotage, interconnector cuts or supply fears before they appear elsewhere; published daily.",
        (lambda b=bzn: S.fetch_energycharts_price(b)), url="https://www.energy-charts.info/", sub="Energy")

def _gpsjam(th):
    def go():
        if os.environ.get("WARWATCH_LIVE") or not store.cache_load(f"gpsjam_{th}"):
            S.gpsjam_update(C.BOXES, store)
        pts = store.cache_load(f"gpsjam_{th}")
        if not pts:
            raise RuntimeError("first refresh pending (GPSJam history fills a few weeks per run)")
        return pts
    return go


def _notam(th):
    def go():
        if os.environ.get("WARWATCH_LIVE"):
            S.nms_update(C.FIRS, store)
        pts = store.cache_load(f"notam_{th}")
        if not pts:
            raise RuntimeError("first refresh pending (FAA NOTAM snapshots start now)")
        return pts
    return go


for th in C.FIRS:
    add(f"notam_{th}", f"New airspace restriction and warning NOTAMs, last 30 days, {TH[th]} (FAA)", "geospatial", th, "daily", False,
        "Airspace closures, restricted areas and conflict warnings are issued before and during operations. Snapshots start now.",
        _notam(th), url="https://notams.aim.faa.gov/", sub="Airspace")

for th in C.BOXES:
    add(f"gpsjam_{th}", f"Aircraft with degraded GPS, share per day, {TH[th]} (GPSJam)", "geospatial", th, "daily", False,
        "Jamming and spoofing of navigation signals rise before and during operations; GPSJam publishes a daily map from ADS-B reports, two days late, with history from 2022.",
        _gpsjam(th), url="https://gpsjam.org/", sub="Airspace")

add("brent_libya", "Brent crude, USD (FRED)", "financial", "libya", "daily", False,
    "Libya's output and exports move the oil price; closures of its terminals show up there first.",
    lambda: S.fetch_fred("DCOILBRENTEU", _key("FRED_API_KEY")), needs=["FRED_API_KEY"], url=FRED + "DCOILBRENTEU", sub="Fuel")
PORTS = {   # theatre: (ISO3, port-name fragments, label)
    "iran": ("IRN", ("Bandar Abbas",), "Bandar Abbas"),
    "israel": ("ISR", ("Haifa", "Ashdod"), "Haifa and Ashdod"),
    "yemen": ("YEM", ("Aden", "Hodeidah"), "Aden and Hodeidah"),
    "taiwan": ("TWN", ("Kaohsiung",), "Kaohsiung"),
    "korea": ("KOR", ("Busan",), "Busan"),
    "europe_east": ("POL", ("Gdansk", "Gdynia"), "Gdansk and Gdynia"),
    "ukraine": ("UKR", (), "all Ukrainian ports"),
    "southasia": ("PAK", ("Karachi",), "Karachi"),
    "libya": ("LBY", ("Tripoli",), "Tripoli"),
    "venezuela": ("VEN", (), "all Venezuelan ports"),
    "drc": ("COD", (), "all Congolese ports"),
    "sudan": ("SDN", (), "all Sudanese ports"),
    "scs": ("PHL", ("Manila",), "Manila"),
}
for th, (iso, names, nm) in PORTS.items():
    add(f"ports_{th}", f"Daily vessel calls, {nm} (IMF PortWatch)", "logistics", th, "daily", False,
        "Merchant ships stop calling at ports ahead of a blockade, war-risk repricing or evacuation; satellite-derived, posted weekly, so it leads supply-chain and trade statistics by months.",
        (lambda i=iso, n=names: S.fetch_portwatch_ports(i, n)), direction="down", url="https://portwatch.imf.org/", sub="Ports")

for th, slugs in C.FCDO.items():
    add(f"fcdo_{th}", f"UK travel-advice updates: {TH[th]}", "behavioral", th, "daily", False,
        "A cluster of advisory rewrites precedes evacuations and airline suspensions.",
        (lambda s=slugs: S.fetch_fcdo(s)), url="https://www.gov.uk/foreign-travel-advice", sub="Advisories")


def _state(theatre):
    def go():
        v = S.state_levels(S.fetch_state(), C.STATE_ISO[theatre])
        # Live readings from October 2026 on (one level per country) go to their own file: the earlier ones summed every
        # item filed under a code (Gaza and the West Bank on top of Israel, Saint Kitts and Nevis under North Korea's code).
        live = f"state_main_{theatre}"
        store.append(live, v)
        return store.seed(f"state_{theatre}", store.daily(live))   # backfill/data holds the weekly Wayback captures back to 2018
    return go


for th in C.STATE_ISO:
    add(f"state_{th}", f"US travel-advisory level sum: {TH[th]}", "behavioral", th, "daily", False,
        "Any step change in a flat series is flagged. History from 2018 is rebuilt from weekly Wayback captures of the State Department page.", _state(th),
        url="https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html", sub="Advisories")


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


def _gdelt(th, roots, share=False):
    def go():
        if os.environ.get("WARWATCH_LIVE"):
            S.gdelt_update(days=150)
        pts = S.gdelt_series(th, roots, share)
        if not pts:
            raise RuntimeError("first refresh pending (GDELT history fills from the news job)")
        return pts
    return go


GD = "https://www.gdeltproject.org/"
for th in C.GNEWS:
    nm = TH[th]
    add(f"news_{th}", f"Headlines with warning language per day, {nm} (Google News)", "information", th, "daily", False,
        "Counts headlines pairing the theatre with mobilization, evacuation, airspace-closure or attack wording. Fast and backfilled, but it also reacts to events, so read it with the other groups.",
        _news(th), url="https://news.google.com/", sub="News")
    add(f"gdelt_posture_{th}", f"Military-posture events per day, {nm} (GDELT)", "information", th, "daily", False,
        "GDELT codes news into events; CAMEO class 15 (show of force, alert, mobilisation) precedes action. Reached through GDELT's daily files, which the API block does not cover.",
        _gdelt(th, ("15",)), url=GD, sub="Events")
    add(f"gdelt_threat_{th}", f"Threats and ultimatums per day, {nm} (GDELT)", "information", th, "daily", False,
        "CAMEO class 13: threats, demands and ultimatums, the diplomatic stage before force.",
        _gdelt(th, ("13",)), url=GD, sub="Events")
    add(f"gdelt_fight_{th}", f"Armed-attack events per day, {nm} (GDELT)", "information", th, "daily", False,
        "CAMEO classes 18 and 19 (assault, fight). Reactive, so it confirms escalation.",
        _gdelt(th, ("18", "19")), url=GD, sub="Events")

add("brent", "Brent crude, USD (FRED)", "financial", "iran", "daily", False, "Oil prices react to Gulf and Hormuz risk.",
    lambda: S.fetch_fred("DCOILBRENTEU", _key("FRED_API_KEY")), needs=["FRED_API_KEY"], url=FRED + "DCOILBRENTEU", sub="Fuel")
add("fx_ils", "Euro in shekels (ECB rate via Frankfurter); a rise means a weaker shekel", "financial", "israel", "daily", False,
    "Currency stress shows up before escalation.", lambda: S.fetch_frankfurter("ILS"), url="https://frankfurter.dev/", sub="Currency")
add("fx_pln", "Euro in zloty (ECB rate via Frankfurter); a rise means a weaker zloty", "financial", "europe_east", "daily", False,
    "Frontline currencies weaken when investors price in conflict risk.", lambda: S.fetch_frankfurter("PLN"),
    url="https://frankfurter.dev/", sub="Currency")
add("eu_gas", "EU natural gas price, USD per MMBtu (FRED, monthly)", "financial", "europe_east", "monthly", True,
    "Gas supply is the lever Russia pulls in a standoff with Europe.",
    lambda: S.fetch_fred("PNGASEUUSDM", _key("FRED_API_KEY"), days=2400), drop=0, needs=["FRED_API_KEY"],
    url=FRED + "PNGASEUUSDM", sub="Fuel")
add("wheat", "Wheat price, USD per tonne (FRED, monthly)", "financial", "ukraine", "monthly", True,
    "Black Sea grain exports are the first thing a Ukraine escalation hits.",
    lambda: S.fetch_fred("PWHEAMTUSDM", _key("FRED_API_KEY"), days=2400), drop=0, needs=["FRED_API_KEY"],
    url=FRED + "PWHEAMTUSDM", sub="Commodities")


# ============ Market stress proxies via Yahoo Finance (no key) ============
TD = "https://finance.yahoo.com/"
for sid, sym, label, th, why, direction in (
    ("gold", "GLD", "Gold ETF (GLD) price", "global", "Money runs to gold ahead of wars, and central banks buy it before sanctions.", "up"),
    ("tanker_equity", "STNG", "Tanker shipping stock (Scorpio Tankers)", "iran", "War-risk freight premia lift tanker equities when Hormuz and Gulf routes look unsafe.", "up"),
    ("container_equity", "ZIM", "Container shipping stock (ZIM)", "yemen", "Red Sea rerouting lifts container rates and the shipping stocks that gain from them.", "up"),
    ("israel_equity", "EIS", "Israel equity ETF (EIS)", "israel", "A falling Israeli equity index prices in escalation before it happens.", "down"),
    ("poland_equity", "EPOL", "Poland equity ETF (EPOL)", "europe_east", "Frontline equity markets fall when investors price a spillover.", "down"),
):
    add(sid, f"{label} (Yahoo Finance)", "financial", th, "daily", False, why, (lambda s=sym: S.fetch_market(s)),
        direction=direction, url=TD, sub="Markets")

# ============ Satellite thermal detections (NASA FIRMS, free key) ============
def _fires(th):
    def go():
        key = _key("FIRMS_MAP_KEY")
        if not key:
            raise RuntimeError("needs FIRMS_MAP_KEY")
        import osint
        osint.firms_counts(key, th, days=150)
        pts = osint.firms_series(th)
        if not pts:
            raise RuntimeError("first refresh pending (fire history fills over a few runs)")
        return store.seed(f"firms_{th}", pts)   # standard-processing archive back to 2018, then the live cache
    return go


for th in C.FIRMS_BOX:
    add(f"firms_{th}", f"Satellite thermal detections per day, {TH[th]} (NASA FIRMS)", "geospatial", th, "daily", False,
        "Infrared satellites see shelling, strikes, burning depots and refinery fires within hours. A sustained rise inside a war-risk box is an early read on kinetic activity.",
        _fires(th), needs=["FIRMS_MAP_KEY"], url="https://firms.modaps.eosdis.nasa.gov/map/", sub="Satellite")

# ============ Evacuation and maritime-incident headlines (Google News, backfilled by the news job) ============
SEA = {"iran": 'tanker OR vessel (attacked OR struck OR seized OR "boarded") (Hormuz OR "Gulf of Oman" OR "Persian Gulf" OR UKMTO)',
       "yemen": 'ship OR vessel OR tanker (attacked OR struck OR missile OR drone) ("Red Sea" OR "Gulf of Aden" OR Houthi OR UKMTO)',
       "ukraine": 'vessel OR ship OR tanker OR port (attacked OR struck OR drone OR mine) ("Black Sea" OR Odesa OR Novorossiysk)',
       "taiwan": 'vessel OR ship OR "coast guard" OR cable (blockade OR inspection OR boarded OR cut OR harassed) ("Taiwan Strait" OR Kinmen OR Matsu OR Taiwan)',
       "scs": 'vessel OR ship OR boat OR "coast guard" (collision OR "water cannon" OR blocked OR harassed OR seized) ("South China Sea" OR "Second Thomas" OR Scarborough)'}


def _newsq(sid, query):
    def go():
        if os.environ.get("WARWATCH_LIVE"):
            return S.fetch_gnews(sid, query, days=150)
        pts = store.cache_load(sid)
        if not pts:
            raise RuntimeError("first refresh pending (news history fills from the news job)")
        return pts
    return go


for th, q in SEA.items():
    add(f"news_sea_{th}", f"Maritime attack headlines per day, {TH[th]} (Google News)", "geospatial", th, "daily", False,
        "Counts headlines on ships attacked, seized or boarded in the theatre's waters (the story UKMTO warnings feed). Seizures and harassment usually precede open strikes.",
        _newsq(f"news_sea_{th}", q), url="https://news.google.com/", sub="Sea")
add("news_evac_global", "Embassy drawdown and ordered-departure headlines per day, worldwide (Google News)", "behavioral", "global", "daily", False,
    "Governments ask staff and families to leave before strikes: 'ordered departure', 'authorized departure', 'embassy drawdown' and citizen evacuation notices.",
    _newsq("news_evac_global", '"ordered departure" OR "authorized departure" OR "embassy drawdown" OR "evacuate its citizens" OR "non-emergency personnel"'),
    url="https://news.google.com/", sub="Evacuation")


# ============ Added theatres: currencies, commodities and equities that price their risk ============
add("fx_twd", "Taiwan dollars per US dollar (Twelve Data)", "financial", "taiwan", "daily", False,
    "A weaker Taiwan dollar means capital is leaving ahead of a Strait crisis.",
    lambda: S.fetch_fx_current("USD/TWD", "DEXTAUS", _key("FRED_API_KEY")), url="https://twelvedata.com/", sub="Currency")
for sid, ccy, label, th, why in (
    ("fx_krw", "KRW", "Korean won per US dollar (ECB reference rate via Frankfurter)", "korea", "The won weakens first when a peninsula crisis is priced."),
    ("fx_inr", "INR", "Indian rupees per US dollar (ECB reference rate via Frankfurter)", "southasia", "Rupee stress shows up as India-Pakistan tension builds."),
):
    add(sid, label, "financial", th, "daily", False, why, (lambda c=ccy: S.fetch_frankfurter(c, base="USD")), direction="up",
        url="https://frankfurter.dev/", sub="Currency")
add("copper", "Copper price, USD per tonne (FRED, monthly)", "financial", "drc", "monthly", True,
    "Congo's copper and cobalt belt supplies a large share of world output, so mine and route disruption moves copper.",
    lambda: S.fetch_fred("PCOPPUSDM", _key("FRED_API_KEY"), days=2400), drop=0, needs=["FRED_API_KEY"], url=FRED + "PCOPPUSDM", sub="Commodities")
for sid, sym, label, th, why, direction in (
    ("taiwan_equity", "EWT", "Taiwan equity ETF (EWT)", "taiwan", "Taiwan's equity market, dominated by chip makers, falls when invasion or blockade risk is priced.", "down"),
    ("china_equity", "FXI", "China large-cap ETF (FXI)", "scs", "Chinese equities fall on sanction and conflict risk around the South China Sea and Taiwan.", "down"),
    ("korea_equity", "EWY", "Korea equity ETF (EWY)", "korea", "Seoul equities discount peninsula escalation.", "down"),
    ("india_equity", "INDA", "India equity ETF (INDA)", "southasia", "Indian equities fall when cross-border escalation is priced.", "down"),
    ("copper_miners", "COPX", "Copper miners ETF (COPX)", "drc", "Copper miners fall or spike on supply risk in Congo and Zambia.", "both"),
    ("latam_equity", "ILF", "Latin America 40 ETF (ILF)", "venezuela", "Regional equities discount Caribbean and Venezuelan escalation.", "down"),
):
    add(sid, f"{label} (Yahoo Finance)", "financial", th, "daily", False, why, (lambda s=sym: S.fetch_market(s)),
        direction=direction, url=TD, sub="Markets")


# Same-day proxies for the monthly or two-day-late FRED commodity series. Weightless until validate.py re-tests them (ZERO_WEIGHT below).
for sid, sym, label, th, why in (
    ("wheat_etf", "WEAT", "Wheat futures ETF (WEAT)", "ukraine", "Same-day read on Black Sea grain risk; the monthly wheat series above runs about three months late."),
    ("copper_etf", "CPER", "Copper futures ETF (CPER)", "drc", "Same-day read on Congo copper supply risk; the monthly copper series above runs about three months late."),
    ("brent_etf", "BNO", "Brent crude futures ETF (BNO)", "iran", "Same-day read on Gulf and Hormuz risk; FRED's Brent runs two days late."),
):
    add(sid, f"{label} (Yahoo Finance, Twelve Data fallback)", "financial", th, "daily", False, why, (lambda s=sym: S.fetch_market(s)),
        url=TD, sub="Commodities")

# ============ Radar ship counts (Sentinel-1), filled by the sar workflow ============
def _sar(box):
    def go():
        pts = store.cache_load(f"sar_{box}")
        if not pts:
            raise RuntimeError("first refresh pending (the radar job fills this; history backfills in slices)")
        return pts
    return go


for box, th, nm in (("hormuz", "iran", "the Strait of Hormuz"), ("bab_el_mandeb", "yemen", "Bab el-Mandeb"), ("gulf_of_aden", "yemen", "the Gulf of Aden")):
    add(f"sar_{box}", f"Radar-detected vessels per 10,000 km2 of sea, {nm} (Sentinel-1)", "geospatial", th, "daily", False,
        "Free live AIS has no receivers here, but radar satellites see every ship, including those with transponders off. Scenes arrive about every two days. "
        "Counts include oil rigs and miss small boats; a fall means fewer ships, a rise means more.",
        _sar(box), direction="down", url="https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc", sub="Sea")

# ============ Vessel presence from Global Fishing Watch (fills the gaps where live AIS has no receivers) ============
GFW_BOX = {"iran": (23, 29, 48, 60), "yemen": (11, 22, 37, 46), "israel": (31, 36, 29, 36), "ukraine": (41, 46, 27, 41), "taiwan": (21, 27, 117, 124),
           "scs": (5, 20, 108, 121), "korea": (33, 40, 124, 131), "venezuela": (8, 14, -74, -60)}
for th, box in GFW_BOX.items():
    add(f"ais_presence_{th}", f"Vessel-hours at sea in the {TH[th]} waters box (Global Fishing Watch AIS)", "geospatial", th, "daily", False,
        "Satellite and coastal AIS vessel presence from Global Fishing Watch, about five days late. A fall means traffic is avoiding the area (war-risk premiums, closures); an unusual rise means surging naval or shipping activity. It fills the gap where live AIS has no receivers.",
        (lambda b=box: S.fetch_gfw_presence(b, _key("GFW_TOKEN"))),
        direction="both", needs=["GFW_TOKEN"], drop=3, url="https://globalfishingwatch.org/map", sub="Sea")


# ============ Derived indicators, built from series already collected ============
def _package(th):
    """Tanker, surveillance and fighter aircraft present together: counts each class, multiplied by the number of classes present (strike packaging)."""
    def go():
        cls = {c: dict(store.backfill(f"adsb_{th}_{c}")) for c in ("tanker", "isr", "fighter")}
        days = sorted(set().union(*[set(v) for v in cls.values()]))
        out = []
        for d in days:
            vals = [cls[c].get(d, 0.0) for c in cls]
            out.append((d, sum(vals) * sum(1 for v in vals if v > 0)))
        return out
    return go


for th in ADSB_TH:
    add(f"package_{th}", f"Strike-package index over {TH[th]} (tankers + AWACS/ISR + fighters together)", "geospatial", th, "daily", False,
        "Derived: tankers, surveillance aircraft and fighters present at the same time. Packaged air power is how operations are staged; any one alone is routine. Built from the archive daily counts.",
        _package(th), url=ADS, sub="Derived")


def _preforce(th):
    def go():
        if os.environ.get("WARWATCH_LIVE"):
            S.gdelt_update(days=150)
        pts = _sum([S.gdelt_series(th, ("13",)), S.gdelt_series(th, ("15",))])
        if not pts:
            raise RuntimeError("first refresh pending (GDELT history fills from the news job)")
        return pts
    return go


for th in C.GNEWS:
    # shares of all coded events: a rise in coverage of a country does not move them, a change in the kind of event does
    for key, roots, nm, why in (("threat", ("13",), "Threat share", "Threats and ultimatums (CAMEO 13) per 1,000 coded events."),
                                ("posture", ("15",), "Posture share", "Military-posture events (CAMEO 15) per 1,000 coded events."),
                                ("fight", ("18", "19"), "Armed-attack share", "Assault and fight events (CAMEO 18, 19) per 1,000 coded events. Reactive, so it confirms escalation."),
                                ("preforce", ("13", "15"), "Pre-force share", "Threats plus military posture events per 1,000 coded events; the strongest broad lead in the methodology review.")):
        add(f"gdeltshare_{key}_{th}", f"{nm}, {TH[th]} (GDELT)", "information", th, "daily", False, why + " A share, so changes in news volume do not move it.",
            _gdelt(th, roots, True), url=GD, sub="Events")
    add(f"gdelt_preforce_{th}", f"Pre-force index: threats plus military posture events per day, {TH[th]} (GDELT)", "information", th, "daily", False,
        "Derived: ultimatums (CAMEO 13) and shows of force (CAMEO 15) together. Escalation ladders run threat, then posture, then force, so both rising together is the pattern that precedes strikes.",
        _preforce(th), url=GD, sub="Derived")


# ============ Japan Coast Guard warnings: NAVAREA XI (Japan coordinates it) and Japan's own navigational warnings ============
for th in ("korea", "taiwan", "scs"):
    add(f"jcg_{th}", f"New firing, missile and exercise warnings, last 30 days, {TH[th]} waters (Japan Coast Guard)", "geospatial", th, "daily", False,
        "Live-fire, missile and exercise notices broadcast by Japan's Coast Guard for the northwest Pacific, including South Korean firing areas and "
        "North Korean launch windows; exercises are announced before they happen. Kept from 10 October 2026 and counted from 9 November.",
        (lambda t=th: extras.jcg_series(t)), url="https://www1.kaiho.mlit.go.jp/TUHO/keiho/navarea11.html", sub="Warnings")


# ============ China MSA military navigational warnings by issuing bureau (mobile-site list API; history from backfill.py msa) ============
for th, where in (("taiwan", "East China Sea and Taiwan Strait"), ("scs", "South China Sea and Gulf of Tonkin"), ("korea", "Yellow Sea and Bohai")):
    add(f"msa_{th}", f"China's military navigational warnings, last 30 days, {TH[th]} waters (China MSA)", "geospatial", th, "daily", False,
        f"Closures China's Maritime Safety Administration posts for military exercises, live fire and missile tests ({where}). "
        "Counts routine and live-fire closures; the PLA's largest drills around Taiwan (2022, 2023, 2024) were announced through Xinhua instead, so this tracks the tempo around them. History from July 2020, when all three seas post to the list.",
        (lambda t=th: extras.msa_series(t)), url="https://www.msa.gov.cn/msacncms_wap/pages/info_warn.jhtml?channelId=9c219298b27f460e995a99401b3ff6af", sub="Warnings")


# ============ China Customs: monthly exports to the countries at war or under sanctions (GACC English Monthly Bulletin) ============
for key, th, nm in (("russia", "ukraine", "Russia"), ("belarus", "ukraine", "Belarus"), ("iran", "iran", "Iran"), ("dprk", "korea", "North Korea")):
    add(f"gacc_{key}", f"China's exports to {nm}, US$ million a month (China Customs)", "logistics", th, "monthly", True,
        f"What China ships to {nm} each month, from its own customs bulletin, about three weeks after the month ends. A supplier stocking a partner "
        "before or during a war shows up here first; Comtrade's mirror data carries the same flow months later.",
        (lambda k=key: extras.gacc_series(k)), drop=0, url=extras.GACC_MONTHLY, sub="Trade")


# ============ Official UKMTO incident counts (the Royal Navy maritime trade centre feed behind ukmto.org) ============
for th in ("iran", "yemen"):
    add(f"ukmto_{th}", f"UKMTO incident reports in last 30 days, {TH[th]} waters (official)", "geospatial", th, "daily", False,
        "Suspicious approaches, hijackings and attacks reported by masters to UKMTO. Harassment and approaches usually precede strikes on shipping. The feed keeps about 100 days, so the history starts a month after its oldest incident.",
        (lambda t=th: __import__("osint").ukmto_series(t)), url="https://www.ukmto.org/recent-incidents", sub="Sea")


# ============ Israel's rocket, missile and drone sirens (Tzeva Adom, which mirrors Home Front Command alerts) ============
add("tzeva_israel", "Rocket, missile and drone alert waves in Israel, last 7 days (Tzeva Adom)", "geospatial", "israel", "daily", False,
    "Each wave is one attack that set off Home Front Command sirens: rockets from Gaza or Lebanon, missiles from Iran or Yemen, hostile drones. "
    "Sirens less than 10 minutes apart count as one wave. Reactive, so it confirms escalation, and a run of waves marks a new round. "
    "Tzeva Adom serves only its latest 50 waves; the history before them comes from the open mirror of Home Front Command alerts, back to July 2014.",
    (lambda: __import__("osint").tzeva_series()), url="https://www.tzevaadom.co.il/", sub="Strikes")

# ============ Crisis Group CrisisWatch alerts (read from the Crisis Group RSS feed; the CrisisWatch pages themselves refuse automated readers) ============
for th in __import__("osint").CW_THEATRE:
    add(f"crisiswatch_{th}", f"CrisisWatch rating, {TH[th]} region: 2 for a conflict-risk alert, plus 1 for a deteriorated situation (Crisis Group)", "information", th, "monthly", False,
        "Crisis Group's monthly global tracker, written by its country analysts. A conflict-risk alert is their judgement that a war or a sharp escalation is likely in the coming month. "
        "Read from the issue posted in Crisis Group's RSS feed and kept from October 2026.",
        (lambda t=th: __import__("osint").crisiswatch_series(t)), drop=0, url="https://www.crisisgroup.org/crisiswatch", sub="Expert")


# ============ Ukraine air-raid alerts (alerts.in.ua; news.yml fills the cache every 6 hours) ============
add("uaair_ukraine", "Air-raid alerts on whole oblasts across Ukraine, last 7 days (alerts.in.ua)", "geospatial", "ukraine", "daily", False,
    "Each count is one oblast (or Kyiv city) placed under air-raid alert. A Russian missile or drone wave sets off most of the country at once, so the "
    "count rises with each wave. Reactive, so it confirms escalation. The service keeps a month per region; the archive starts on 10 October 2026, a month back.",
    _slow("uaair_ukraine", lambda: __import__("osint").ua_air_series(_key("ALERTS_IN_UA_TOKEN"))), needs=["ALERTS_IN_UA_TOKEN"], url="https://alerts.in.ua/", sub="Strikes")


# ============ Bluesky war talk per theatre (Jetstream firehose sample, five minutes every half hour; news.yml fills the cache) ============
for th in extras.KEYS:
    add(f"bsky_{th}", f"Bluesky posts about war naming {TH[th]}, per 10,000 English posts", "information", th, "daily", False,
        "Share of English Bluesky posts that name the theatre and use war words (strike, missiles, troops, evacuation). A share, so the network's growth "
        "does not move it. Social talk spikes with the news, so it mostly confirms; a rise before the headlines is the signal worth watching.",
        _slow(f"bsky_{th}", (lambda t=th: __import__("osint").bsky_series(t))), url="https://docs.bsky.app/blog/jetstream", sub="Social")


# ============ ACLED conflict-event counts via HDX HAPI (the open route to ACLED data; ~2 months behind) ============
HAPI_LOC = {"ukraine": ("UKR",), "europe_east": ("POL", "LTU", "LVA", "EST"), "iran": ("IRN",), "yemen": ("YEM",), "israel": ("ISR", "PSE", "LBN"),
            "scs": ("PHL",), "southasia": ("IND", "PAK"), "libya": ("LBY",), "sudan": ("SDN", "SSD"), "drc": ("COD",), "venezuela": ("VEN", "COL")}
for th, locs in HAPI_LOC.items():
    add(f"acled_demo_{th}", f"Demonstrations per month, {TH[th]} region (ACLED via HDX HAPI)", "behavioral", th, "monthly", True,
        "Protest waves and unrest precede and accompany regime stress, mobilisation and war decisions. ACLED data through the open HDX HAPI feed, about two months behind.",
        (lambda l=locs: S.fetch_hapi_events(l, ("demonstration",))), drop=0, url="https://hapi.humdata.org/", sub="Unrest")
    if th != "europe_east":
        add(f"acled_viol_{th}", f"Political violence and civilian-targeting events per month, {TH[th]} region (ACLED via HDX HAPI)", "geospatial", th, "monthly", True,
            "Counts of armed clashes, strikes and attacks on civilians coded by ACLED. Reactive, so it confirms escalation. Open HDX HAPI feed, about two months behind.",
            (lambda l=locs: S.fetch_hapi_events(l, ("political_violence", "civilian_targeting"))), drop=0, url="https://hapi.humdata.org/", sub="Conflict events")

# The full download takes about ten minutes, so news.yml fetches it every 6 hours and the build only reads the cache
# (no 'every' cadence below: the build re-reading the cache would re-stamp it and the slow job would never refetch).
for th, box in C.BOXES.items():
    add(f"ucdp_deaths_{th}", f"Deaths in organised violence per month, {TH[th]} region (UCDP)", "geospatial", th, "monthly", True,
        "Uppsala's event-by-event conflict dataset: best-estimate deaths from battles, one-sided attacks and non-state clashes inside the theatre box. Reactive, so it confirms escalation. Runs two to three months behind and is revised.",
        _slow(f"ucdp_deaths_{th}", lambda b=box: S.fetch_ucdp(b, _key("UCDP_TOKEN"))), drop=0, needs=["UCDP_TOKEN"], url="https://ucdp.uu.se/", sub="Conflict events")

# ============ How often each source is worth fetching (hours between full fetches) ============
# Slow-moving sources are re-read from their cache in between, so the page can rebuild every 30 minutes
# for the live layers without hammering rate-limited APIs.
for _s in SERIES:
    _id = _s["id"]
    if _id.startswith(("us_", "eu_", "dod_", "acled_", "gacc_")) and _s["kind"] == "monthly":
        _s["every"] = 20      # trade and contract data change monthly, after a lag
    elif "FRED_API_KEY" in _s["needs"] or "fetch_market" in _s["fetch"].__code__.co_names:
        _s["every"] = 6       # daily closes
    elif _id.startswith(("portwatch_", "fcdo_", "crisiswatch_")):
        _s["every"] = 12      # PortWatch posts weekly, FCDO rewrites advice rarely, CrisisWatch is monthly
    elif _id.startswith(("ioda_", "ooni_", "ports_", "cfr_", "gas_", "power_", "fx_", "msa_", "jcg_")):
        _s["every"] = 3
    elif _id.startswith("ais_presence_"):
        _s["every"] = 12      # one call per box; the source posts daily with a ~5 day delay


# ============ Zero weight: families the methodology review found to be noise ============
# Their noise-to-signal ratio on 78 labelled events (2018-2026) was 1 or more, so they raised false alarms without adding
# warning (docs/METHODOLOGY.md, "Zero-weight families"). They stay on the page and keep being scored; the composite ignores
# them until a refit shows they lead events. Remove an id here to give it weight again.
ZERO_WEIGHT = ("ioda_", "ooni_", "diesel_nyh", "jet_fuel_gulf", "fx_ils", "dod_build_", "wheat_etf", "copper_etf", "brent_etf", "sar_")
for _s in SERIES:
    if _s["id"].startswith(ZERO_WEIGHT):
        _s["scored"] = False


# ============ Prices scored on their change ============
# A price that trends sits above its own yearly baseline for months: gold, copper, FX and the defence stocks read z >= 2 on
# 20-34% of calm days when scored on their level (docs/INDICATORSTUDY.md). Scored on their % change (20 trading days,
# 3 months for monthly series) the same series do so on 2-10%. VIX and power prices mean-revert, so they keep their level.
CHANGE_SCORED = ("def_", "brent", "gold", "fx_", "tanker_equity", "container_equity", "israel_equity", "poland_equity", "taiwan_equity",
                 "china_equity", "korea_equity", "india_equity", "latam_equity", "copper", "eu_gas", "wheat", "diesel_nyh", "jet_fuel_gulf")
for _s in SERIES:
    if _s["domain"] == "financial" and _s["id"].startswith(CHANGE_SCORED):
        _s["transform"] = "chg"
