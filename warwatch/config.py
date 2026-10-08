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
    "iran": {"name": "Iran", "view": (42, 70, 11, 40), "countries": ["Iran"]},
    "yemen": {"name": "Yemen", "view": (34, 60, 8, 22),
              "countries": ["Yemen", "Saudi Arabia", "Oman", "Djibouti", "Eritrea", "Somalia"]},
    "israel": {"name": "Israel", "view": (28, 42, 26, 36),
               "countries": ["Israel", "Lebanon", "Palestine", "Syria", "Jordan", "Egypt"]},
    "taiwan": {"name": "Taiwan Strait", "view": (112, 132, 16, 32), "countries": ["Taiwan"]},
    "scs": {"name": "South China Sea", "view": (105, 125, 2, 22), "countries": ["Philippines", "Vietnam"]},
    "korea": {"name": "Korea", "view": (121, 136, 32, 44), "countries": ["South Korea", "North Korea"]},
    "southasia": {"name": "South Asia (India-Pakistan)", "view": (60, 92, 20, 40), "countries": ["India", "Pakistan"]},
    "libya": {"name": "Libya", "view": (8, 28, 18, 38), "countries": ["Libya"]},
    "sudan": {"name": "Sudan", "view": (20, 40, 3, 23), "countries": ["Sudan", "S. Sudan"]},
    "drc": {"name": "DR Congo", "view": (10, 36, -14, 6), "countries": ["Dem. Rep. Congo"]},
    "venezuela": {"name": "Americas (Venezuela and Caribbean)", "view": (-85, -55, 0, 16), "countries": ["Venezuela", "Guyana"]},
    "global": {"name": "Global", "view": (-100, 150, -20, 64), "countries": []},
}
# Main tabs: the market-moving theatres. A region with several sub-theatres shows them as a secondary tab row;
# a region with one sub-theatre is that theatre. Region level = the highest sub-theatre level.
REGIONS = [
    ("mideast", "Middle East", ["iran", "israel", "yemen"]),
    ("ukraine_r", "Ukraine", ["ukraine", "europe_east"]),
    ("taiwan_r", "Taiwan", ["taiwan", "scs"]),
    ("korea_r", "Korea", ["korea"]),
    ("southasia_r", "South Asia", ["southasia"]),
    ("africa_r", "Africa", ["libya", "sudan", "drc"]),
    ("americas_r", "Americas", ["venezuela"]),
]
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
    "taiwan": {"iso": ["TW"], "names": ["TAIWAN"]},
    "korea": {"iso": ["KR"], "names": ["KOREA, SOUTH"]},
    "southasia": {"iso": ["IN", "PK"], "names": ["INDIA", "PAKISTAN"]},
}
BOXES = {   # lat_min, lat_max, lon_min, lon_max for military ADS-B counts and hazard warnings
    "ukraine": (44, 53, 22, 41),
    "europe_east": (49, 66, 14, 30),
    "iran": (24, 40, 44, 64),
    "yemen": (8, 21, 38, 56),
    "israel": (27, 37, 28, 40),
    "taiwan": (20, 28, 117, 126),
    "scs": (5, 20, 108, 122),
    "korea": (33, 43, 124, 132),
    "southasia": (23, 37, 66, 78),
    "libya": (24, 34, 10, 25),
    "sudan": (8, 22, 22, 38),
    "drc": (-12, 2, 12, 32),
    "venezuela": (0, 13, -76, -60),
}
THEATRE_BOX = BOXES
FIRS = {   # flight information regions queried in the FAA NOTAM service for each theatre
    "ukraine": ["UKBV", "UKLV", "UKOV", "UKDV", "UKXX"], "europe_east": ["EPWW", "EVRR", "EYVL", "EETT", "UMMV"],
    "iran": ["OIIX"], "yemen": ["OYSC"], "israel": ["LLLL", "OLBB", "OSTT", "ORBB"], "taiwan": ["RCAA"],
    "scs": ["RPHI", "VHHK"], "korea": ["RKRR", "ZKKP"], "southasia": ["OPKR", "OPLR", "VIDF", "VABF"],
    "libya": ["HLLL"], "sudan": ["HSSS"], "drc": ["FZZA"], "venezuela": ["SVZM"],
}
NOTAM_PREFIX = {"ukraine": "UK", "yemen": "OY", "libya": "HL"}   # also match 4-letter ICAO locations with this prefix (US airports use 3 letters)
FIRMS_BOX = {   # satellite thermal boxes: wider than the aircraft boxes so they cover the Levant, Iraq and the Gulf states
    "ukraine": (44, 53, 22, 41), "europe_east": (49, 66, 14, 30),
    "iran": (22, 40, 38, 64),      # Iran, Iraq, Kuwait, Bahrain, Qatar, UAE, northern Oman, eastern Saudi Arabia
    "yemen": (8, 22, 34, 60),      # Yemen, Red Sea coasts, southern Oman, Horn of Africa coast
    "israel": (28, 38, 32, 44),    # Israel, Gaza, Lebanon, Syria, Jordan, Sinai
    "korea": (33, 43, 124, 132), "libya": (24, 34, 10, 25),   # skipped where crop burning swamps the signal: Sudan, DRC, India, Venezuela
}
HUBS = {   # civil-traffic samples for GNSS-jamming and airspace-closure signals: (lat, lon, radius nm)
    "ukraine": [(46.8, 26.5, 250)],
    "europe_east": [(55.0, 22.5, 250)],
    "iran": [(26.0, 52.0, 250), (36.0, 44.0, 250)],
    "yemen": [(18.0, 41.0, 250), (13.0, 48.0, 250)],
    "israel": [(32.0, 35.5, 250)],
    "taiwan": [(25.0, 121.2, 250)],
    "scs": [(14.6, 121.0, 250)],
    "korea": [(37.5, 127.0, 250)],
    "southasia": [(31.5, 74.3, 250), (28.6, 77.1, 250)],
    "libya": [(32.9, 13.2, 250)],
    "venezuela": [(10.6, -66.9, 250)],
}
FCDO = {   # UK travel-advice slugs per theatre
    "ukraine": ["ukraine", "belarus", "moldova"],
    "europe_east": ["poland", "lithuania", "latvia", "estonia", "finland"],
    "iran": ["iran", "iraq"],
    "yemen": ["yemen", "saudi-arabia", "oman", "djibouti"],
    "israel": ["israel", "lebanon", "jordan", "egypt"],
    "taiwan": ["taiwan"], "scs": ["philippines", "vietnam"], "korea": ["south-korea", "north-korea"],
    "southasia": ["india", "pakistan"], "libya": ["libya"], "sudan": ["sudan", "south-sudan"],
    "drc": ["democratic-republic-of-the-congo"], "venezuela": ["venezuela", "colombia", "cuba"],
}
STATE_ISO = {"ukraine": ["UP", "BO", "MD"],
             "europe_east": ["PL", "LH", "LG", "EN", "FI"],
             "iran": ["IR", "IZ"],
             "yemen": ["YM", "SA", "MU", "DJ"],
             "israel": ["IS", "LE", "JO", "EG"],   # FIPS codes, as the feed uses
             "taiwan": ["TW"], "scs": ["RP", "VM"], "korea": ["KS", "KN"], "southasia": ["IN", "PK"],
             "libya": ["LY"], "sudan": ["SU", "OD"], "drc": ["CG"], "venezuela": ["VE", "CO", "CU"]}
GDELT_CC = {   # FIPS country codes whose events count toward a theatre
    "ukraine": ["UP", "BO", "MD"],
    "europe_east": ["PL", "LH", "LG", "EN", "FI", "RO"],
    "iran": ["IR"],
    "yemen": ["YM"],
    "israel": ["IS", "LE"],
    "taiwan": ["TW"], "scs": ["RP", "VM"], "korea": ["KS", "KN"], "southasia": ["IN", "PK"],
    "libya": ["LY"], "sudan": ["SU", "OD"], "drc": ["CG"], "venezuela": ["VE"],
}
GNEWS = {   # theatre -> headline search for warning-class language (Google News RSS)
    "ukraine": '(Ukraine OR Belarus) (mobilization OR "troops massing" OR reservists OR "airspace closed" OR "martial law")',
    "europe_east": '(Baltic OR Kaliningrad OR Suwalki OR Poland OR Lithuania) (troops OR exercise OR "airspace violation" OR "GPS jamming")',
    "iran": '(Iran OR IRGC OR Hormuz) (strike OR mobilization OR evacuate OR "airspace closed" OR "internet shutdown" OR "carrier strike group")',
    "yemen": '(Houthi OR Yemen OR "Red Sea") (attack OR missile OR ship OR drone OR strike)',
    "israel": '(Israel OR Hezbollah OR Lebanon OR Gaza) (mobilization OR reservists OR evacuate OR "airspace closed" OR embassy)',
    "taiwan": '(Taiwan OR "Taiwan Strait" OR PLA) (drills OR blockade OR "air defense identification zone" OR "live-fire" OR invasion OR "coast guard")',
    "scs": '("South China Sea" OR Philippines OR "Second Thomas" OR Scarborough) (collision OR "water cannon" OR coast guard OR blockade OR "live-fire")',
    "korea": '("North Korea" OR Pyongyang OR "Korean Peninsula") (missile OR launch OR "nuclear test" OR artillery OR DMZ OR "troops")',
    "southasia": '(India OR Pakistan OR Kashmir OR "Line of Control") (strike OR shelling OR mobilization OR "airspace closed" OR ceasefire OR missile)',
    "libya": '(Libya OR Tripoli OR "Es Sider" OR "oil terminal") (clashes OR shutdown OR "force majeure" OR blockade OR militia)',
    "sudan": '(Sudan OR Khartoum OR RSF OR "South Sudan") (attack OR offensive OR "oil pipeline" OR shelling OR drone)',
    "drc": '(Congo OR DRC OR M23 OR Goma OR Katanga) (offensive OR clashes OR cobalt OR copper OR "mine" OR attack)',
    "venezuela": '(Venezuela OR Maduro OR Caribbean OR Guyana OR Essequibo) (strike OR "naval" OR troops OR blockade OR sanctions OR "military buildup")',
}
CHOKEPOINTS = {  # PortWatch portname fragment -> theatre
    "Hormuz": "iran", "Bab": "yemen", "Suez": "israel", "Bosporus": "ukraine",
    "Taiwan Strait": "taiwan", "Malacca": "scs", "Panama": "venezuela",
}
CHOKE_XY = {"Hormuz": (26.6, 56.3, "Strait of Hormuz"), "Bab": (12.6, 43.3, "Bab el-Mandeb"),
            "Suez": (30.0, 32.5, "Suez Canal"), "Bosporus": (41.1, 29.0, "Bosporus"),
            "Taiwan Strait": (24.5, 119.5, "Taiwan Strait"), "Malacca": (2.5, 101.5, "Strait of Malacca"), "Panama": (9.1, -79.7, "Panama Canal")}
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
    "taiwan": [("Taipei", 25.03, 121.56), ("Kaohsiung", 22.63, 120.3), ("Kinmen", 24.45, 118.38), ("Fuzhou", 26.07, 119.3), ("Xiamen", 24.48, 118.09), ("Okinawa", 26.2, 127.7)],
    "scs": [("Manila", 14.6, 120.98), ("Scarborough Shoal", 15.15, 117.76), ("Second Thomas Shoal", 9.73, 115.86), ("Spratly Is.", 9.5, 114.0), ("Hainan", 19.2, 109.7), ("Cam Ranh", 11.9, 109.2)],
    "korea": [("Seoul", 37.57, 126.98), ("Pyongyang", 39.02, 125.75), ("Busan", 35.18, 129.08), ("DMZ", 38.0, 127.0), ("Yongbyon", 39.8, 125.75)],
    "southasia": [("New Delhi", 28.61, 77.21), ("Islamabad", 33.68, 73.05), ("Srinagar", 34.08, 74.8), ("Mumbai", 19.08, 72.88), ("Karachi", 24.86, 67.0), ("Lahore", 31.55, 74.34)],
    "libya": [("Tripoli", 32.89, 13.19), ("Benghazi", 32.12, 20.09), ("Es Sider", 30.63, 18.35), ("Sharara field", 26.6, 12.3)],
    "sudan": [("Khartoum", 15.5, 32.56), ("Port Sudan", 19.62, 37.22), ("El Fasher", 13.63, 25.35), ("Juba", 4.85, 31.58)],
    "drc": [("Kinshasa", -4.32, 15.31), ("Goma", -1.68, 29.22), ("Lubumbashi", -11.66, 27.48), ("Kolwezi", -10.72, 25.47)],
    "venezuela": [("Caracas", 10.48, -66.9), ("Maracaibo", 10.63, -71.64), ("Georgetown", 6.8, -58.16), ("Bogota", 4.71, -74.07), ("Havana", 23.11, -82.37)],
}

SEAS = [("Black Sea", 43.5, 34.5), ("Baltic Sea", 57.5, 19.5), ("Mediterranean Sea", 35.0, 18.0), ("Red Sea", 20.5, 38.5), ("Arabian Sea", 16.0, 64.0),
        ("Persian Gulf", 27.0, 51.5), ("Gulf of Aden", 12.2, 48.0), ("North Sea", 56.0, 3.0), ("Caspian Sea", 41.5, 50.5), ("Norwegian Sea", 66.5, 3.0),
        ("Gulf of Oman", 24.5, 58.8), ("Adriatic Sea", 42.8, 15.8), ("Taiwan Strait", 24.0, 119.0), ("South China Sea", 14.0, 114.0),
        ("Sea of Japan", 40.0, 134.0), ("Yellow Sea", 36.0, 123.5), ("Caribbean Sea", 14.5, -72.0), ("Bay of Bengal", 14.0, 88.0)]
