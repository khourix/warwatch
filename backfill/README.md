# History back-fills (methodology review, phase 3)

The review found that the fast leading feeds (aircraft, warnings, fires, vessels) have 1 to 150 days of history, so none of them could be tested
against past wars and strikes. This folder holds one job per source that rebuilds the history from free public archives. The live score does not
read any of it. Each series earns weight only after `validate.py` (phase 2) re-tests it against the event codebook (plan item 14).

Run: Actions > **backfill** > Run workflow (`source` = all, or one of fred, nga, pla, state, firms, gfw, adsb). Before the workflow is on the default branch, a push that edits `backfill/run.txt` (one line: `source [start] [end]`) starts the same run. Re-running is safe: jobs skip days they already have.
Output: `backfill/data/<series>.csv`, one `date,value` row per UTC day. `COVERAGE.md` lists rows, first and last day and the share of non-zero days per series.

| Source | Series (id) | Archive | Starts | Key |
|---|---|---|---|---|
| Military aircraft per theatre box and class | `adsb_<theatre>_<mil\|lift\|tanker\|isr\|fighter>`, `adsb_global_mil` | adsb.lol daily archives (GitHub releases `adsblol/globe_history_YYYY`) | 2024-03-20 (the archive has no earlier day; 71 later days are missing) | none |
| Hazard and missile-range warnings | `nga_<theatre>` (30-day count, as live), `nga_new_<theatre>` (issued that day) | NGA broadcast warnings, active and cancelled, per year | 2018 | none |
| Vessel presence and SAR detections | `ais_presence_<theatre>` (as live), `sar_<theatre>` | Global Fishing Watch 4Wings | 2018 (SAR 2017) | `GFW_TOKEN` |
| Thermal detections | `firms_<theatre>`, `firms_frp_<theatre>` | NASA FIRMS VIIRS S-NPP standard processing | 2018 | `FIRMS_MAP_KEY` |
| Implied volatility | `vol_ovx`, `vol_gvz`, `vol_vix`, `vol_vix3m`, `vol_vix_term` | FRED (OVXCLS, GVZCLS, VIXCLS, VXVCLS) | 2007 | `FRED_API_KEY` |
| PLA aircraft around Taiwan | `pla_aircraft`, `pla_median`, `pla_vessels`, `pla_official_ships` | Taiwan MND bulletins (list pages), plus the public ypcat/plavis CSV | 2022-08 (see PLA note) | none |
| US travel advisories | `state_<theatre>` (level sum, as live), `state_od_<theatre>` (countries with an ordered departure), `state_level_<country>`, `state_od_<country>` | Wayback Machine captures of travel.state.gov | 2018 | none |

## Things to know before testing a series

* **ADS-B level differs from live.** The archive counts different military aircraft seen in the box during the day; the live feed counts aircraft present at one instant. Score each on its own baseline. The network of feeders grew, so divide by `adsb_global_mil` or use ranks before comparing years.
* **FIRMS** standard processing lags about three months. The jobs stop at the archive's last day; the live cache covers the rest.
* **NGA stopped publishing in May 2024.** The `broadcast-warn` API returns nothing issued after 2024-05-10 (all statuses, all four navareas, checked 2026-10-07), so `nga_*` and `nga_new_*` end there and are not zero-filled. The live `nga_*` catalogue series reads that same frozen database, so it is not a working early-warning feed today. A replacement source is needed before NGA data can be used after May 2024.
* **NGA**: a warning is placed at its first coordinate (same rule as the live parser, `extras.parse_nga`), and only hazard text counts (missile, firing, gunnery, exercise, GPS, mine, drone).
* **State advisories** are read from one capture per week (and only when the page changed), then carried forward, so a level change is dated to within a week.
  Ordered departure is detected from the words "ordered departure" on the page, which also appear when one is being lifted.
* **PLA counts**: days a bulletin does not state a number stay empty, never zero (a bulletin that says no aircraft were detected is zero). The MND site publishes the figures as an attached image from late 2023 to early 2025 and for 2020-09 to 2022-07, so those periods are not readable as text; the public plavis CSV fills part of 2025 onward. `pla_aircraft` therefore runs 2022-08 to today with gaps. Check `COVERAGE.md` for the share parsed.
* **ADS-B coverage**: Yemen and DRC are all zeros (no military traffic seen in their boxes), so they cannot be tested.
* **Rate limits**: FIRMS allows 5000 requests per 10 minutes and GFW answers 429; both jobs back off and run few jobs at once.
* Gaps are real gaps: a day that failed to download is simply absent, not zero.

`python3 backfill/test_backfill.py` runs the parser tests (no network).
