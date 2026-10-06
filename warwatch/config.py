"""Domains, theatres and thresholds. Series themselves live in catalog.py.

Every PSC, HS and CPV code is a hypothesis to verify against the official
code manuals; each series in the catalogue carries a `why` line.
"""
DOMAINS = {
    "kit": "Troop kit (boots, body armor)",
    "vehicles": "Pickups and light trucks",
    "medical": "Blood and trauma supplies",
    "infrastructure": "Forward infrastructure",
    "flows": "Sea and air flows",
    "airspace": "Airspace and navigation",
    "attention": "Advisories and news",
    "markets": "Markets",
}
THEATRES = {
    "global": "Supplier side (US and EU)",
    "europe_east": "NATO eastern flank",
    "ukraine": "Ukraine",
    "mideast": "Middle East",
}
THRESH_SIGNAL = 3.0   # a domain fires at or above this robust z (calibrated: ~5% Watch on pure noise)
THRESH_WATCH = 2.0
USER_AGENT = "warwatch/0.2 (public-data research; github.com/khourix/warwatch)"

# destination sets for trade series (ISO2 as Eurostat uses; names as Census prints)
PARTNERS = {
    "ukraine": {"iso": ["UA"], "names": ["UKRAINE"]},
    "mideast": {"iso": ["IL", "JO", "LB", "SA", "AE", "KW", "QA", "BH", "OM", "IQ"],
                "names": ["ISRAEL", "JORDAN", "LEBANON", "SAUDI ARABIA",
                          "UNITED ARAB EMIRATES", "KUWAIT", "QATAR", "BAHRAIN",
                          "OMAN", "IRAQ"]},
    "europe_east": {"iso": ["PL", "LT", "LV", "EE", "FI", "RO"],
                    "names": ["POLAND", "LITHUANIA", "LATVIA", "ESTONIA",
                              "FINLAND", "ROMANIA"]},
}
BOXES = {   # lat_min, lat_max, lon_min, lon_max for military ADS-B counts
    "ukraine": (44, 53, 22, 41),
    "mideast": (12, 38, 34, 60),
    "europe_east": (49, 66, 14, 30),
}
FCDO = {   # UK travel-advice slugs per theatre
    "ukraine": ["ukraine", "belarus", "moldova"],
    "mideast": ["israel", "iran", "lebanon", "jordan", "iraq", "saudi-arabia",
                "united-arab-emirates", "kuwait", "qatar", "bahrain", "oman"],
    "europe_east": ["poland", "lithuania", "latvia", "estonia", "finland"],
}
STATE_ISO = {"ukraine": ["UP", "BO", "MD"],
             "mideast": ["IS", "IR", "LE", "JO", "IZ", "SA", "AE", "KU", "QA", "BA", "MU"],
             "europe_east": ["PL", "LH", "LG", "EN", "FI"]}   # FIPS codes, as the feed uses
HUBS = {   # civil-traffic samples for GNSS-jamming and airspace-closure signals: (lat, lon, radius nm)
    "ukraine": [(46.8, 26.5, 250)],
    "europe_east": [(55.0, 22.5, 250)],
    "mideast": [(31.5, 36.0, 300), (26.0, 52.0, 250)],
}
THEATRE_BOX = {   # lat_min, lat_max, lon_min, lon_max: where hazard warnings count toward a theatre
    "ukraine": (43, 53, 22, 42),
    "europe_east": (53, 66, 12, 30),
    "mideast": (10, 40, 28, 62),
}
GNEWS = {   # theatre -> headline search for warning-class language (Google News RSS)
    "ukraine": '(Ukraine OR Belarus) (mobilization OR "troops massing" OR reservists OR "airspace closed" OR "martial law")',
    "mideast": '(Iran OR Israel OR Hezbollah OR Houthi) (mobilization OR evacuate OR "airspace closed" OR embassy OR "carrier strike group")',
    "europe_east": '(Baltic OR Kaliningrad OR Suwalki OR Poland OR Lithuania) (troops OR exercise OR "airspace violation" OR "GPS jamming")',
}
CHOKEPOINTS = {  # PortWatch portname fragment -> theatre
    "Hormuz": "mideast", "Bab": "mideast", "Suez": "mideast",
    "Bosporus": "ukraine",
}
