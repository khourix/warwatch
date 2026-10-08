# Lead study: which indicators rose before the events

Written by `warwatch/leadstudy.py`. No model is fitted and nothing is tuned to the events. For each archive series the 7-day mean is compared with its own normal (the 150 days ending 31 days earlier) as a z-score. An event is a **hit** for a series if the z reached the cut at any point in the 30 days before it. A **false alarm** is the same thing in a 30-day window with no event within 30 days either side, in the same theatre. If a family really leads events, its hit rate should clearly beat its false-alarm rate.

Events: 78 labelled, counted only when no earlier event in the same theatre fell in the previous 30 days (a continuing war is not a new onset). Only series with history before the event can be scored, so aircraft cover 2024 onward and advisories, fires, NGA and vessel presence reach further back. The p-value is an exact binomial test of the hit count against the false-alarm rate; windows overlap, so it is a little generous.

## Hit rate against false-alarm rate (z of 2 or more)

| Family | Theatres | Events scored | Hits | Hit rate | False-alarm rate | Lift | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| adsb_fighter | 13 | 26 | 2 | 8% | 1% | 5.2x | 0.056 |
| adsb_lift | 13 | 26 | 5 | 19% | 13% | 1.5x | 0.223 |
| adsb_tanker | 13 | 26 | 2 | 8% | 5% | 1.6x | 0.344 |
| adsb_mil | 13 | 26 | 4 | 15% | 12% | 1.3x | 0.370 |
| firms_frp | 7 | 43 | 11 | 26% | 24% | 1.0x | 0.485 |
| nga | 13 | 28 | 3 | 11% | 12% | 0.9x | 0.662 |
| firms | 7 | 43 | 7 | 16% | 21% | 0.8x | 0.816 |
| ais_presence | 8 | 45 | 1 | 2% | 5% | 0.5x | 0.892 |
| adsb_isr | 13 | 26 | 0 | 0% | 5% | 0.0x | 1.000 |
| state | 13 | 60 | 0 | 0% | 3% | 0.0x | 1.000 |
| sar | 8 | 45 | 0 | 0% | 1% | 0.0x | 1.000 |

33 family-and-cut combinations are tested here, so about 1.7 would show p < 0.05 by chance alone. Treat a single p just under 0.05 as a lead to follow, not a finding.

### Other cut-offs

| Family | Cut | Hit rate | False-alarm rate | p |
|---|---:|---:|---:|---:|
| adsb_fighter | 1.5 | 12% | 2% | 0.017 |
| adsb_fighter | 3.0 | 0% | 1% | 1.000 |
| adsb_isr | 1.5 | 4% | 8% | 0.888 |
| adsb_isr | 3.0 | 0% | 1% | 1.000 |
| adsb_lift | 1.5 | 23% | 21% | 0.483 |
| adsb_lift | 3.0 | 4% | 6% | 0.772 |
| adsb_mil | 1.5 | 23% | 24% | 0.608 |
| adsb_mil | 3.0 | 0% | 4% | 1.000 |
| adsb_tanker | 1.5 | 19% | 10% | 0.105 |
| adsb_tanker | 3.0 | 4% | 2% | 0.361 |
| ais_presence | 1.5 | 11% | 9% | 0.419 |
| ais_presence | 3.0 | 0% | 1% | 1.000 |
| firms | 1.5 | 28% | 26% | 0.442 |
| firms | 3.0 | 7% | 15% | 0.970 |
| firms_frp | 1.5 | 28% | 29% | 0.628 |
| firms_frp | 3.0 | 14% | 18% | 0.823 |
| nga | 1.5 | 21% | 17% | 0.318 |
| nga | 3.0 | 7% | 6% | 0.534 |
| sar | 1.5 | 2% | 2% | 0.650 |
| sar | 3.0 | 0% | 0% | 1.000 |
| state | 1.5 | 2% | 3% | 0.849 |
| state | 3.0 | 0% | 1% | 1.000 |

## Average z by days before the event

Mean z of the series on the given day before the event, over the same events as above. A real lead shows the mean climbing toward 0; the last column is the mean on ordinary days.

| Family | -30 | -21 | -14 | -7 | -3 | -1 | event day | ordinary day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| adsb_fighter | +0.06 | +0.04 | +0.10 | +0.13 | +0.15 | +0.08 | +0.08 | +0.00 |
| adsb_isr | -0.01 | -0.01 | -0.01 | +0.14 | -0.03 | -0.03 | -0.01 | +0.07 |
| adsb_lift | +0.19 | +0.20 | +0.38 | +0.25 | +0.21 | +0.20 | +0.22 | +0.22 |
| adsb_mil | +0.32 | +0.32 | +0.31 | +0.19 | +0.19 | +0.10 | +0.08 | +0.35 |
| adsb_tanker | +0.14 | +0.09 | +0.77 | +0.79 | +0.68 | +0.64 | +0.68 | +0.07 |
| ais_presence | +0.12 | +0.16 | +0.15 | +0.25 | +0.29 | +0.26 | +0.25 | +0.10 |
| firms | -0.00 | -0.07 | +0.15 | +0.13 | +0.10 | +0.16 | +0.15 | +0.32 |
| firms_frp | +0.09 | +0.15 | +0.71 | +0.29 | +0.20 | +0.30 | +0.27 | +0.53 |
| nga | +0.38 | +0.12 | -0.07 | -0.22 | -0.22 | -0.15 | -0.11 | +0.08 |
| sar | -0.00 | -0.03 | -0.02 | +0.05 | +0.07 | +0.03 | -0.01 | +0.02 |
| state | +0.04 | +0.04 | +0.04 | +0.05 | +0.06 | +0.06 | +0.06 | +0.05 |

## Events with a family above z = 2 beforehand

| Date | Theatre | Event | Type | Families that rose |
|---|---|---|---|---|
| 2019-06-13 | iran | Gulf of Oman tanker attacks | buildup | firms (2.7), firms_frp (5.8), ais_presence (2.0) |
| 2022-01-17 | yemen | Houthi attack on Abu Dhabi | surprise | firms (4.8), firms_frp (4.1) |
| 2022-03-24 | korea | First ICBM since 2017 | buildup | firms (9.9), firms_frp (42.3) |
| 2022-08-04 | taiwan | PLA drills after Pelosi | buildup | nga (2.0) |
| 2022-10-10 | ukraine | First mass missile wave on Ukrainian grid | buildup | nga (5.2) |
| 2023-11-19 | yemen | Red Sea attacks begin | buildup | firms (12.6), firms_frp (13.9) |
| 2024-04-13 | iran | Iran first direct attack on Israel | buildup | nga (4.7) |
| 2024-07-31 | iran | Haniyeh assassinated in Tehran | surprise | firms_frp (2.7) |
| 2024-08-06 | ukraine | Ukraine Kursk offensive | surprise | firms (2.5), firms_frp (2.7) |
| 2024-11-21 | ukraine | Oreshnik IRBM on Dnipro | surprise | adsb_lift (2.1), adsb_mil (2.2) |
| 2024-11-27 | israel | HTS offensive and fall of Assad | surprise | adsb_fighter (2.0), adsb_mil (2.1) |
| 2025-03-15 | yemen | US Rough Rider campaign | buildup | firms (2.0), firms_frp (2.7) |
| 2025-05-07 | southasia | Operation Sindoor | buildup | adsb_lift (2.5), adsb_mil (2.8) |
| 2025-06-01 | ukraine | Operation Spiderweb | surprise | adsb_lift (2.7) |
| 2025-06-13 | iran | Twelve-Day War | buildup | adsb_lift (2.5), adsb_tanker (2.6), firms_frp (2.5) |
| 2025-09-09 | israel | Israeli strike in Doha | surprise | adsb_fighter (2.3), firms_frp (4.7) |
| 2026-03-28 | yemen | Houthis join 2026 Iran war | buildup | firms (2.1), firms_frp (2.4) |
| 2026-07-08 | iran | Ceasefire collapse in Hormuz | surprise | adsb_lift (4.9), adsb_mil (2.6), adsb_tanker (21.0), firms_frp (3.8) |
