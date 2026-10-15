# Unusual satellite fires against past events

Written by `warwatch/sourcestudy.py fireanom` to the plan fixed before the counts were read ([FIREANOM_PLAN.md](FIREANOM_PLAN.md)). Daily VIIRS S-NPP detections that `firecls` classes as unusual (`anom` or `hot`), replayed over the 2018–2025 archive with reference data from earlier years only, scored as the live build scores a daily count and tested against the events of the theatres each box covers. Pass rule (firms_anom only): added events p < 0.05, original events p < 0.10, AUC above 0.55 on both. The raw count of all detections is tested the same way for comparison; it is not part of the rule.

Hit = z reached 2 in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.

| Family | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| firms_anom | 778 | 50% | 33 | 70% | 0.016 | 0.59 | 49 | 53% | 0.367 | 0.50 | no |
| firms (raw, for comparison) | 778 | 21% | 33 | 21% | 0.532 | 0.52 | 49 | 24% | 0.299 | 0.53 | no |

## Events where the series reached z 2 or more in the 30 days before

| Family | Theatre | Date | Event | Max z | List |
|---|---|---|---|---:|---|
| firms_anom | libya | 2019-04-04 | Haftar Tripoli offensive | 2.0 | original |
| firms_anom | iran | 2019-05-12 | Fujairah tanker sabotage | 4.9 | original |
| firms_anom | yemen | 2019-05-14 | Houthi drones on Saudi East-West pipeline | 4.2 | added |
| firms_anom | iran | 2019-06-13 | Gulf of Oman tanker attacks | 5.0 | original |
| firms_anom | israel | 2019-08-24 | Israeli strike on Quds Force drone team near Damascus and drones in Beirut; Hezbollah ATGM reply 1 Sept | 5.0 | added |
| firms_anom | iran | 2019-09-14 | Abqaiq-Khurais attack | 5.0 | original |
| firms_anom | israel | 2019-10-09 | Turkey launches Operation Peace Spring in northeast Syria | 5.0 | added |
| firms_anom | israel | 2019-11-12 | Operation Black Belt (PIJ commander killed) | 5.0 | added |
| firms_anom | libya | 2020-01-18 | Oil port blockade | 3.1 | original |
| firms_anom | iran | 2020-11-27 | Nuclear scientist Fakhrizadeh assassinated near Tehran | 2.6 | added |
| firms_anom | yemen | 2021-02-07 | Houthi Marib offensive escalates | 3.2 | added |
| firms_anom | iran | 2021-06-27 | US strikes militias on Iraq-Syria border | 2.2 | added |
| firms_anom | iran | 2021-07-29 | Drone attack on tanker Mercer Street | 2.9 | added |
| firms_anom | europe_east | 2021-09-10 | Zapad 2021 | 2.4 | original |
| firms_anom | ukraine | 2022-02-24 | Russia full-scale invasion | 5.0 | original |
| firms_anom | iran | 2022-03-13 | IRGC missiles on Erbil | 2.6 | added |
| firms_anom | korea | 2022-03-24 | First ICBM since 2017 | 5.0 | original |
| firms_anom | ukraine | 2022-04-13 | Russian flagship Moskva hit by Neptune missiles, sinks next day | 5.0 | added |
| firms_anom | iran | 2022-05-27 | Iran seizes two Greek tankers | 2.5 | added |
| firms_anom | ukraine | 2022-08-29 | Ukraine launches Kherson counteroffensive | 5.0 | added |
| firms_anom | europe_east | 2022-09-26 | Nord Stream pipelines sabotaged | 5.0 | added |
| firms_anom | ukraine | 2022-10-08 | Crimean Bridge truck-bomb explosion | 5.0 | added |
| firms_anom | iran | 2023-04-27 | Iran seizes tanker Advantage Sweet | 2.6 | added |
| firms_anom | israel | 2023-05-09 | Operation Shield and Arrow in Gaza | 3.9 | added |
| firms_anom | libya | 2023-08-14 | Tripoli clashes (444 Brigade) | 3.7 | added |
| firms_anom | israel | 2023-10-07 | Hamas attack | 5.0 | original |
| firms_anom | europe_east | 2023-10-08 | Balticconnector pipeline and cable damaged | 2.7 | added |
| firms_anom | yemen | 2023-10-19 | Houthis' first missiles and drones at Israel; USS Carney intercepts | 5.0 | added |
| firms_anom | yemen | 2023-11-19 | Red Sea attacks begin | 2.4 | original |
| firms_anom | korea | 2023-11-21 | North Korean spy satellite launch and end of 2018 military accord | 5.0 | added |
| firms_anom | israel | 2024-04-01 | Damascus consulate strike | 3.4 | original |
| firms_anom | iran | 2024-04-13 | Iran first direct attack on Israel | 2.3 | original |
| firms_anom | ukraine | 2024-05-10 | Russian Kharkiv offensive | 5.0 | added |
| firms_anom | yemen | 2024-07-20 | Israel strikes Hodeidah | 5.0 | original |
| firms_anom | israel | 2024-07-30 | Israel kills Fuad Shukr in Beirut after Majdal Shams | 5.0 | added |
| firms_anom | iran | 2024-07-31 | Haniyeh assassinated in Tehran | 2.4 | original |
| firms_anom | iran | 2024-10-01 | Iran 200 missiles at Israel | 3.3 | original |
| firms_anom | europe_east | 2024-11-17 | Baltic Sea cables cut (BCS and C-Lion1) | 3.8 | added |
| firms_anom | ukraine | 2024-11-21 | Oreshnik IRBM on Dnipro | 4.5 | original |
| firms_anom | israel | 2024-11-27 | HTS offensive and fall of Assad | 5.0 | original |
| firms_anom | yemen | 2024-12-19 | Israel strikes Sanaa and Hodeidah ports and power stations | 5.0 | added |
| firms_anom | yemen | 2025-03-15 | US Rough Rider campaign | 5.0 | original |
| firms_anom | yemen | 2025-05-05 | Israel strikes Hodeidah port, then Sanaa airport (6 May) | 2.1 | added |
| firms_anom | libya | 2025-05-12 | Tripoli clashes after al-Kikli killed | 2.7 | added |
| firms_anom | ukraine | 2025-06-01 | Operation Spiderweb | 2.7 | original |
| firms_anom | iran | 2025-06-13 | Twelve-Day War | 4.9 | original |
| firms_anom | yemen | 2025-07-06 | Magic Seas and Eternity C sunk | 2.1 | original |
| firms_anom | europe_east | 2025-09-09 | Russian drones into Poland | 5.0 | original |
| firms_anom | israel | 2025-09-09 | Israeli strike in Doha | 5.0 | original |
| firms (raw, for comparison) | israel | 2019-08-24 | Israeli strike on Quds Force drone team near Damascus and drones in Beirut; Hezbollah ATGM reply 1 Sept | 3.7 | added |
| firms (raw, for comparison) | israel | 2019-10-09 | Turkey launches Operation Peace Spring in northeast Syria | 5.0 | added |
| firms (raw, for comparison) | israel | 2019-11-12 | Operation Black Belt (PIJ commander killed) | 4.3 | added |
| firms (raw, for comparison) | yemen | 2022-01-02 | Houthis seize UAE-flagged Rwabee | 3.2 | added |
| firms (raw, for comparison) | yemen | 2022-03-19 | Houthi drone and missile wave on Aramco sites (Jeddah depot hit 25 Mar) | 2.6 | added |
| firms (raw, for comparison) | korea | 2022-03-24 | First ICBM since 2017 | 5.0 | original |
| firms (raw, for comparison) | ukraine | 2022-04-13 | Russian flagship Moskva hit by Neptune missiles, sinks next day | 5.0 | added |
| firms (raw, for comparison) | ukraine | 2022-08-29 | Ukraine launches Kherson counteroffensive | 2.1 | added |
| firms (raw, for comparison) | europe_east | 2022-09-26 | Nord Stream pipelines sabotaged | 2.2 | added |
| firms (raw, for comparison) | israel | 2023-10-07 | Hamas attack | 2.7 | original |
| firms (raw, for comparison) | korea | 2023-11-21 | North Korean spy satellite launch and end of 2018 military accord | 5.0 | added |
| firms (raw, for comparison) | ukraine | 2024-05-10 | Russian Kharkiv offensive | 4.3 | added |
| firms (raw, for comparison) | israel | 2024-07-30 | Israel kills Fuad Shukr in Beirut after Majdal Shams | 3.4 | added |
| firms (raw, for comparison) | iran | 2024-07-31 | Haniyeh assassinated in Tehran | 2.4 | original |
| firms (raw, for comparison) | ukraine | 2024-08-06 | Ukraine Kursk offensive | 3.1 | original |
| firms (raw, for comparison) | israel | 2024-11-27 | HTS offensive and fall of Assad | 3.2 | original |
| firms (raw, for comparison) | yemen | 2025-03-15 | US Rough Rider campaign | 2.7 | original |
| firms (raw, for comparison) | israel | 2025-07-14 | Israel strikes Syrian forces in Sweida, then defence ministry in Damascus | 2.1 | added |
| firms (raw, for comparison) | israel | 2025-09-09 | Israeli strike in Doha | 2.3 | original |
