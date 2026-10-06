"""Groups, theatres and thresholds. Series themselves live in catalog.py.

Every PSC, HS and CPV code is a hypothesis to verify against the official
code manuals; each series in the catalogue carries a `why` line.
"""
# Five independent evidence groups. A theatre's level counts how many fire at once.
DOMAINS = {
    "logistics": "Logistics & procurement",
    "financial": "Financial & markets",
    "behavioral": "Human & behavioral",
    "geospatial": "Geospatial & physical",
    "information": "Information space",
}
GROUP_HELP = {
    "logistics": "Armies must buy, ship and stock before they fight: contracts, tenders and trade flows.",
    "financial": "Money moves before armies: defence stocks, currencies, fuel and prediction markets.",
    "behavioral": "What governments, airlines and citizens do when they expect trouble: advisories, evacuations, alerts.",
    "geospatial": "Observable physical activity: aircraft, ships, jamming, closed airspace, internet blackouts.",
    "information": "How the news and event record shifts: warning language, military-posture events.",
}
# theatre -> name, map focus (lon_min, lon_max, lat_min, lat_max), countries to outline on the map
THEATRES = {
    "ukraine": {"name": "Ukraine", "view": (20, 46, 42, 56),
                "countries": ["Ukraine", "Russia", "Belarus", "Moldova"]},
    "europe_east": {"name": "Eastern flank", "view": (8, 36, 48, 62),
                    "countries": ["Poland", "Lithuania", "Latvia", "Estonia", "Finland", "Romania"]},
    "iran": {"name": "Iran", "view": (42, 66, 22, 40), "countries": ["Iran"]},
    "yemen": {"name": "Yemen", "view": (34, 60, 8, 22),
              "countries": ["Yemen", "Saudi Arabia", "Oman", "Djibouti", "Eritrea", "Somalia"]},
    "israel": {"name": "Israel", "view": (28, 42, 26, 36),
               "countries": ["Israel", "Lebanon", "Palestine", "Syria", "Jordan", "Egypt"]},
    "global": {"name": "Global", "view": (-10, 70, 10, 62), "countries": []},
}
THRESH_SIGNAL = 3.0   # a group fires at or above this robust z (calibrated: ~5% Watch on pure noise)
THRESH_WATCH = 2.0
USER_AGENT = "warwatch/0.3 (public-data research; github.com/khourix/warwatch)"

# destination sets for trade series (ISO2 as Eurostat uses; names as Census prints)
PARTNERS = {
    "ukraine": {"iso": ["UA"], "names": ["UKRAINE"]},
    "europe_east": {"iso": ["PL", "LT", "LV", "EE", "FI", "RO"],
                    "names": ["POLAND", "LITHUANIA", "LATVIA", "ESTONIA", "FINLAND", "ROMANIA"]},
    "iran": {"iso": ["IR", "IQ"], "names": ["IRAN", "IRAQ"]},
    "yemen": {"iso": ["YE", "DJ", "OM"], "names": ["YEMEN", "DJIBOUTI", "OMAN"]},
    "israel": {"iso": ["IL", "JO", "LB"], "names": ["ISRAEL", "JORDAN", "LEBANON"]},
}
BOXES = {   # lat_min, lat_max, lon_min, lon_max for military ADS-B counts and hazard warnings
    "ukraine": (44, 53, 22, 41),
    "europe_east": (49, 66, 14, 30),
    "iran": (24, 40, 44, 64),
    "yemen": (8, 21, 38, 56),
    "israel": (27, 37, 28, 40),
}
THEATRE_BOX = BOXES
HUBS = {   # civil-traffic samples for GNSS-jamming and airspace-closure signals: (lat, lon, radius nm)
    "ukraine": [(46.8, 26.5, 250)],
    "europe_east": [(55.0, 22.5, 250)],
    "iran": [(26.0, 52.0, 250), (36.0, 44.0, 250)],
    "yemen": [(18.0, 41.0, 250), (13.0, 48.0, 250)],
    "israel": [(32.0, 35.5, 250)],
}
FCDO = {   # UK travel-advice slugs per theatre
    "ukraine": ["ukraine", "belarus", "moldova"],
    "europe_east": ["poland", "lithuania", "latvia", "estonia", "finland"],
    "iran": ["iran", "iraq"],
    "yemen": ["yemen", "saudi-arabia", "oman", "djibouti"],
    "israel": ["israel", "lebanon", "jordan", "egypt"],
}
STATE_ISO = {"ukraine": ["UP", "BO", "MD"],
             "europe_east": ["PL", "LH", "LG", "EN", "FI"],
             "iran": ["IR", "IZ"],
             "yemen": ["YM", "SA", "MU", "DJ"],
             "israel": ["IS", "LE", "JO", "EG"]}   # FIPS codes, as the feed uses
GDELT_CC = {   # FIPS country codes whose events count toward a theatre
    "ukraine": ["UP", "BO", "MD"],
    "europe_east": ["PL", "LH", "LG", "EN", "FI", "RO"],
    "iran": ["IR"],
    "yemen": ["YM"],
    "israel": ["IS", "LE"],
}
GNEWS = {   # theatre -> headline search for warning-class language (Google News RSS)
    "ukraine": '(Ukraine OR Belarus) (mobilization OR "troops massing" OR reservists OR "airspace closed" OR "martial law")',
    "europe_east": '(Baltic OR Kaliningrad OR Suwalki OR Poland OR Lithuania) (troops OR exercise OR "airspace violation" OR "GPS jamming")',
    "iran": '(Iran OR IRGC OR Hormuz) (strike OR mobilization OR evacuate OR "airspace closed" OR "internet shutdown" OR "carrier strike group")',
    "yemen": '(Houthi OR Yemen OR "Red Sea") (attack OR missile OR ship OR drone OR strike)',
    "israel": '(Israel OR Hezbollah OR Lebanon OR Gaza) (mobilization OR reservists OR evacuate OR "airspace closed" OR embassy)',
}
CHOKEPOINTS = {  # PortWatch portname fragment -> theatre
    "Hormuz": "iran", "Bab": "yemen", "Suez": "israel", "Bosporus": "ukraine",
}
CHOKE_XY = {"Hormuz": (26.6, 56.3, "Strait of Hormuz"), "Bab": (12.6, 43.3, "Bab el-Mandeb"),
            "Suez": (30.0, 32.5, "Suez Canal"), "Bosporus": (41.1, 29.0, "Bosporus")}
CITIES = {   # theatre -> [(name, lat, lon)] reference points drawn on the map
    "ukraine": [("Kyiv", 50.45, 30.52), ("Kharkiv", 49.99, 36.23), ("Odesa", 46.48, 30.72), ("Moscow", 55.75, 37.62),
                ("Minsk", 53.9, 27.57), ("Sevastopol", 44.6, 33.5), ("Donetsk", 48.0, 37.8)],
    "europe_east": [("Warsaw", 52.23, 21.01), ("Vilnius", 54.69, 25.28), ("Riga", 56.95, 24.1), ("Tallinn", 59.44, 24.75),
                    ("Kaliningrad", 54.71, 20.51), ("Helsinki", 60.17, 24.94), ("Bucharest", 44.43, 26.1),
                    ("Suwalki gap", 54.1, 23.0)],
    "iran": [("Tehran", 35.69, 51.39), ("Isfahan", 32.65, 51.67), ("Bandar Abbas", 27.18, 56.27), ("Natanz", 33.72, 51.73),
             ("Baghdad", 33.31, 44.36), ("Dubai", 25.2, 55.27)],
    "yemen": [("Sanaa", 15.37, 44.19), ("Hodeidah", 14.8, 42.95), ("Aden", 12.78, 45.04), ("Riyadh", 24.71, 46.68),
              ("Djibouti", 11.59, 43.15), ("Jeddah", 21.5, 39.2)],
    "israel": [("Tel Aviv", 32.09, 34.78), ("Jerusalem", 31.77, 35.21), ("Haifa", 32.79, 34.99), ("Beirut", 33.89, 35.5),
               ("Gaza", 31.5, 34.47), ("Damascus", 33.51, 36.29), ("Cairo", 30.04, 31.24)],
}

SEAS = [("Black Sea", 43.5, 34.5), ("Baltic Sea", 57.5, 19.5), ("Mediterranean Sea", 35.0, 18.0), ("Red Sea", 20.5, 38.5), ("Arabian Sea", 16.0, 64.0),
        ("Persian Gulf", 27.0, 51.5), ("Gulf of Aden", 12.2, 48.0), ("North Sea", 56.0, 3.0), ("Caspian Sea", 41.5, 50.5), ("Norwegian Sea", 66.5, 3.0),
        ("Gulf of Oman", 24.5, 58.8), ("Adriatic Sea", 42.8, 15.8)]
