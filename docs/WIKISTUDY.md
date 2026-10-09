# Wikipedia page views against past events

Written by `warwatch/wikistudy.py` to the plan fixed before the data was read ([WIKISTUDY_PLAN.md](WIKISTUDY_PLAN.md)). Hit = z reached 2 in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.

| Family | Original events | Hit rate | False-alarm rate | p | AUC | Added events | Hit rate | p | AUC | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| wiki | 54 | 50% | 35% | 0.016 | 0.60 | 65 | 40% | 0.233 | 0.53 | no |
| wikiloc | 54 | 33% | 27% | 0.197 | 0.50 | 65 | 32% | 0.218 | 0.58 | no |

## Events where views reached z 2 or more in the 30 days before

| Family | Theatre | Date | Event | Max z | List |
|---|---|---|---|---:|---|
| wiki | southasia | 2019-02-26 | Balakot | 5.0 | original |
| wiki | venezuela | 2019-04-30 | Guaido uprising attempt | 4.3 | added |
| wiki | israel | 2019-05-04 | May 2019 Gaza-Israel clashes (700 rockets) | 4.4 | added |
| wiki | iran | 2019-05-12 | Fujairah tanker sabotage | 4.9 | original |
| wiki | iran | 2019-06-13 | Gulf of Oman tanker attacks | 5.0 | original |
| wiki | israel | 2019-08-24 | Israeli strike on Quds Force drone team near Damascus and drones in Beirut; Hezbollah ATGM reply 1 Sept | 2.2 | added |
| wiki | israel | 2019-10-09 | Turkey launches Operation Peace Spring in northeast Syria | 3.0 | added |
| wiki | libya | 2020-01-18 | Oil port blockade | 5.0 | original |
| wiki | israel | 2020-02-27 | Balyun airstrike kills 33 Turkish soldiers; Turkey strikes Syrian forces | 3.1 | added |
| wiki | venezuela | 2020-05-03 | Operation Gideon incursion | 4.2 | added |
| wiki | korea | 2020-06-16 | Kaesong liaison office blown up | 4.3 | original |
| wiki | yemen | 2021-02-07 | Houthi Marib offensive escalates | 2.3 | added |
| wiki | iran | 2021-06-27 | US strikes militias on Iraq-Syria border | 5.0 | added |
| wiki | iran | 2021-07-29 | Drone attack on tanker Mercer Street | 2.8 | added |
| wiki | europe_east | 2021-09-10 | Zapad 2021 | 2.4 | original |
| wiki | europe_east | 2022-02-10 | Allied Resolve 2022 (Russia-Belarus) | 5.0 | added |
| wiki | ukraine | 2022-02-24 | Russia full-scale invasion | 5.0 | original |
| wiki | iran | 2022-03-13 | IRGC missiles on Erbil | 2.9 | added |
| wiki | yemen | 2022-03-19 | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | 5.0 | added |
| wiki | korea | 2022-03-24 | First ICBM since 2017 | 5.0 | original |
| wiki | drc | 2022-03-27 | M23 resurgence in North Kivu | 2.2 | added |
| wiki | ukraine | 2022-04-13 | Russian flagship Moskva hit by Neptune missiles, sinks next day | 5.0 | added |
| wiki | taiwan | 2022-08-04 | PLA drills after Pelosi | 5.0 | original |
| wiki | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 5.0 | added |
| wiki | sudan | 2023-04-15 | SAF-RSF war | 5.0 | original |
| wiki | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 5.0 | added |
| wiki | ukraine | 2023-06-04 | Ukrainian summer counteroffensive begins | 4.1 | added |
| wiki | ukraine | 2023-07-17 | Russia quits grain deal and strikes Odesa ports | 5.0 | original |
| wiki | scs | 2023-08-05 | Water cannon on Philippine resupply at Second Thomas Shoal | 5.0 | added |
| wiki | iran | 2023-10-17 | Militia attacks on US forces in Iraq and Syria begin | 5.0 | added |
| wiki | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 5.0 | added |
| wiki | scs | 2023-10-22 | Collisions at Second Thomas Shoal | 5.0 | added |
| wiki | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| wiki | sudan | 2023-12-15 | RSF Gezira offensive; Wad Madani falls | 3.1 | added |
| wiki | iran | 2024-01-16 | Iran-Pakistan border strikes | 5.0 | original |
| wiki | israel | 2024-04-01 | Damascus consulate strike | 3.6 | original |
| wiki | iran | 2024-04-13 | Iran first direct attack on Israel | 5.0 | original |
| wiki | taiwan | 2024-05-23 | Joint Sword-2024A | 3.8 | original |
| wiki | sudan | 2024-09-26 | SAF offensive in Khartoum | 5.0 | added |
| wiki | iran | 2024-10-01 | Iran 200 missiles at Israel | 2.6 | original |
| wiki | drc | 2025-03-13 | Bisie tin mine halted | 5.0 | original |
| wiki | sudan | 2025-05-04 | Drone strikes on Port Sudan | 4.5 | original |
| wiki | yemen | 2025-05-05 | Israel strikes Hodeidah port, then Sanaa airport (6 May) | 4.0 | added |
| wiki | southasia | 2025-05-07 | Operation Sindoor | 5.0 | original |
| wiki | libya | 2025-05-12 | Tripoli clashes after al-Kikli killed | 2.2 | added |
| wiki | yemen | 2025-07-06 | Magic Seas and Eternity C sunk | 5.0 | original |
| wiki | israel | 2025-07-14 | Israel strikes Syrian forces in Sweida, then defence ministry in Damascus | 5.0 | added |
| wiki | venezuela | 2025-09-02 | First US boat strike | 5.0 | original |
| wiki | venezuela | 2025-12-10 | US seizes tanker Skipper | 5.0 | original |
| wiki | taiwan | 2025-12-29 | Justice Mission-2025 | 2.4 | original |
| wiki | iran | 2026-02-28 | US-Israel war on Iran | 5.0 | original |
| wiki | yemen | 2026-03-28 | Houthis join 2026 Iran war | 5.0 | original |
| wiki | iran | 2026-07-08 | Ceasefire collapse in Hormuz | 3.6 | original |
| wikiloc | southasia | 2019-02-26 | Balakot | 5.0 | original |
| wikiloc | libya | 2019-04-04 | Haftar Tripoli offensive | 2.9 | original |
| wikiloc | israel | 2019-05-04 | May 2019 Gaza-Israel clashes (700 rockets) | 4.0 | added |
| wikiloc | israel | 2019-10-09 | Turkey launches Operation Peace Spring in northeast Syria | 5.0 | added |
| wikiloc | israel | 2019-11-12 | Operation Black Belt (PIJ commander killed) | 5.0 | added |
| wikiloc | libya | 2020-01-18 | Oil port blockade | 5.0 | original |
| wikiloc | iran | 2020-03-12 | US strikes Kataib Hezbollah after Camp Taji attack | 2.4 | added |
| wikiloc | venezuela | 2020-05-03 | Operation Gideon incursion | 3.1 | added |
| wikiloc | iran | 2020-11-27 | Nuclear scientist Fakhrizadeh assassinated near Tehran | 2.4 | added |
| wikiloc | israel | 2021-05-10 | 11-day Gaza war | 2.3 | original |
| wikiloc | scs | 2021-11-16 | China Coast Guard water cannon on Philippine resupply at Second Thomas Shoal | 3.3 | added |
| wikiloc | europe_east | 2022-02-10 | Allied Resolve 2022 (Russia-Belarus) | 2.4 | added |
| wikiloc | ukraine | 2022-02-24 | Russia full-scale invasion | 5.0 | original |
| wikiloc | iran | 2022-03-13 | IRGC missiles on Erbil | 5.0 | added |
| wikiloc | drc | 2022-03-27 | M23 resurgence in North Kivu | 2.1 | added |
| wikiloc | ukraine | 2022-04-13 | Russian flagship Moskva hit by Neptune missiles, sinks next day | 5.0 | added |
| wikiloc | taiwan | 2022-08-04 | PLA drills after Pelosi | 4.4 | original |
| wikiloc | ukraine | 2022-08-29 | Ukraine launches Kherson counteroffensive | 2.5 | added |
| wikiloc | iran | 2022-09-28 | IRGC missile and drone strikes on Kurdish groups in Iraq | 5.0 | added |
| wikiloc | ukraine | 2022-10-08 | Crimean Bridge truck-bomb explosion | 2.7 | added |
| wikiloc | korea | 2022-12-26 | North Korean drones penetrate Seoul airspace | 5.0 | added |
| wikiloc | taiwan | 2023-04-08 | Joint Sword | 3.2 | original |
| wikiloc | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 5.0 | added |
| wikiloc | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 3.3 | added |
| wikiloc | yemen | 2023-11-19 | Red Sea attacks begin | 5.0 | original |
| wikiloc | korea | 2023-11-21 | North Korean spy satellite launch and end of 2018 military accord | 4.8 | added |
| wikiloc | sudan | 2023-12-15 | RSF Gezira offensive; Wad Madani falls | 4.7 | added |
| wikiloc | taiwan | 2024-05-23 | Joint Sword-2024A | 3.4 | original |
| wikiloc | scs | 2024-06-17 | Second Thomas Shoal boarding | 4.5 | original |
| wikiloc | taiwan | 2024-10-14 | Joint Sword-2024B | 4.3 | original |
| wikiloc | drc | 2025-03-13 | Bisie tin mine halted | 5.0 | original |
| wikiloc | sudan | 2025-05-04 | Drone strikes on Port Sudan | 4.4 | original |
| wikiloc | southasia | 2025-05-07 | Operation Sindoor | 5.0 | original |
| wikiloc | venezuela | 2025-09-02 | First US boat strike | 3.8 | original |
| wikiloc | europe_east | 2025-09-09 | Russian drones into Poland | 3.1 | original |
| wikiloc | drc | 2025-12-01 | M23 Uvira offensive with Rwandan support; Uvira falls | 2.6 | added |
| wikiloc | venezuela | 2025-12-10 | US seizes tanker Skipper | 2.6 | original |
| wikiloc | iran | 2026-02-28 | US-Israel war on Iran | 3.9 | original |
| wikiloc | scs | 2026-07-20 | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon at Scarborough | 2.2 | added |
