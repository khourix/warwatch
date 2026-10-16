# Fire classification: implementation plan

Status: proposal, written 2026-10-15. Read [SATELLITE_PROPOSAL.md](SATELLITE_PROPOSAL.md) first for the why.
This file is the how. It is written for an implementer who has not seen the design discussion. Build the
stages in order (F1 to F5) and open one PR per stage. Each stage lists its files, functions, data formats,
thresholds, tests and "done when" checks.

## As built (2026-10-15)

Built in this order: F1, F2, F3, F4, F5. Where the build differs from the spec below, the build wins:
- **Country files**: FIRMS spells them `Russian_Federation`, `Republic_of_Korea`, `Dem_Rep_Korea`, `Czech_Republic` and
  `Turkey` (`config.FIRE_COUNTRIES`). The archive runs 2012–2025; 2026 is not published yet.
- **Grids**: storing every cell that burned twice was too big (Ukraine's farmland). There are three files per box:
  - `fire_cells_<box>.csv.gz`: only "notable" cells, those with 20 or more burn days in some year, or NASA type 1/2/3.
  - `fire_years_<box>.bin.gz`: a 16-bit mask of the years each ~1 km cell burned.
  - `fire_coarse_<box>.csv.gz`.
  All seven boxes together come to about 3 MB.
- **Rules changed before the test** (see the amendments in [FIREANOM_PLAN.md](FIREANOM_PLAN.md)):
  - offshore needs a persistent source that is mostly over water, which keeps reed fires, river fronts and waterside
    steel works out;
  - seasonal needs the ~3 km spot to have burned in 3 or more earlier years. Without that, the Shahran depot fire in
    Tehran was called a farm fire.
- **Replay output** goes to `backfill/data/firecls/`, so `fastfeeds.py`, which globs `backfill/data/*.csv`, does not pick it up.
- **The Economist (F3)**: their per-fire file (`output-data/ukraine_war_fires.csv`, ~70 MB) is streamed every 6 hours in
  `imagery.yml` (`fireref.py econ`), keeping 21 days of war-related fires. Their flag adds +15. It never makes a fire
  "unusual" on its own.
- **OpenStreetMap**: Overpass is often at capacity. `fireref.overpass` rotates mirrors (overpass-api.de, maps.mail.ru,
  kumi, private.coffee) and backs off. All tag filters for a tile go in one union query.

## What changes for the reader

Today a fire on the map is either "unusual" or "routine". "Routine" means its ~2 km cell burned on 3 of the
last 7 days (`osint.mark_routine`). That rule has two faults. A gas flare that was off for a week shows as
unusual. A town shelled three days running turns "routine" and fades out.

After this work each detection carries a **class**, a **score** (0 to 100) and a **plain reason**:

| Class code | Map look | Reason shown (example) |
|---|---|---|
| `anom` | bright lime, glow, ping | "No fire here in 14 years of records, 1.2 km from Isfahan air base, 86 MW at night." |
| `hot` | bright lime, glow, ping | "Much more heat than usual at Abqaiq processing plant: 640 MW against a usual 40 MW." |
| `unex` | lime, no glow | "Not a known industrial site, and this area rarely burns in October." |
| `seas` | faint hollow ring | "This area burns in most years in June (farm and grass fires)." |
| `ind` | faint dashed grey ring | "Gas flare at Rumaila field: this spot burns on 9 days in 10." |
| `volc`, `off` | faint dashed grey ring | "Volcano" / "Offshore platform or flare." |

`anom` and `hot` are the anomalies. `seas`, `ind`, `volc` and `off` are the "explained" fires. They stay on the
map, faded, and a layer filter hides them (owner's choice, 2026-10-15).

## Ground rules (from this repo)

- The dashboard build (`warwatch/run.py`, workflow `warwatch.yml`) is **standard-library Python only**. Anything
  that needs numpy, rasterio or Pillow runs in its own workflow and writes small cache files that the build reads.
  `warwatch/sar.py` + `.github/workflows/sar.yml` is the pattern to copy.
- Public data only. Never commit a key. The FIRMS key is the secret `FIRMS_MAP_KEY`.
- `warwatch/history/*.csv` merges with `merge=union` (append-only). Whole-file caches go in `warwatch/history/cache/`.
  Static reference tables go in `warwatch/data/`.
- Page text is plain words and short sentences, like the existing strings in `page.html`.
- A new series is shown but carries **zero weight** in the model (`ZERO_WEIGHT` in `catalog.py`) until it passes a
  test plan written **before** its results are read (see `docs/SENKAKU_PLAN.md` for the format).
- Before each commit run `.agents/skills/verify-warwatch/verify.sh quick`. Before each PR run `full` and paste the
  output into the PR body.

## Facts the design relies on (checked 2026-10-15)

| Fact | Status | Source |
|---|---|---|
| VIIRS 375 m `type` field: 0 vegetation fire, 1 active volcano, 2 other static land source, 3 offshore. Only in standard-processing (SP) data, not in NRT. | Documented by NASA. Not checked live from this sandbox. | earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs |
| Yearly SP country files, no key: `https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/{YYYY}/viirs-snpp_{YYYY}_{Country_Name}.csv`. VIIRS S-NPP from 2012. About 5 months behind real time. They include `type` and `daynight`. | URL pattern seen in several public repos. **Step F1.0 checks it live.** | firms.modaps.eosdis.nasa.gov/country/ |
| Area API: `/api/area/csv/{KEY}/{SOURCE}/{W,S,E,N}/{1..5 days}/{YYYY-MM-DD}`. Sources include `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_SP`. Limit 5,000 transactions per 10 minutes per key. | Already used by `osint.py` and `backfill/sources_fast.py`. | firms.modaps.eosdis.nasa.gov/api/area/ |
| A very intense fire can saturate VIIRS and report FRP = 0. | VIIRS VNP14 user guide | |
| World Bank GGFR per-flare locations and volumes, 2012 to 2024, free xlsx. | URL is used in World Bank training code. **F1.0 checks it live.** | thedocs.worldbank.org/en/doc/bd2432bbb0e514986f382f61b14b2608-0400072025/related/2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx |
| Global Energy Monitor trackers are CC BY 4.0. They are downloaded through a free request form, and the files have Latitude and Longitude columns. | GEM licence page | globalenergymonitor.org/creative-commons-public-license/ |
| WRI Global Power Plant Database v1.3.0: CC BY 4.0. Frozen since 2021. Has latitude, longitude, primary_fuel and capacity_mw. | github.com/wri/global-power-plant-database | |
| The Economist war-fire model: open code (MIT), data CC BY 4.0, updated several times a day. It counts fires per 0.1° cell-day, predicts the expected count from past fires, season, population and night lights, and flags a cell-day as war-related when the excess had under 5% chance in a normal year and repeats nearby. | Read from the repo | github.com/TheEconomist/the-economist-war-fire-model |

FRP alone does not separate flares from strike fires. Small vegetation fires average roughly 7 to 12 MW per pixel,
and VIIRS sees down to about 1.5 to 3.5 MW. No source gives a clean FRP range for flares. Flares and small fires
overlap. **Location history is the main separator; FRP only modifies the score** and drives the "hotter than its own
normal" test at known sites.

---

## F1. Reference tables (one-off build, refreshed monthly)

New script `warwatch/fireref.py`. It uses only the standard library, but it is too slow for the dashboard build.
It runs in the new workflow `.github/workflows/fireref.yml` (dispatch plus monthly cron `20 3 2 * *`) and commits
its outputs to `warwatch/data/`.

### F1.0 Live checks (do first, 15 minutes)

`python3 warwatch/fireref.py probe` fetches and reports:
1. The HTTP status and the header row of `viirs-snpp_2023_Ukraine.csv`. It must have `latitude, longitude, acq_date, acq_time, frp, daynight, type`.
2. The same for every country name in `FIRE_COUNTRIES` (below), for one year. Fix names that 404. NASA uses
   underscores, e.g. `Saudi_Arabia`, `United_Arab_Emirates`. Try the spelling the FIRMS country page uses.
3. The GGFR xlsx: the status and the first sheet's column names.

If the country files are gone, fall back to the area API with source `VIIRS_SNPP_SP`. `backfill/sources_fast.py
cmd_firms` already pages it 5 days per call. Keep every detection instead of daily sums. Check that `type` is in the
SP header; if it is missing, drop rule `t2` below and rely on the persistence rule.

### F1.1 Country list per box (add to `config.py`)

```python
FIRE_COUNTRIES = {   # FIRMS country files that cover each FIRMS_BOX; detections are clipped to the box after download
    "ukraine": ["Ukraine", "Russia", "Belarus", "Moldova", "Romania", "Poland", "Slovakia", "Hungary"],
    "europe_east": ["Poland", "Lithuania", "Latvia", "Estonia", "Finland", "Sweden", "Belarus", "Russia", "Germany", "Czechia", "Slovakia", "Ukraine"],
    "iran": ["Iran", "Iraq", "Kuwait", "Bahrain", "Qatar", "United_Arab_Emirates", "Oman", "Saudi_Arabia", "Syria", "Turkey", "Jordan",
             "Armenia", "Azerbaijan", "Turkmenistan", "Afghanistan", "Pakistan", "Georgia"],
    "yemen": ["Yemen", "Saudi_Arabia", "Oman", "Eritrea", "Ethiopia", "Djibouti", "Somalia", "Sudan", "Egypt"],
    "israel": ["Israel", "Palestine", "Lebanon", "Syria", "Jordan", "Egypt", "Turkey", "Iraq", "Saudi_Arabia", "Cyprus"],
    "korea": ["South_Korea", "North_Korea", "China", "Japan"],
    "libya": ["Libya", "Tunisia", "Algeria", "Egypt", "Niger", "Chad", "Sudan"],
}
FIRE_CLIM_YEARS = {"ukraine": (2012, 2021), "europe_east": (2012, 2021), "israel": (2012, 2022)}   # years used for the SEASONAL baseline; others use 2012..last full year
```

The `FIRE_CLIM_YEARS` exclusion matters. Since 2022 the front line in Ukraine burns every summer. If those years
count, the seasonal rule would label shelling as "seasonal" and fade it. The Economist model trains only on data up
to 23 Feb 2022 for the same reason. The static-source rule still uses every year, because flares do not care about
wars.

### F1.2 Download and reduce

`python3 warwatch/fireref.py build --box iran [--years 2012-2025]`

For each year and country, stream the CSV (do not hold it all in memory) and keep rows inside `C.FIRMS_BOX[box]`.
Keep low-confidence rows too, as the backfill does. Then reduce to two grids. Do not store raw detections.

**Fine grid, 0.01° (~1.1 km).** Cell key `i = round(lat / 0.01)`, `j = round(lon / 0.01)`. Per cell:
- `t1`, `t2`, `t3`: the number of detections with `type` 1, 2 and 3.
- `frp95`: the 95th percentile of per-detection FRP. `frpmax`: the maximum.
- `n95`: the 95th percentile of detections per day on days the cell burned.
- `d{YYYY}`: for each year, the number of distinct days with a detection.
- `last`: the last date seen.
Only cells with at least 2 detection days in total are kept.

File: `warwatch/data/fire_cells_{box}.csv.gz` (gzip CSV). Header:
`i,j,t1,t2,t3,frp95,frpmax,n95,last,d2012,d2013,...,d{last}`.
Write integers for counts and one decimal for FRP.

**Coarse grid, 0.1° (~11 km).** Cell key `I = round(lat / 0.1)`, `J = round(lon / 0.1)`. Per cell and year, store a
12-bit month mask: bit `m-1` is set if any detection fell in month `m`. **Leave out detections whose fine cell is
static** (rule below), so flares do not make a district look "seasonal".

File: `warwatch/data/fire_coarse_{box}.csv.gz`. Header: `I,J,m2012,...,m{last}` (integers 0 to 4095).

Size check: print row counts and file sizes. If one box's files together exceed 8 MB gzipped, raise the fine-cell
keep threshold to 3 days and say so in the PR.

### F1.3 Site gazetteer

`python3 warwatch/fireref.py sites` writes `warwatch/data/fire_sites.csv` with columns
`id,name,kind,lat,lon,src`. `kind` is one of:

- Industrial (heat expected): `flare`, `oilgas` (refinery, gas plant, petrochemical, terminal), `steel`, `power`, `cement`.
- Sensitive (heat unexpected, a fire here matters more): `military`, `airfield`, `port`, `fuel` (tank farm or depot), `substation`.

Sources:
1. **OpenStreetMap via Overpass** (`https://overpass-api.de/api/interpreter`). Run one query per box per tag group,
   with `[out:json][timeout:300]` and `out center tags;`, and sleep 30 s between queries (Overpass fair use). Tags:
   - `man_made=flare` → flare
   - `industrial~"^(refinery|oil|gas|petrochemical)$"`, `man_made=works` with `product~"oil|gas|petrol"` → oilgas
   - `industrial=steelmaker` or `man_made=works` with `product~"steel|iron"` → steel
   - `power=plant` → power (keep `plant:source`)
   - `industrial=cement` or `product=cement` → cement
   - `landuse=military`, `military~"^(airfield|base|naval_base|barracks|range)$"` → military
   - `aeroway=aerodrome` → airfield
   - `industrial=port`, `landuse=port`, `harbour=yes` → port
   - `man_made=storage_tank` with `content~"oil|fuel|gas|petrol|diesel"` → fuel. Merge tanks closer than 400 m into
     one site at their mean position. Many tanks have no `content` tag. Also keep untagged tank clusters of 5 or more
     tanks as `fuel`.
   - `power=substation` with `voltage>=220000` → substation (strikes on the grid)
2. **World Bank GGFR flare list** (the xlsx above). Parse it with `zipfile` + XML. The build stays stdlib-only, so do
   not add openpyxl. Keep flares inside the box as `flare`, with `src=ggfr`.
3. **Global Energy Monitor** (optional; it needs the free request form, so the owner downloads it by hand). If
   `warwatch/data/raw/gem_*.xlsx` or `.csv` exists, add oil and gas plants, steel plants and coal plants. Add
   `warwatch/data/raw/` to `.gitignore`; only the merged `fire_sites.csv` is committed.
4. **WRI power plants** (CSV from GitHub, CC BY 4.0): gas, oil and coal plants of 50 MW or more → power.

Store a site index for fast lookups: bucket sites by `(round(lat/0.05), round(lon/0.05))`.

Licence note: `fire_sites.csv` is built from OSM, so it falls under ODbL. Add a header comment line
`# Contains data © OpenStreetMap contributors (ODbL), GGFR (World Bank), WRI, GEM (CC BY 4.0)` and add the same to
the dashboard source list (`dashboard.py`, the tuple list near line 42).

### F1 tests (add to `warwatch/tests/test_warwatch.py`, class `TestFireRef`)

- `reduce` on a 20-row synthetic CSV gives the expected fine cells, `d{YYYY}` counts, `t2` and month masks.
- Detections in a static fine cell leave the coarse mask untouched.
- The storage-tank merge joins tanks 300 m apart and keeps tanks 600 m apart separate.

**Done when:** all seven boxes have both grids committed; `fire_sites.csv` has a site count per box per kind printed
in the PR; and the spot checks below come out as expected. Write them as a printed table from
`python3 warwatch/fireref.py check`:
- The Baba Gurgur flame (Kirkuk), Rumaila field flares (Basra) and South Pars / Assaluyeh flares are static cells
  with `t2 > 0` or the persistence rule.
- Isfahan city centre and central Kyiv are not static.

---

## F2. Live classifier

New module `warwatch/firecls.py`, standard library only.

```python
def load(box) -> Ref          # reads fire_cells_{box}.csv.gz, fire_coarse_{box}.csv.gz and the box's sites; cached per process
def classify(pts, box, today) # sets p["c"], p["a"], p["why"], p["site"] on each detection dict; returns pts
```

`pts` are the dicts that `osint.parse_firms` makes. Extend `parse_firms` to also keep `daynight` ("D"/"N"),
`bright_ti4` and `confidence`.

### Rules, in this order (the first match wins)

Let `Y` be the current year, `nb(cell)` the 3×3 neighbourhood of a fine cell (about 3.3 km), and `site(k, r)` the
nearest gazetteer site of a kind in `k` within `r` km.

1. **Static source**. `static(cell)` is true when any cell in `nb(cell)` has `t2 >= 5`, **or** has at least 60
   detection days in each of at least 2 of the 5 years before `Y`. In plain words: it burns on one day in six or
   more, year after year.
2. **Volcano**: any cell in `nb` has `t1 >= 3` → `volc`, score 5.
3. **Offshore**: `t3 >= 3` in `nb` and no `port`/`military` site within 2 km → `off`, score 5.
4. **Industrial**: `static` or `site(flare|oilgas|steel|power|cement, 1.0 km)`:
   - **Hotter than its own normal** → `hot`, when any of these holds:
     - `frp >= max(3 * frp95, frp95 + 100)` over the `nb` cells (use the largest `frp95` among them);
     - the detections this pass within 1.5 km number at least `3 * n95 + 3`;
     - `frp == 0 and bright_ti4 >= 367` (saturated pixel).
     Score 75. Reason: "Much more heat than usual at {site or 'this industrial site'}: {frp} MW against a usual {frp95} MW."
   - Otherwise → `ind`, score 10. Reason: "{Gas flare|Refinery|Steel works|Power plant|Industrial heat} at {name}:
     this spot burns on {pct}% of days." `pct` = mean of the `d{y}` over the last 3 years / 365, rounded.
5. **Seasonal burning**. `seasonal_p` = the share of baseline years (from `FIRE_CLIM_YEARS`, years before `Y` only,
   at least 4 of them, otherwise `None`) in which the coarse cell **or any of its 8 neighbours** has the detection's
   month bit set. If the date is within 10 days of a month boundary, the adjacent month's bit also counts. Then:
   - `seasonal_p >= 0.4` **and** no `military|airfield|port|fuel|substation` site within 2 km **and** `frp < 100`
     → `seas`, score 15. Reason: "This area burns in most years in {Month} (farm and grass fires)."
6. **Everything else is unexplained**: `unex`, and it becomes `anom` when the score reaches 60. The score adds:
   - 30 base;
   - +20 when no cell in `nb` has any detection day in the archive ("No fire here in {n} years of records");
   - +10 when `seasonal_p` is not `None` and is below 0.1 ("this area rarely burns in {Month}");
   - +25 when a `military|airfield|port|fuel|substation` site is within 2 km ("{km} km from {site}");
   - +10 when `frp >= 50`, and +10 more when `frp >= 200`;
   - +10 when at least 3 detections lie within 2 km of each other in the same pass (same `ts`);
   - +5 when `daynight == "N"` (farm burning is a daytime activity);
   - −15 when `seasonal_p >= 0.4` (seasonal, but kept unexplained because it is near a sensitive site or very hot).
   Cap the score at 100. The reason joins the parts that applied, in the order above, as one sentence.

If a box has no reference files (a new box), fall back to the old `mark_routine` rule: routine → `ind`, otherwise
→ `unex`.

**These weights are starting values.** Tune them only on 2018–2021 data (F4) and freeze them in a commit **before**
F4 reads 2022–2026. Record the frozen values in `docs/FIRECLASS_PLAN.md` under "Frozen values".

### Wire it in

- `osint.fetch_fires`: after collecting `got` per box, call `firecls.classify(got, th, today)` instead of
  `mark_routine(got)`. Selection per box: every `anom` and `hot` (cap 300), then `unex` by score (cap 200), then
  explained by FRP (cap 100).
- Optional (F2b): add `VIIRS_NOAA20_NRT` and `VIIRS_NOAA21_NRT` to the **map layer only** (not to `firms_counts`;
  that series stays S-NPP to match its archive). This adds 28 calls per run, well under the limit. Store the source
  as `p["sat"]`.
- `dashboard.py` fires payload: add `c=p["c"]`, `a=p["a"]`, `why=p["why"]`, `site=p.get("site","")`,
  `ll=[round(lat,3), round(lon,3)]`, `dn=p.get("daynight","")`. Keep `r=1` for explained classes
  (`seas, ind, volc, off`), so old page code paths keep working.
- Every run, write the anomalies to `warwatch/history/cache/fire_anoms.csv`. F5 reads this file. Columns:
  `cid,th,lat,lon,first_ts,last_ts,max_frp,score,c`, where `cid` = `{box}_{i}_{j}_{first date}` of the
  highest-scoring detection in a 2 km cluster. Keep 21 days of rows.
- `demo.py`: add about 12 synthetic fires covering every class, with `ll`, `why` and `a`, so the `full` verify
  screenshots show the layer.

### Page (`warwatch/page.html`)

Names below are current identifiers. Line numbers drift, so search for them.
- `FIRE_BANDS`, `fireR` and the fire drawing block (search `const gf = L('fires')`):
  - `anom` and `hot`: the current "fresh" look (glow plus `ping`) whatever their age band.
  - `unex`: the normal lime dot, no glow.
  - Explained classes: hollow dashed grey ring (today's routine style) at opacity 0.45.
- Layers popover (search `['fires', 'Fires and heat (NASA)', 'fire']`): add a sub-toggle
  `['firesx', 'Show explained fires', 'fire']`. Add `firesx: true` to `DEFAULTS`. When it is off, hide
  explained-class markers.
- Legend (search `Fires and heat · fainter = older`): one row per look: "Anomaly", "Unexplained", "Explained
  (industry, farm burning)".
- Tooltip and drawer (search `type === 'fires'`): the title by class ("Unusual fire or heat", "Unexplained heat",
  "Hotter than usual at an industrial site", "Seasonal farm or grass fire", "Routine industrial heat", "Volcano",
  "Offshore platform or flare"), then `why`, FRP, the time, and two buttons:
  - **Copernicus Browser** (Sentinel-2): `https://browser.dataspace.copernicus.eu/?zoom=14&lat={lat}&lng={lon}&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=1_TRUE_COLOR&fromTime={d-10}T00%3A00%3A00.000Z&toTime={d+10}T23%3A59%3A59.999Z&dateMode=TIME%20RANGE`
    (`layerId=6-SWIR` shows burn scars; test both in a browser before you ship).
  - **NASA Worldview** (the day's fires over VIIRS true colour): `https://worldview.earthdata.nasa.gov/?v={lon-0.15},{lat-0.1},{lon+0.15},{lat+0.1}&l=VIIRS_SNPP_Thermal_Anomalies_375m_All,VIIRS_NOAA20_Thermal_Anomalies_375m_All,VIIRS_SNPP_CorrectedReflectance_TrueColor&t={d}-T00%3A00%3A00Z`
  Build these URLs in JS from `ll` and the date. Do not store them in the data. The verify check `links-data`
  requires that fields named `u`/`url` be http(s), so use other names.
- Alerts (search `new fires in`): count only `anom` and `hot` in the last 24 h. Alert at 5 or more per theatre
  (it was 10 "unusual"). Title: "{n} unusual fires in {theatre} in the last 24 hours".
- Activity page KPI (search `'Fires · '`): "{a} unusual · {u} unexplained · {e} explained".

### F2 tests (`TestFireCls`)

Use a tiny in-memory `Ref`:
- a static cell (`t2=10`) → `ind`;
- the same cell at 5 × its `frp95` → `hot`;
- a never-burned cell 1 km from a `military` site, 80 MW, night → `anom` with score ≥ 60, and a reason that names the site;
- a cropland-like coarse cell that burned in June in 8 of 10 years, a June detection → `seas`;
- the same in October → `unex`;
- a box with no reference → falls back to `mark_routine`;
- the dashboard payload keeps `r` for explained classes.

**Done when:** `verify.sh full` passes, the demo screenshot shows all looks, and a live run's Activity page shows
the three counts.

---

## F3. Optional second opinion for Ukraine (The Economist)

The Economist model publishes its classification several times a day under CC BY 4.0. In
`github.com/TheEconomist/the-economist-war-fire-model`, find the output file of per-fire or per-cell war
classifications (look in the repo's output folders and the README; do not guess the path). If it is there:
`osint.fetch_econ_fires()` reads it in the build (stdlib, a raw.githubusercontent.com GET). In the Ukraine box,
add "+ The Economist's model also marks this as war-related" to `why`, and add +15 to the score when a detection is
within 1 km and 1 day of one of their war-related fires. Credit them in the drawer and the source list. Skip F3 if
no machine-readable output exists.

---

## F4. Series and the fixed test plan

### F4.1 The series

`firms_anom_{box}`: the daily count of S-NPP detections classed `anom` or `hot`.
- **History**: `python3 warwatch/fireref.py replay --box iran` re-runs `classify` over the archive, day by day,
  using **only reference data from years before each day's year**. The `d{YYYY}` columns and month masks exist for
  exactly this. It writes `backfill/data/firms_anom_{box}.csv`. To replay, the build step must keep a per-box
  detection archive. Keep a compact `warwatch/data/raw/fires_{box}_{YYYY}.csv.gz` (lat, lon, date, time, frp,
  daynight, type, bright_ti4) out of git: build it in the workflow, use it, discard it. Classification needs
  clusters and passes, so the replay groups by `acq_date` + `acq_time`.
- **Live**: in `catalog.py`, beside `_fires(th)`, add `firms_anom_{th}`. It is the daily count of `anom`+`hot` from
  the S-NPP map detections, cached as `firms_anom_events` the same way `firms_counts` does it. Seed it with
  `store.seed`. Label: "Unusual satellite fire detections per day, {theatre} (NASA FIRMS, classified)". Domain
  `geospatial`, `sub="Satellite"`. Add the prefix `firms_anom_` to `ZERO_WEIGHT` and to `catalog.SCALE` as a count.

### F4.2 Test plan (commit as `docs/FIREANOM_PLAN.md` BEFORE running the replay on 2022+)

Copy the Senkaku format. Fix in advance:
- **Calibration years 2018–2021**: tune only the weights and thresholds in F2 here. Then freeze them.
- **Test years 2022 to the archive end**: score `firms_anom_{box}` day by day with `stats.score_series`, as the build
  does. For each event in `events.csv` / `events_added.csv` whose theatre the box covers, take the highest z in the
  30 days before it. Compare against calm 30-day windows of the same theatre.
- **Pass rule per box**: the hit rate at z ≥ 2 beats the calm false-alarm rate with p < 0.05 / 7 (Bonferroni over
  seven boxes), and AUC > 0.55 on both event sets. A series that passes is put forward for the feature study; one
  that fails is recorded as failed and not tuned.
- **Case checks** (recorded, not part of the pass rule). Build `warwatch/data/fire_cases.csv` with `date, lat, lon,
  name, expect (anom|hot|ind), source` and a source link for each, as `events.csv` does. Verify every date and place
  from a published report before adding it. Candidates to verify:
  - Abqaiq and Khurais (Saudi Arabia), 14 Sep 2019 → `hot`
  - Shahran fuel depot (Tehran), 15 Jun 2025 → `anom` or `hot`
  - Hodeidah port fuel tanks (Yemen), 20 Jul 2024 → `anom` or `hot`
  - A Ukrainian drone strike on an oil depot inside the Ukraine box, e.g. Proletarsk (Rostov), Aug 2024 → `hot`
  - Controls, which must be `ind`: Baba Gurgur, Rumaila, Assaluyeh, on any ordinary day.
- **Precision audit**: draw 50 random `anom` detections from the test years. The owner reviews each with the
  Copernicus link (or the F5 chips) and labels it `conflict`, `industrial`, `farm/wild` or `cannot tell`. Report the
  shares. There is no pass mark. It tells us whether the label "unusual" can be trusted.

---

## F5. Satellite image check for anomalies (needs the shared imagery plumbing)

Build `S0` in [BASEWATCH_PLAN.md](BASEWATCH_PLAN.md#s0-shared-imagery-plumbing-also-used-by-fireclass-f5) first. It sets up the
`imagery.yml` workflow, the `imagery` branch and the chip writer. Then add `warwatch/firereview.py`
(numpy, rasterio, Pillow), which runs as the first step of `imagery.yml`:

1. Read `warwatch/history/cache/fire_anoms.csv`. Take clusters with score ≥ 60, younger than 21 days, with no final
   verdict in `fire_review.csv`. Take at most 25 per run, highest score first.
2. Build an area of 2.56 km × 2.56 km around the point. Search STAC `sentinel-2-l2a` (Planetary Computer, the same
   signing as `sar.py`) for the window `first_ts − 60 d … now`.
3. Per scene, compute the clear share inside the area from the `SCL` band. Clear means classes 4, 5, 6, 7 and 11;
   use the 20 m band.
   - **before** = the newest scene ending at least 1 day before `first_ts` with clear share ≥ 0.8.
   - **after** = the oldest scene after `first_ts` with clear share ≥ 0.8.
4. If both exist, compute NBR = (B08 − B12) / (B08 + B12) at 20 m, and dNBR = NBR_before − NBR_after over the
   central 1 km × 1 km. The burnt area is the pixel count with dNBR ≥ 0.27 × 0.04 ha. 0.27 is the usual
   "moderate severity" cut.
   Verdict:
   - `scar` when the burnt area is ≥ 1 ha;
   - `none` when it is under 0.2 ha;
   - `unclear` otherwise.
   If there is no clear after-scene yet → `wait`. After 21 days → `cloud`.
5. Land cover: read `esa-worldcover` (as `sar.py` does) in a 300 m radius and take the majority class →
   `cropland`, `built`, `bare`, `tree`, `grass`, `shrub`, `water`, `other`.
6. Chips via the S0 writer: `fires/{cid}_b.jpg` (before, true colour B04/B03/B02), `fires/{cid}_a.jpg` (after, true
   colour) and `fires/{cid}_s.jpg` (after, SWIR B12/B8A/B04). Each is 256 × 256 px covering 2.56 km.
7. Append to `warwatch/history/cache/fire_review.csv`:
   `cid,verdict,burn_ha,landcover,before_date,after_date,before_id,after_id,checked_at`.

Back in the build, `firecls` reads `fire_review.csv` and adjusts the class:
- `scar` + `cropland` → `seas`. Reason: "The satellite image shows a burnt field."
- `scar` + `built`/`bare` → keep the class. Add: "The satellite image shows a burn scar ({ha} ha) on {date}." Add +10 to the score.
- `none` → keep the class. Add: "No burn scar visible on {date}." Subtract 10 from the score.
- `wait`/`cloud` → "Waiting for a clear satellite image."

The page shows the chips in the fire drawer (before, after, SWIR) with their dates, captioned "Contains modified
Copernicus Sentinel data {year}". The image paths are `img/fires/{cid}_a.jpg`, etc. Store the field as
`img: {b, a, s, bd, ad}` and never as `u` or `url`.

Never say "confirmed strike". The image shows a burn scar; it does not show a cause.

**Done when:** a dispatch run reviews at least 10 real clusters, chips appear in the deployed page, and
`fire_review.csv` has verdicts.
