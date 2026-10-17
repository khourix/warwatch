# Base watch against past events: result

Written by `warwatch/basestudy.py` on 2026-10-17 to the plan fixed before the backfill was read ([BASEWATCH_STUDY_PLAN.md](BASEWATCH_STUDY_PLAN.md), amendment of 2026-10-17).

**Verdict: PASS.** A base was out or in during the 14 days before 19 of 111 events (17%), against 163 of 1473 calm windows (11%); one-sided Fisher p = 0.043. The rule needs p < 0.05 and calm firing of 15% or less.

Sites with scored radar passes: 113 of 120. Scenes to 2026-10-16. Left out for lack of data: 0 events and 0 calm windows.

| Events | Fired before | Share | p against calm |
|---|---:|---:|---:|
| original | 12 of 62 | 19% | 0.042 |
| added | 7 of 49 | 14% | 0.303 |

## Feasibility cases

| Site | Case date | State in the 14 days before | What |
|---|---|---|---|
| Al Udeid Air Base, Qatar | 2025-06-19 | other, out | aircraft dispersed before Iran's strike of 23 Jun 2025 |
| NSA Bahrain and Mina Salman port | 2026-02-26 | other | US ships left port before the strikes of 28 Feb 2026 |
| Olenya Air Base | 2025-06-01 | other | bombers present, then struck on 1 Jun 2025 |

## Sites that fired most in calm windows (the first to look at)

| Site | Calm window-days firing |
|---|---:|
| Tel Nof Air Base, Israel | 65 |
| Sevastopol naval base, Crimea | 65 |
| PAF Base Nur Khan, Rawalpindi | 53 |
| Hmeimim Air Base, Syria | 49 |
| Berbera airport and port, Somaliland | 44 |
| Kursk Khalino air base | 43 |
| Al Udeid Air Base, Qatar | 39 |
| Tartus naval base, Syria | 35 |
| Chiayi Air Base, Taiwan | 34 |
| Shaykovka Air Base | 33 |
| Saky air base, Crimea | 31 |
| NSA Bahrain and Mina Salman port | 27 |
| Baltiysk naval base, Kaliningrad | 24 |
| Shiraz 7th Tactical Air Base, Iran | 24 |
| Nevatim Air Base | 20 |

## Each event

| Date | Theatre | Event | Fired | Sites |
|---|---|---|---|---|
| 2022-03-13 | iran | IRGC missiles on Erbil | no |  |
| 2022-03-19 | yemen | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | no |  |
| 2022-03-24 | korea | First ICBM since 2017 | no |  |
| 2022-04-13 | ukraine | Russian flagship Moskva hit by Neptune missiles, sinks next day | yes | baltimor in |
| 2022-05-27 | iran | Iran seizes two Greek tankers | yes | mashhad_14tab in |
| 2022-08-04 | taiwan | PLA drills after Pelosi | no |  |
| 2022-08-05 | israel | Operation Breaking Dawn in Gaza | yes | souda in |
| 2022-08-27 | libya | Tripoli clashes over Bashagha government | no |  |
| 2022-08-29 | ukraine | Ukraine launches Kherson counteroffensive | yes | yeysk in |
| 2022-09-06 | ukraine | Kharkiv counteroffensive | yes | severomorsk in; yeysk in |
| 2022-09-26 | europe_east | Nord Stream pipelines sabotaged | no |  |
| 2022-09-28 | iran | IRGC missile and drone strikes on Kurdish groups in Iraq | no |  |
| 2022-10-04 | korea | Missile over Japan | no |  |
| 2022-10-08 | ukraine | Crimean Bridge truck-bomb explosion | no |  |
| 2022-10-10 | ukraine | First mass missile wave on Ukrainian grid | no |  |
| 2022-11-02 | korea | 23 missiles in a day | no |  |
| 2022-11-15 | europe_east | Przewodow missile | no |  |
| 2022-12-26 | korea | North Korean drones penetrate Seoul airspace | no |  |
| 2023-04-08 | taiwan | Joint Sword | no |  |
| 2023-04-15 | sudan | SAF-RSF war | no |  |
| 2023-04-27 | iran | Iran seizes tanker Advantage Sweet | yes | incirlik in |
| 2023-05-09 | israel | Operation Shield and Arrow in Gaza | no |  |
| 2023-06-04 | ukraine | Ukrainian summer counteroffensive begins | no |  |
| 2023-06-06 | ukraine | Kakhovka dam destroyed | no |  |
| 2023-07-17 | ukraine | Russia quits grain deal and strikes Odesa ports | no |  |
| 2023-08-05 | scs | Water cannon on Philippine resupply at Second Thomas Shoal | no |  |
| 2023-08-14 | libya | Tripoli clashes (444 Brigade) | no |  |
| 2023-08-19 | taiwan | PLA drills after Lai stopover in the US | no |  |
| 2023-10-07 | israel | Hamas attack | no |  |
| 2023-10-08 | israel | Hezbollah opens the northern front; Israel strikes southern Lebanon | no |  |
| 2023-10-08 | europe_east | Balticconnector pipeline and cable damaged | no |  |
| 2023-10-17 | iran | Militia attacks on US forces in Iraq and Syria begin | no |  |
| 2023-10-19 | yemen | Houthis' first missiles and drones at Israel; USS Carney intercepts | no |  |
| 2023-10-22 | scs | Collisions at Second Thomas Shoal | no |  |
| 2023-11-19 | yemen | Red Sea attacks begin | no |  |
| 2023-11-21 | korea | North Korean spy satellite launch and end of 2018 military accord | no |  |
| 2023-12-09 | scs | Water cannon at Scarborough and ramming at Second Thomas Shoal | no |  |
| 2023-12-15 | sudan | RSF Gezira offensive; Wad Madani falls | no |  |
| 2023-12-18 | yemen | Prosperity Guardian and carrier suspensions | no |  |
| 2024-01-05 | korea | North Korean artillery fire near Yeonpyeong | no |  |
| 2024-01-12 | yemen | First US-UK strikes on Houthis | no |  |
| 2024-01-16 | iran | Iran-Pakistan border strikes | no |  |
| 2024-01-28 | iran | Militia drone attack on Tower 22 in Jordan kills three US soldiers, the first US | no |  |
| 2024-02-02 | iran | US strikes militias in Iraq and Syria | yes | tel_nof in |
| 2024-03-05 | scs | Water cannon and collision at Second Thomas Shoal | no |  |
| 2024-04-01 | israel | Damascus consulate strike | no |  |
| 2024-04-13 | iran | Iran first direct attack on Israel | yes | shiraz_7tab in |
| 2024-04-19 | iran | Israeli strike near Isfahan | no |  |
| 2024-05-10 | ukraine | Russian Kharkiv offensive | no |  |
| 2024-05-23 | taiwan | Joint Sword-2024A | no |  |
| 2024-06-17 | scs | Second Thomas Shoal boarding | no |  |
| 2024-07-20 | yemen | Israel strikes Hodeidah | no |  |
| 2024-07-30 | israel | Israel kills Fuad Shukr in Beirut after Majdal Shams | no |  |
| 2024-07-31 | iran | Haniyeh assassinated in Tehran | yes | al_udeid out |
| 2024-08-06 | ukraine | Ukraine Kursk offensive | no |  |
| 2024-08-19 | scs | Collisions at Sabina Shoal | no |  |
| 2024-08-25 | israel | Israeli pre-emptive strikes and Hezbollah barrage | no |  |
| 2024-08-26 | libya | Oil shutdown over central bank | no |  |
| 2024-09-17 | israel | Pager attacks | no |  |
| 2024-09-23 | israel | Israel air campaign in Lebanon | no |  |
| 2024-09-26 | sudan | SAF offensive in Khartoum | no |  |
| 2024-10-01 | iran | Iran 200 missiles at Israel | no |  |
| 2024-10-14 | taiwan | Joint Sword-2024B | no |  |
| 2024-10-15 | korea | North Korea blows up inter-Korean roads | no |  |
| 2024-10-26 | iran | Israel strikes Iran | no |  |
| 2024-11-17 | europe_east | Baltic Sea cables cut (BCS and C-Lion1) | no |  |
| 2024-11-21 | ukraine | Oreshnik IRBM on Dnipro | yes | belbek in; novorossiysk out |
| 2024-11-27 | israel | HTS offensive and fall of Assad | no |  |
| 2024-12-08 | israel | Israel strikes Syrian military arsenal and enters Golan buffer zone after Assad  | no |  |
| 2024-12-19 | yemen | Israel strikes Sanaa and Hodeidah ports and power stations | no |  |
| 2024-12-25 | europe_east | Estlink 2 cable damage | no |  |
| 2025-03-15 | yemen | US Rough Rider campaign | no |  |
| 2025-03-18 | israel | Israel ends Gaza ceasefire | no |  |
| 2025-04-01 | taiwan | Strait Thunder-2025A | no |  |
| 2025-05-04 | sudan | Drone strikes on Port Sudan | no |  |
| 2025-05-05 | yemen | Israel strikes Hodeidah port, then Sanaa airport (6 May) | no |  |
| 2025-05-07 | southasia | Operation Sindoor | no |  |
| 2025-05-10 | southasia | Pakistan strikes Indian bases | no |  |
| 2025-05-12 | libya | Tripoli clashes after al-Kikli killed | no |  |
| 2025-06-01 | ukraine | Operation Spiderweb | yes | severomorsk in |
| 2025-06-13 | iran | Twelve-Day War | yes | erbil in |
| 2025-06-22 | iran | US Midnight Hammer | yes | al_udeid out |
| 2025-06-23 | iran | Iran strikes Al Udeid | yes | al_udeid out |
| 2025-07-06 | yemen | Magic Seas and Eternity C sunk | no |  |
| 2025-07-14 | israel | Israel strikes Syrian forces in Sweida, then defence ministry in Damascus | no |  |
| 2025-08-11 | scs | Scarborough collision | no |  |
| 2025-08-28 | yemen | Israeli strike kills Houthi prime minister | no |  |
| 2025-09-02 | venezuela | First US boat strike | no |  |
| 2025-09-09 | europe_east | Russian drones into Poland | no |  |
| 2025-09-09 | israel | Israeli strike in Doha | no |  |
| 2025-09-12 | europe_east | Zapad 2025 | no |  |
| 2025-09-19 | europe_east | MiG-31s violate Estonian airspace | yes | chkalovsk in; powidz in |
| 2025-10-26 | sudan | El Fasher falls | no |  |
| 2025-11-15 | europe_east | Explosive sabotage of Warsaw-Lublin rail line by Russian-recruited agents | no |  |
| 2025-12-03 | yemen | STC seizes Hadramawt and Mahra from government forces | no |  |
| 2025-12-10 | venezuela | US seizes tanker Skipper | no |  |
| 2025-12-29 | taiwan | Justice Mission-2025 | no |  |
| 2025-12-30 | yemen | Saudi strikes Mukalla port; Saudi-backed forces retake the south from STC | no |  |
| 2025-12-31 | europe_east | Helsinki-Tallinn telecom cable damaged; Finland seizes Fitburg | yes | baltiysk in |
| 2026-01-03 | venezuela | US strikes and capture of Maduro | no |  |
| 2026-02-28 | iran | US-Israel war on Iran | no |  |
| 2026-03-02 | iran | Hormuz standstill and Gulf strikes | no |  |
| 2026-03-02 | israel | Hezbollah-Israel war resumes | yes | akrotiri in |
| 2026-03-18 | iran | South Pars and Qatar LNG strikes | yes | muwaffaq_salti in |
| 2026-03-28 | yemen | Houthis join 2026 Iran war | no |  |
| 2026-04-13 | iran | US naval blockade of Iranian ports begins | no |  |
| 2026-07-08 | iran | Ceasefire collapse in Hormuz | yes | nevatim in |
| 2026-07-20 | scs | CCG rams Philippine boat and injures sailor at Second Thomas Shoal; water cannon | no |  |
| 2026-07-25 | yemen | Houthi missile and drone strikes on Aramco sites at Jizan and Yanbu, the first o | no |  |
| 2026-09-03 | yemen | Houthi west-coast offensive; Mocha and Mayun Island taken | no |  |
| 2026-10-06 | yemen | Houthi missile and drone campaign on Saudi airports (Jazan, Abha, Riyadh), the d | no |  |

Contains modified Copernicus Sentinel data 2021–2026 (Sentinel-1 RTC via Microsoft Planetary Computer).
