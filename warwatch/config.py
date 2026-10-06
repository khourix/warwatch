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
    "attention": "Attention and advisories",
    "markets": "Markets",
}
THEATRES = {
    "global": "Supplier side (US and EU)",
    "europe_east": "NATO eastern flank",
    "ukraine": "Ukraine",
    "mideast": "Middle East",
}
THRESH_SIGNAL = 2.5   # a domain fires at or above this robust z
THRESH_WATCH = 1.5
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
GDELT = {   # theatre -> (id, query)
    "ukraine": ("gdelt_ukraine", '(Ukraine OR Kyiv) (mobilization OR offensive OR "air raid")'),
    "mideast": ("gdelt_mideast", '(Iran OR Israel OR Hezbollah OR Houthi) (strike OR missile OR mobilization)'),
    "europe_east": ("gdelt_eastflank", '(Baltic OR Suwalki OR Kaliningrad OR "eastern flank") (troops OR drills OR buildup)'),
}
WIKI = {
    "global": ["Conscription", "Mobilization", "Nuclear_warfare"],
    "mideast": ["Strait_of_Hormuz", "Houthi_movement"],
    "ukraine": ["Russo-Ukrainian_War"],
    "medical": ["Blood_donation", "Tourniquet"],
    "vehicles": ["Toyota_Hilux", "Technical_(vehicle)"],
    "kit": ["Combat_boot"],
}
CHOKEPOINTS = {  # PortWatch portname fragment -> theatre
    "Hormuz": "mideast", "Bab": "mideast", "Suez": "mideast",
    "Bosporus": "ukraine",
}
