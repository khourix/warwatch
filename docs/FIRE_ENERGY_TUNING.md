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

The result section below is filled in after the run, with the counts for the chosen setting and the baseline, and the
cases neither can catch (most often no satellite saw the fire on the day).
