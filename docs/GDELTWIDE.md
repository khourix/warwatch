# Wider GDELT event types against past events

Written by `warwatch/sourcestudy.py gdeltwide` to the plan fixed before the data was read ([GDELTWIDE_PLAN.md](GDELTWIDE_PLAN.md)). 3183 days of GDELT files, 2018-01-01 to 2026-10-08. Pass rule: added events p < 0.00625, original events p < 0.10, AUC above 0.55 on both.

Hit = z reached 2 in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.

| Family | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| gw_milthreat | 912 | 42% | 52 | 54% | 0.062 | 0.59 | 60 | 28% | 0.991 | 0.46 | no |
| gw_mobilise | 912 | 46% | 52 | 60% | 0.030 | 0.60 | 60 | 42% | 0.771 | 0.47 | no |
| gw_coerce | 912 | 30% | 52 | 31% | 0.500 | 0.48 | 60 | 40% | 0.062 | 0.54 | no |
| gw_material | 912 | 29% | 52 | 29% | 0.531 | 0.45 | 60 | 35% | 0.165 | 0.50 | no |
| gw_goldstein | 912 | 26% | 52 | 31% | 0.248 | 0.49 | 60 | 28% | 0.371 | 0.50 | no |
| gw_dyadhostile | 763 | 27% | 46 | 24% | 0.720 | 0.45 | 55 | 31% | 0.287 | 0.49 | no |
| gw_dyadforce | 986 | 42% | 53 | 49% | 0.199 | 0.53 | 64 | 45% | 0.363 | 0.53 | no |
| gw_dyadgoldstein | 763 | 30% | 46 | 20% | 0.962 | 0.42 | 55 | 22% | 0.936 | 0.47 | no |

## Events where the series reached z 2 or more in the 30 days before

| Family | Theatre | Date | Event | Max z | List |
|---|---|---|---|---:|---|
| gw_milthreat | southasia | 2019-02-26 | Balakot | 5.0 | original |
| gw_milthreat | libya | 2019-04-04 | Haftar Tripoli offensive | 4.4 | original |
| gw_milthreat | venezuela | 2019-04-30 | Guaido uprising attempt | 4.7 | added |
| gw_milthreat | iran | 2019-05-12 | Fujairah tanker sabotage | 2.1 | original |
| gw_milthreat | yemen | 2019-05-14 | Houthi drones on Saudi East-West pipeline | 3.5 | added |
| gw_milthreat | iran | 2019-06-13 | Gulf of Oman tanker attacks | 5.0 | original |
| gw_milthreat | israel | 2019-10-09 | Turkey launches Operation Peace Spring in northeast Syria | 2.9 | added |
| gw_milthreat | iran | 2020-11-27 | Nuclear scientist Fakhrizadeh assassinated near Tehran | 4.1 | added |
| gw_milthreat | yemen | 2021-02-07 | Houthi Marib offensive escalates | 3.0 | added |
| gw_milthreat | europe_east | 2021-09-10 | Zapad 2021 | 3.8 | original |
| gw_milthreat | europe_east | 2022-02-10 | Allied Resolve 2022 (Russia-Belarus) | 5.0 | added |
| gw_milthreat | ukraine | 2022-02-24 | Russia full-scale invasion | 4.9 | original |
| gw_milthreat | korea | 2022-03-24 | First ICBM since 2017 | 4.4 | original |
| gw_milthreat | taiwan | 2022-08-04 | PLA drills after Pelosi | 2.6 | original |
| gw_milthreat | israel | 2022-08-05 | Operation Breaking Dawn in Gaza | 4.3 | added |
| gw_milthreat | europe_east | 2022-11-15 | Przewodow missile | 2.9 | original |
| gw_milthreat | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.6 | added |
| gw_milthreat | iran | 2023-04-27 | Iran seizes tanker Advantage Sweet | 2.9 | added |
| gw_milthreat | libya | 2023-08-14 | Tripoli clashes (444 Brigade) | 4.4 | added |
| gw_milthreat | iran | 2023-10-17 | Militia attacks on US forces in Iraq and Syria begin | 5.0 | added |
| gw_milthreat | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 2.5 | added |
| gw_milthreat | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| gw_milthreat | scs | 2023-12-09 | Water cannon at Scarborough and ramming at Second Thomas Shoal | 5.0 | added |
| gw_milthreat | korea | 2024-01-05 | North Korean artillery fire near Yeonpyeong | 5.0 | added |
| gw_milthreat | iran | 2024-01-16 | Iran-Pakistan border strikes | 4.6 | original |
| gw_milthreat | scs | 2024-03-05 | Water cannon and collision at Second Thomas Shoal | 5.0 | added |
| gw_milthreat | iran | 2024-04-13 | Iran first direct attack on Israel | 5.0 | original |
| gw_milthreat | scs | 2024-06-17 | Second Thomas Shoal boarding | 3.7 | original |
| gw_milthreat | iran | 2024-07-31 | Haniyeh assassinated in Tehran | 2.2 | original |
| gw_milthreat | libya | 2024-08-26 | Oil shutdown over central bank | 5.0 | original |
| gw_milthreat | ukraine | 2024-11-21 | Oreshnik IRBM on Dnipro | 2.5 | original |
| gw_milthreat | europe_east | 2024-12-25 | Estlink 2 cable damage | 2.1 | original |
| gw_milthreat | drc | 2025-03-13 | Bisie tin mine halted | 4.4 | original |
| gw_milthreat | sudan | 2025-05-04 | Drone strikes on Port Sudan | 3.0 | original |
| gw_milthreat | southasia | 2025-05-07 | Operation Sindoor | 5.0 | original |
| gw_milthreat | venezuela | 2025-09-02 | First US boat strike | 5.0 | original |
| gw_milthreat | sudan | 2025-10-26 | El Fasher falls | 2.4 | original |
| gw_milthreat | venezuela | 2025-12-10 | US seizes tanker Skipper | 5.0 | original |
| gw_milthreat | taiwan | 2025-12-29 | Justice Mission-2025 | 3.9 | original |
| gw_milthreat | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 3.4 | added |
| gw_milthreat | iran | 2026-02-28 | US-Israel war on Iran | 5.0 | original |
| gw_milthreat | israel | 2026-03-02 | Hezbollah-Israel war resumes | 2.6 | original |
| gw_milthreat | yemen | 2026-03-28 | Houthis join 2026 Iran war | 3.0 | original |
| gw_milthreat | iran | 2026-07-08 | Ceasefire collapse in Hormuz | 2.2 | original |
| gw_milthreat | scs | 2026-07-20 | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon at Scarborough | 2.4 | added |
| gw_mobilise | venezuela | 2019-04-30 | Guaido uprising attempt | 4.6 | added |
| gw_mobilise | israel | 2019-05-04 | May 2019 Gaza-Israel clashes (700 rockets) | 2.9 | added |
| gw_mobilise | iran | 2019-05-12 | Fujairah tanker sabotage | 5.0 | original |
| gw_mobilise | iran | 2019-06-13 | Gulf of Oman tanker attacks | 5.0 | original |
| gw_mobilise | yemen | 2019-08-07 | STC seizes Aden from government forces | 3.1 | added |
| gw_mobilise | iran | 2019-09-14 | Abqaiq-Khurais attack | 2.0 | original |
| gw_mobilise | israel | 2019-11-12 | Operation Black Belt (PIJ commander killed) | 2.3 | added |
| gw_mobilise | iran | 2019-12-29 | US strikes Kataib Hezbollah after K-1 attack | 2.3 | added |
| gw_mobilise | libya | 2020-01-18 | Oil port blockade | 5.0 | original |
| gw_mobilise | libya | 2020-03-25 | GNA Operation Peace Storm | 2.4 | added |
| gw_mobilise | korea | 2020-06-16 | Kaesong liaison office blown up | 4.8 | original |
| gw_mobilise | iran | 2020-11-27 | Nuclear scientist Fakhrizadeh assassinated near Tehran | 5.0 | added |
| gw_mobilise | yemen | 2021-02-07 | Houthi Marib offensive escalates | 2.6 | added |
| gw_mobilise | israel | 2021-05-10 | 11-day Gaza war | 3.1 | original |
| gw_mobilise | europe_east | 2021-09-10 | Zapad 2021 | 4.1 | original |
| gw_mobilise | europe_east | 2022-02-10 | Allied Resolve 2022 (Russia-Belarus) | 5.0 | added |
| gw_mobilise | ukraine | 2022-02-24 | Russia full-scale invasion | 5.0 | original |
| gw_mobilise | yemen | 2022-03-19 | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | 3.3 | added |
| gw_mobilise | korea | 2022-03-24 | First ICBM since 2017 | 2.1 | original |
| gw_mobilise | libya | 2022-08-27 | Tripoli clashes over Bashagha government | 2.3 | added |
| gw_mobilise | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 3.4 | added |
| gw_mobilise | korea | 2022-10-04 | Missile over Japan | 2.9 | original |
| gw_mobilise | europe_east | 2022-11-15 | Przewodow missile | 5.0 | original |
| gw_mobilise | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.3 | added |
| gw_mobilise | taiwan | 2023-04-08 | Joint Sword | 2.8 | original |
| gw_mobilise | sudan | 2023-04-15 | SAF-RSF war | 2.6 | original |
| gw_mobilise | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 4.3 | added |
| gw_mobilise | scs | 2023-08-05 | Water cannon on Philippine resupply at Second Thomas Shoal | 2.3 | added |
| gw_mobilise | taiwan | 2023-08-19 | PLA drills after Lai stopover in the US | 4.6 | added |
| gw_mobilise | israel | 2023-10-07 | Hamas attack | 5.0 | original |
| gw_mobilise | iran | 2023-10-17 | Militia attacks on US forces in Iraq and Syria begin | 3.6 | added |
| gw_mobilise | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 3.3 | added |
| gw_mobilise | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| gw_mobilise | sudan | 2023-12-15 | RSF Gezira offensive; Wad Madani falls | 4.1 | added |
| gw_mobilise | korea | 2024-01-05 | North Korean artillery fire near Yeonpyeong | 2.1 | added |
| gw_mobilise | scs | 2024-03-05 | Water cannon and collision at Second Thomas Shoal | 2.2 | added |
| gw_mobilise | iran | 2024-04-13 | Iran first direct attack on Israel | 3.9 | original |
| gw_mobilise | ukraine | 2024-05-10 | Russian Kharkiv offensive | 5.0 | added |
| gw_mobilise | scs | 2024-06-17 | Second Thomas Shoal boarding | 2.9 | original |
| gw_mobilise | iran | 2024-07-31 | Haniyeh assassinated in Tehran | 2.7 | original |
| gw_mobilise | libya | 2024-08-26 | Oil shutdown over central bank | 5.0 | original |
| gw_mobilise | taiwan | 2024-10-14 | Joint Sword-2024B | 3.7 | original |
| gw_mobilise | korea | 2024-10-15 | North Korea blows up inter-Korean roads | 3.9 | added |
| gw_mobilise | ukraine | 2024-11-21 | Oreshnik IRBM on Dnipro | 4.8 | original |
| gw_mobilise | yemen | 2024-12-19 | Israel strikes Sanaa and Hodeidah ports and power stations | 3.4 | added |
| gw_mobilise | drc | 2025-03-13 | Bisie tin mine halted | 5.0 | original |
| gw_mobilise | israel | 2025-03-18 | Israel ends Gaza ceasefire | 3.6 | original |
| gw_mobilise | sudan | 2025-05-04 | Drone strikes on Port Sudan | 2.3 | original |
| gw_mobilise | southasia | 2025-05-07 | Operation Sindoor | 5.0 | original |
| gw_mobilise | venezuela | 2025-09-02 | First US boat strike | 5.0 | original |
| gw_mobilise | europe_east | 2025-09-09 | Russian drones into Poland | 4.7 | original |
| gw_mobilise | venezuela | 2025-12-10 | US seizes tanker Skipper | 5.0 | original |
| gw_mobilise | iran | 2026-02-28 | US-Israel war on Iran | 5.0 | original |
| gw_mobilise | israel | 2026-03-02 | Hezbollah-Israel war resumes | 3.9 | original |
| gw_mobilise | yemen | 2026-03-28 | Houthis join 2026 Iran war | 5.0 | original |
| gw_mobilise | yemen | 2026-09-03 | Houthi west-coast offensive; Mocha and Mayun Island taken | 3.2 | added |
| gw_coerce | libya | 2019-04-04 | Haftar Tripoli offensive | 3.0 | original |
| gw_coerce | yemen | 2019-05-14 | Houthi drones on Saudi East-West pipeline | 2.4 | added |
| gw_coerce | yemen | 2019-08-07 | STC seizes Aden from government forces | 2.5 | added |
| gw_coerce | israel | 2019-08-24 | Israeli strike on Quds Force drone team near Damascus and drones in Beirut; Hezbollah ATGM reply 1 Sept | 3.7 | added |
| gw_coerce | iran | 2020-03-12 | US strikes Kataib Hezbollah after Camp Taji attack | 2.7 | added |
| gw_coerce | libya | 2020-03-25 | GNA Operation Peace Storm | 4.5 | added |
| gw_coerce | korea | 2020-06-16 | Kaesong liaison office blown up | 2.2 | original |
| gw_coerce | yemen | 2022-01-02 | Houthis seize UAE-flagged Rwabee | 5.0 | added |
| gw_coerce | yemen | 2022-03-19 | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | 5.0 | added |
| gw_coerce | korea | 2022-03-24 | First ICBM since 2017 | 2.1 | original |
| gw_coerce | iran | 2022-05-27 | Iran seizes two Greek tankers | 4.2 | added |
| gw_coerce | libya | 2022-08-27 | Tripoli clashes over Bashagha government | 2.2 | added |
| gw_coerce | europe_east | 2022-09-26 | Nord Stream pipelines sabotaged | 2.3 | added |
| gw_coerce | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 4.0 | added |
| gw_coerce | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.8 | added |
| gw_coerce | taiwan | 2023-04-08 | Joint Sword | 2.6 | original |
| gw_coerce | scs | 2023-08-05 | Water cannon on Philippine resupply at Second Thomas Shoal | 2.2 | added |
| gw_coerce | libya | 2023-08-14 | Tripoli clashes (444 Brigade) | 3.2 | added |
| gw_coerce | europe_east | 2023-10-08 | Balticconnector pipeline and cable damaged | 5.0 | added |
| gw_coerce | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 2.4 | added |
| gw_coerce | korea | 2023-11-21 | North Korean spy satellite launch and end of 2018 military accord | 2.7 | added |
| gw_coerce | korea | 2024-01-05 | North Korean artillery fire near Yeonpyeong | 3.0 | added |
| gw_coerce | scs | 2024-03-05 | Water cannon and collision at Second Thomas Shoal | 2.6 | added |
| gw_coerce | taiwan | 2024-05-23 | Joint Sword-2024A | 2.4 | original |
| gw_coerce | scs | 2024-06-17 | Second Thomas Shoal boarding | 5.0 | original |
| gw_coerce | yemen | 2024-07-20 | Israel strikes Hodeidah | 4.2 | original |
| gw_coerce | ukraine | 2024-08-06 | Ukraine Kursk offensive | 3.9 | original |
| gw_coerce | scs | 2024-08-19 | Collisions at Sabina Shoal | 3.1 | added |
| gw_coerce | libya | 2024-08-26 | Oil shutdown over central bank | 5.0 | original |
| gw_coerce | taiwan | 2024-10-14 | Joint Sword-2024B | 4.2 | original |
| gw_coerce | korea | 2024-10-15 | North Korea blows up inter-Korean roads | 2.2 | added |
| gw_coerce | israel | 2024-11-27 | HTS offensive and fall of Assad | 4.5 | original |
| gw_coerce | yemen | 2024-12-19 | Israel strikes Sanaa and Hodeidah ports and power stations | 2.7 | added |
| gw_coerce | yemen | 2025-03-15 | US Rough Rider campaign | 5.0 | original |
| gw_coerce | israel | 2025-03-18 | Israel ends Gaza ceasefire | 4.5 | original |
| gw_coerce | taiwan | 2025-04-01 | Strait Thunder-2025A | 2.6 | original |
| gw_coerce | sudan | 2025-05-04 | Drone strikes on Port Sudan | 3.6 | original |
| gw_coerce | iran | 2025-06-13 | Twelve-Day War | 2.2 | original |
| gw_coerce | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 2.3 | added |
| gw_coerce | scs | 2026-07-20 | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon at Scarborough | 2.9 | added |
| gw_material | southasia | 2019-02-26 | Balakot | 2.4 | original |
| gw_material | iran | 2019-12-29 | US strikes Kataib Hezbollah after K-1 attack | 4.9 | added |
| gw_material | iran | 2020-03-12 | US strikes Kataib Hezbollah after Camp Taji attack | 4.7 | added |
| gw_material | libya | 2020-03-25 | GNA Operation Peace Storm | 2.2 | added |
| gw_material | venezuela | 2020-05-03 | Operation Gideon incursion | 2.4 | added |
| gw_material | iran | 2020-11-27 | Nuclear scientist Fakhrizadeh assassinated near Tehran | 2.6 | added |
| gw_material | israel | 2021-05-10 | 11-day Gaza war | 3.2 | original |
| gw_material | europe_east | 2021-09-10 | Zapad 2021 | 3.3 | original |
| gw_material | yemen | 2022-01-02 | Houthis seize UAE-flagged Rwabee | 2.4 | added |
| gw_material | korea | 2022-03-24 | First ICBM since 2017 | 3.3 | original |
| gw_material | iran | 2022-05-27 | Iran seizes two Greek tankers | 2.3 | added |
| gw_material | libya | 2022-08-27 | Tripoli clashes over Bashagha government | 2.9 | added |
| gw_material | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 3.2 | added |
| gw_material | korea | 2022-10-04 | Missile over Japan | 3.1 | original |
| gw_material | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.2 | added |
| gw_material | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 3.8 | added |
| gw_material | ukraine | 2023-06-04 | Ukrainian summer counteroffensive begins | 2.2 | added |
| gw_material | taiwan | 2023-08-19 | PLA drills after Lai stopover in the US | 3.4 | added |
| gw_material | europe_east | 2023-10-08 | Balticconnector pipeline and cable damaged | 3.1 | added |
| gw_material | yemen | 2023-11-19 | Red Sea attacks begin | 4.9 | original |
| gw_material | scs | 2023-12-09 | Water cannon at Scarborough and ramming at Second Thomas Shoal | 2.6 | added |
| gw_material | iran | 2024-01-16 | Iran-Pakistan border strikes | 3.6 | original |
| gw_material | scs | 2024-03-05 | Water cannon and collision at Second Thomas Shoal | 2.1 | added |
| gw_material | iran | 2024-04-13 | Iran first direct attack on Israel | 3.0 | original |
| gw_material | scs | 2024-06-17 | Second Thomas Shoal boarding | 2.7 | original |
| gw_material | israel | 2024-07-30 | Israel kills Fuad Shukr in Beirut after Majdal Shams | 2.3 | added |
| gw_material | libya | 2024-08-26 | Oil shutdown over central bank | 5.0 | original |
| gw_material | taiwan | 2024-10-14 | Joint Sword-2024B | 2.4 | original |
| gw_material | korea | 2024-10-15 | North Korea blows up inter-Korean roads | 2.1 | added |
| gw_material | israel | 2024-11-27 | HTS offensive and fall of Assad | 2.7 | original |
| gw_material | southasia | 2025-05-07 | Operation Sindoor | 4.3 | original |
| gw_material | europe_east | 2025-09-09 | Russian drones into Poland | 2.2 | original |
| gw_material | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 2.9 | added |
| gw_material | iran | 2026-02-28 | US-Israel war on Iran | 2.6 | original |
| gw_material | scs | 2026-07-20 | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon at Scarborough | 2.4 | added |
| gw_material | yemen | 2026-09-03 | Houthi west-coast offensive; Mocha and Mayun Island taken | 2.5 | added |
| gw_goldstein | southasia | 2019-02-26 | Balakot | 2.4 | original |
| gw_goldstein | yemen | 2019-08-07 | STC seizes Aden from government forces | 2.2 | added |
| gw_goldstein | iran | 2019-12-29 | US strikes Kataib Hezbollah after K-1 attack | 4.9 | added |
| gw_goldstein | iran | 2020-03-12 | US strikes Kataib Hezbollah after Camp Taji attack | 3.3 | added |
| gw_goldstein | korea | 2020-06-16 | Kaesong liaison office blown up | 2.2 | original |
| gw_goldstein | iran | 2020-11-27 | Nuclear scientist Fakhrizadeh assassinated near Tehran | 2.5 | added |
| gw_goldstein | israel | 2021-05-10 | 11-day Gaza war | 2.7 | original |
| gw_goldstein | europe_east | 2021-09-10 | Zapad 2021 | 3.4 | original |
| gw_goldstein | yemen | 2022-01-02 | Houthis seize UAE-flagged Rwabee | 2.4 | added |
| gw_goldstein | korea | 2022-03-24 | First ICBM since 2017 | 3.5 | original |
| gw_goldstein | iran | 2022-05-27 | Iran seizes two Greek tankers | 2.4 | added |
| gw_goldstein | libya | 2022-08-27 | Tripoli clashes over Bashagha government | 2.5 | added |
| gw_goldstein | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 4.8 | added |
| gw_goldstein | korea | 2022-10-04 | Missile over Japan | 2.4 | original |
| gw_goldstein | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.4 | added |
| gw_goldstein | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 3.9 | added |
| gw_goldstein | europe_east | 2023-10-08 | Balticconnector pipeline and cable damaged | 3.4 | added |
| gw_goldstein | yemen | 2023-11-19 | Red Sea attacks begin | 3.8 | original |
| gw_goldstein | scs | 2023-12-09 | Water cannon at Scarborough and ramming at Second Thomas Shoal | 3.9 | added |
| gw_goldstein | korea | 2024-01-05 | North Korean artillery fire near Yeonpyeong | 2.1 | added |
| gw_goldstein | iran | 2024-01-16 | Iran-Pakistan border strikes | 3.1 | original |
| gw_goldstein | scs | 2024-03-05 | Water cannon and collision at Second Thomas Shoal | 2.8 | added |
| gw_goldstein | iran | 2024-04-13 | Iran first direct attack on Israel | 3.6 | original |
| gw_goldstein | scs | 2024-06-17 | Second Thomas Shoal boarding | 3.5 | original |
| gw_goldstein | libya | 2024-08-26 | Oil shutdown over central bank | 3.2 | original |
| gw_goldstein | sudan | 2025-05-04 | Drone strikes on Port Sudan | 2.5 | original |
| gw_goldstein | southasia | 2025-05-07 | Operation Sindoor | 4.5 | original |
| gw_goldstein | taiwan | 2025-12-29 | Justice Mission-2025 | 2.2 | original |
| gw_goldstein | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 2.4 | added |
| gw_goldstein | iran | 2026-02-28 | US-Israel war on Iran | 3.9 | original |
| gw_goldstein | iran | 2026-07-08 | Ceasefire collapse in Hormuz | 2.6 | original |
| gw_goldstein | scs | 2026-07-20 | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon at Scarborough | 2.6 | added |
| gw_goldstein | yemen | 2026-09-03 | Houthi west-coast offensive; Mocha and Mayun Island taken | 2.7 | added |
| gw_dyadhostile | iran | 2019-05-12 | Fujairah tanker sabotage | 2.2 | original |
| gw_dyadhostile | iran | 2019-09-14 | Abqaiq-Khurais attack | 2.7 | original |
| gw_dyadhostile | iran | 2019-12-29 | US strikes Kataib Hezbollah after K-1 attack | 2.9 | added |
| gw_dyadhostile | iran | 2020-03-12 | US strikes Kataib Hezbollah after Camp Taji attack | 2.0 | added |
| gw_dyadhostile | venezuela | 2020-05-03 | Operation Gideon incursion | 2.3 | added |
| gw_dyadhostile | korea | 2020-06-16 | Kaesong liaison office blown up | 4.3 | original |
| gw_dyadhostile | israel | 2021-05-10 | 11-day Gaza war | 2.4 | original |
| gw_dyadhostile | europe_east | 2021-09-10 | Zapad 2021 | 2.4 | original |
| gw_dyadhostile | yemen | 2022-01-02 | Houthis seize UAE-flagged Rwabee | 2.8 | added |
| gw_dyadhostile | korea | 2022-03-24 | First ICBM since 2017 | 3.4 | original |
| gw_dyadhostile | ukraine | 2022-08-29 | Ukraine launches Kherson counteroffensive | 2.2 | added |
| gw_dyadhostile | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.5 | added |
| gw_dyadhostile | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 3.3 | added |
| gw_dyadhostile | ukraine | 2023-06-04 | Ukrainian summer counteroffensive begins | 2.5 | added |
| gw_dyadhostile | scs | 2023-08-05 | Water cannon on Philippine resupply at Second Thomas Shoal | 2.0 | added |
| gw_dyadhostile | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 3.2 | added |
| gw_dyadhostile | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| gw_dyadhostile | korea | 2023-11-21 | North Korean spy satellite launch and end of 2018 military accord | 2.3 | added |
| gw_dyadhostile | iran | 2024-01-16 | Iran-Pakistan border strikes | 3.6 | original |
| gw_dyadhostile | scs | 2024-03-05 | Water cannon and collision at Second Thomas Shoal | 2.0 | added |
| gw_dyadhostile | scs | 2024-06-17 | Second Thomas Shoal boarding | 2.7 | original |
| gw_dyadhostile | korea | 2024-10-15 | North Korea blows up inter-Korean roads | 2.5 | added |
| gw_dyadhostile | europe_east | 2024-11-17 | Baltic Sea cables cut (BCS and C-Lion1) | 2.8 | added |
| gw_dyadhostile | taiwan | 2025-04-01 | Strait Thunder-2025A | 3.4 | original |
| gw_dyadhostile | southasia | 2025-05-07 | Operation Sindoor | 2.6 | original |
| gw_dyadhostile | europe_east | 2025-11-15 | Explosive sabotage of Warsaw-Lublin rail line by Russian-recruited agents | 2.3 | added |
| gw_dyadhostile | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 2.6 | added |
| gw_dyadhostile | scs | 2026-07-20 | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon at Scarborough | 3.2 | added |
| gw_dyadforce | southasia | 2019-02-26 | Balakot | 5.0 | original |
| gw_dyadforce | venezuela | 2019-04-30 | Guaido uprising attempt | 4.4 | added |
| gw_dyadforce | iran | 2019-06-13 | Gulf of Oman tanker attacks | 5.0 | original |
| gw_dyadforce | iran | 2019-12-29 | US strikes Kataib Hezbollah after K-1 attack | 3.6 | added |
| gw_dyadforce | libya | 2020-01-18 | Oil port blockade | 4.8 | original |
| gw_dyadforce | venezuela | 2020-05-03 | Operation Gideon incursion | 5.0 | added |
| gw_dyadforce | yemen | 2021-02-07 | Houthi Marib offensive escalates | 5.0 | added |
| gw_dyadforce | israel | 2021-05-10 | 11-day Gaza war | 3.2 | original |
| gw_dyadforce | europe_east | 2021-09-10 | Zapad 2021 | 2.1 | original |
| gw_dyadforce | europe_east | 2022-02-10 | Allied Resolve 2022 (Russia-Belarus) | 2.6 | added |
| gw_dyadforce | ukraine | 2022-02-24 | Russia full-scale invasion | 5.0 | original |
| gw_dyadforce | yemen | 2022-03-19 | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | 5.0 | added |
| gw_dyadforce | korea | 2022-03-24 | First ICBM since 2017 | 2.0 | original |
| gw_dyadforce | drc | 2022-03-27 | M23 resurgence in North Kivu | 3.4 | added |
| gw_dyadforce | ukraine | 2022-04-13 | Russian flagship Moskva hit by Neptune missiles, sinks next day | 5.0 | added |
| gw_dyadforce | taiwan | 2022-08-04 | PLA drills after Pelosi | 5.0 | original |
| gw_dyadforce | israel | 2022-08-05 | Operation Breaking Dawn in Gaza | 2.3 | added |
| gw_dyadforce | libya | 2022-08-27 | Tripoli clashes over Bashagha government | 2.4 | added |
| gw_dyadforce | europe_east | 2022-09-26 | Nord Stream pipelines sabotaged | 3.9 | added |
| gw_dyadforce | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 2.3 | added |
| gw_dyadforce | korea | 2022-10-04 | Missile over Japan | 5.0 | original |
| gw_dyadforce | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.2 | added |
| gw_dyadforce | taiwan | 2023-04-08 | Joint Sword | 5.0 | original |
| gw_dyadforce | sudan | 2023-04-15 | SAF-RSF war | 4.7 | original |
| gw_dyadforce | iran | 2023-04-27 | Iran seizes tanker Advantage Sweet | 2.6 | added |
| gw_dyadforce | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 4.1 | added |
| gw_dyadforce | scs | 2023-08-05 | Water cannon on Philippine resupply at Second Thomas Shoal | 5.0 | added |
| gw_dyadforce | libya | 2023-08-14 | Tripoli clashes (444 Brigade) | 5.0 | added |
| gw_dyadforce | europe_east | 2023-10-08 | Balticconnector pipeline and cable damaged | 3.6 | added |
| gw_dyadforce | iran | 2023-10-17 | Militia attacks on US forces in Iraq and Syria begin | 5.0 | added |
| gw_dyadforce | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 5.0 | added |
| gw_dyadforce | scs | 2023-10-22 | Collisions at Second Thomas Shoal | 5.0 | added |
| gw_dyadforce | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| gw_dyadforce | scs | 2023-12-09 | Water cannon at Scarborough and ramming at Second Thomas Shoal | 3.6 | added |
| gw_dyadforce | korea | 2024-01-05 | North Korean artillery fire near Yeonpyeong | 3.0 | added |
| gw_dyadforce | iran | 2024-01-16 | Iran-Pakistan border strikes | 2.8 | original |
| gw_dyadforce | israel | 2024-04-01 | Damascus consulate strike | 2.3 | original |
| gw_dyadforce | iran | 2024-04-13 | Iran first direct attack on Israel | 5.0 | original |
| gw_dyadforce | scs | 2024-06-17 | Second Thomas Shoal boarding | 4.6 | original |
| gw_dyadforce | sudan | 2024-09-26 | SAF offensive in Khartoum | 4.0 | added |
| gw_dyadforce | iran | 2024-10-01 | Iran 200 missiles at Israel | 2.4 | original |
| gw_dyadforce | taiwan | 2024-10-14 | Joint Sword-2024B | 2.8 | original |
| gw_dyadforce | drc | 2025-03-13 | Bisie tin mine halted | 5.0 | original |
| gw_dyadforce | sudan | 2025-05-04 | Drone strikes on Port Sudan | 3.4 | original |
| gw_dyadforce | southasia | 2025-05-07 | Operation Sindoor | 5.0 | original |
| gw_dyadforce | libya | 2025-05-12 | Tripoli clashes after al-Kikli killed | 5.0 | added |
| gw_dyadforce | iran | 2025-06-13 | Twelve-Day War | 3.1 | original |
| gw_dyadforce | sudan | 2025-10-26 | El Fasher falls | 5.0 | original |
| gw_dyadforce | europe_east | 2025-11-15 | Explosive sabotage of Warsaw-Lublin rail line by Russian-recruited agents | 5.0 | added |
| gw_dyadforce | yemen | 2025-12-03 | STC seizes Hadramawt and Mahra from government forces | 3.0 | added |
| gw_dyadforce | venezuela | 2025-12-10 | US seizes tanker Skipper | 2.3 | original |
| gw_dyadforce | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 2.5 | added |
| gw_dyadforce | iran | 2026-02-28 | US-Israel war on Iran | 5.0 | original |
| gw_dyadforce | iran | 2026-07-08 | Ceasefire collapse in Hormuz | 3.3 | original |
| gw_dyadforce | yemen | 2026-09-03 | Houthi west-coast offensive; Mocha and Mayun Island taken | 5.0 | added |
| gw_dyadgoldstein | iran | 2019-09-14 | Abqaiq-Khurais attack | 2.3 | original |
| gw_dyadgoldstein | iran | 2020-03-12 | US strikes Kataib Hezbollah after Camp Taji attack | 3.0 | added |
| gw_dyadgoldstein | korea | 2020-06-16 | Kaesong liaison office blown up | 2.8 | original |
| gw_dyadgoldstein | israel | 2021-05-10 | 11-day Gaza war | 3.0 | original |
| gw_dyadgoldstein | europe_east | 2021-09-10 | Zapad 2021 | 2.5 | original |
| gw_dyadgoldstein | yemen | 2022-01-02 | Houthis seize UAE-flagged Rwabee | 2.7 | added |
| gw_dyadgoldstein | yemen | 2022-03-19 | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | 2.1 | added |
| gw_dyadgoldstein | korea | 2022-03-24 | First ICBM since 2017 | 3.7 | original |
| gw_dyadgoldstein | iran | 2022-05-27 | Iran seizes two Greek tankers | 2.7 | added |
| gw_dyadgoldstein | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 2.5 | added |
| gw_dyadgoldstein | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 2.8 | added |
| gw_dyadgoldstein | ukraine | 2023-06-04 | Ukrainian summer counteroffensive begins | 3.1 | added |
| gw_dyadgoldstein | scs | 2023-08-05 | Water cannon on Philippine resupply at Second Thomas Shoal | 2.1 | added |
| gw_dyadgoldstein | europe_east | 2023-10-08 | Balticconnector pipeline and cable damaged | 2.8 | added |
| gw_dyadgoldstein | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 2.3 | added |
| gw_dyadgoldstein | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| gw_dyadgoldstein | iran | 2024-01-16 | Iran-Pakistan border strikes | 3.2 | original |
| gw_dyadgoldstein | scs | 2024-06-17 | Second Thomas Shoal boarding | 3.0 | original |
| gw_dyadgoldstein | taiwan | 2025-04-01 | Strait Thunder-2025A | 3.3 | original |
| gw_dyadgoldstein | europe_east | 2025-11-15 | Explosive sabotage of Warsaw-Lublin rail line by Russian-recruited agents | 2.6 | added |
| gw_dyadgoldstein | europe_east | 2025-12-31 | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | 3.4 | added |
