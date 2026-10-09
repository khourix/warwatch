# Toyota indicator test

Written by `warwatch/tradelab.py`. Rule and cut fixed on 2026-10-09 before any result was seen (see the module docstring). Nothing here changes the live score.

Feature: monthly Japan and Thailand exports of pickups and large SUVs (Land Cruiser and Hilux sources) to the country, from UN Comtrade. A surge is the latest 3 months at least 2 standard deviations above the same measure over the 24 months that ended a year earlier. Hit: a surge in the 12 months before a buildup onset.

| Test | Onsets scored | Hits | Hit rate | False-alarm rate | Lift | p | Countries hit |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pre-registered: Sudan, Libya, Yemen, DRC | 10 | 6 | 60% | 53% | 1.1x | 0.453 | 4 |
| Same, with the 8-month publication lag (what could be seen in time) | 10 | 6 | 60% | 32% | 1.9x | 0.065 | 4 |
| Exploratory: UAE + Jordan + Turkey, against the same four theatres' events | 10 | 2 | 20% | 19% | 1.1x | 0.580 | 2 |
| Exploratory: hubs with the 8-month lag | 10 | 0 | 0% | 6% | 0.0x | 1.000 | 0 |

**Pre-registered verdict: does not pass** (needs 10 or more onsets, hit rate 3x false alarms, p < 0.01, hits in 3 or more countries).

## Each onset

| Date | Country | Type | Event | Highest surge z in the 12 months before |
|---|---|---|---|---:|
| 2019-04-04 | libya | surprise | Haftar Tripoli offensive | 14.4 |
| 2020-01-18 | libya | buildup | Oil port blockade | 16.1 |
| 2022-01-17 | yemen | surprise | Houthi attack on Abu Dhabi | 1.6 |
| 2023-04-15 | sudan | buildup | SAF-RSF war | 4.7 |
| 2023-11-19 | yemen | buildup | Red Sea attacks begin | 1.0 |
| 2024-07-20 | yemen | buildup | Israel strikes Hodeidah | 1.1 |
| 2024-08-26 | libya | buildup | Oil shutdown over central bank | 1.1 |
| 2025-01-23 | drc | buildup | M23 Goma offensive | 3.0 |
| 2025-03-13 | drc | buildup | Bisie tin mine halted | 3.0 |
| 2025-03-15 | yemen | buildup | US Rough Rider campaign | 1.1 |
| 2025-05-04 | sudan | surprise | Drone strikes on Port Sudan | 6.5 |
| 2025-07-06 | yemen | surprise | Magic Seas and Eternity C sunk | 2.9 |
| 2025-10-26 | sudan | buildup | El Fasher falls | 6.5 |
| 2026-03-28 | yemen | buildup | Houthis join 2026 Iran war | 3.8 |
