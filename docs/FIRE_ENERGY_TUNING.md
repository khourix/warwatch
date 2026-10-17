# Energy-site fire rule: tuning plan

Written on 2026-10-17, before any tuning run was read. The run is `python3 warwatch/fireref.py tune`; it writes
`backtest/fire_energy_tuning.json`.

## Why

The energy-site rule in PR #40 (a fire at a plant that rarely burns, or one far hotter than similar plants, is unusual) was
set by hand. Anthony asked to move its thresholds so the map catches more real strikes on power plants, refineries and fuel
depots while adding as few false alarms as possible.

## Cases

`warwatch/data/fire_energy_cases.csv`: 41 strikes on energy sites from 2019 to 2025, each with a published report of fire
and a position within about 2 km (18 in Ukraine and Russia, 10 in the Iran box, 8 in Yemen and Saudi Arabia, 5 in Israel).
A case counts as caught when any detection within 3 km, on the strike day or the next, is classed unusual (`anom` or `hot`).
Detections come from all three VIIRS satellites (Suomi NPP, NOAA-20, NOAA-21), as on the live map. The NOAA-20 and NOAA-21
yearly archives are read only if FIRMS publishes them; the run log says which satellites were read.

## False alarms

Every detection within 2 km of an energy or industrial site on every day of 2018 to 2021, across all boxes, with 3 days
around each case left out. These years have few strikes on energy sites in the boxes, so nearly every unusual flag there is
a false alarm. A false alarm is one distinct site cell (0.02 degrees) and day classed `anom` or `hot`, counted per year.

## Settings tried

| Setting | Values | In PR #40 |
|---|---|---|
| Days a plant burned in the prior 3 years for its fires to count as routine (`usual_days`) | 0, 5, 10, 20, 40, 80 | 10 |
| Score added for a non-routine fire at an energy site (`site`) | 25, 30, 35 | 25 |
| Hotter than similar plants: x times the spot's 95th percentile plus a margin, in MW (`similar`) | 2x+20, 1.5x+10, off | 2x+20 |
| Hotter than the spot's own record (`hot`) | max(3x, +100 MW), max(2x, +50 MW) | 3x, +100 |
| Fuel depots and substations within 1 km count as energy sites (`energy_sens`) | off, on | on |

## Selection rule (fixed now)

1. The baseline is the PR #40 setting in the right column.
2. Keep the settings whose false alarms per year are at most 1.25 times the baseline's.
3. Among those, pick the one that catches the most cases. Ties go to fewer false alarms, then to the setting closest to the
   baseline.
4. If no setting catches more cases than the baseline within that limit, the baseline stays.


## Result (run of 2026-10-17)

FIRMS publishes yearly country archives for Suomi NPP and NOAA-20 (`viirs-jpss1`) but not yet for NOAA-21, so the run
read two of the three satellites. 216 settings were scored; the full table is `backtest/fire_energy_tuning.json`.

| | Strikes caught (of 41) | Strikes with any detection | False alarms per year (2018–2021) |
|---|---:|---:|---:|
| PR #40 setting (baseline) | 5 | 17 | 1,865 |
| **Chosen setting** | **6** | 17 | **1,820** |
| Most caught by any setting | 7 | 17 | 2,379 (1.28 times the baseline, over the limit) |

**Chosen:** `usual_days` 5, `site` 30, the similar-plants test off, `hot` unchanged (3x, +100 MW), and fuel depots and
substations no longer count as energy sites (`energy_sens` off). It catches one more strike than the baseline with 2% fewer
false alarms. The rule picked it; nothing was changed after reading the table.

What moved:

- Now caught: Belgorod oil depot (1 Apr 2022) and Burshtyn power plant (10 Oct 2022), both from "unexplained" to "unusual".
- Lost: Shahran fuel depot (14 Jun 2025) drops from "unusual" (70) to "unexplained" (55), because depots no longer get the
  energy-site score. It still shows on the map, marked unexplained.
- The similar-plants test caught no strike in any setting and only added false alarms.

Why most strikes stay uncaught:

- **24 of 41 strikes had no detection** within 3 km on the day or the next from either satellite (cloud, smoke, a fire
  out before the overpass, or a fire too small). No threshold can catch these.
- **8 strikes look like routine heat**: Abqaiq, Shaybah, the Riyadh, Homs, Tehran and Bazan refineries and Khor Mor sit
  on flares that burn most days, and the strike fire was not hot enough above their own record to stand out. Lowering the
  "hotter than its own record" bar (2x, +50 MW) caught none of them.
- 2 depot fires in Crimea and Luhansk fell in the farm-burning season.

The false-alarm count is detections within 2 km of an energy or industrial site, so most of it is ordinary industry
that the map already shows as unexplained or unusual; it is a yardstick for comparing settings, not the map's daily
alert count.
