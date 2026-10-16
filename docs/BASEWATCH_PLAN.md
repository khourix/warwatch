# Base watch: implementation plan

Status: proposal, written 2026-10-15. Read [SATELLITE_PROPOSAL.md](SATELLITE_PROPOSAL.md) first for the why.
This file is the how, written for an implementer who has not seen the design discussion. The ground rules in
[FIRECLASS_PLAN.md](FIRECLASS_PLAN.md#ground-rules-from-this-repo) apply here too: the build stays stdlib-only; heavy
work goes in its own workflow; public data only; new series get zero weight until a fixed test plan passes; run
`verify.sh quick` before each commit and `full` before each PR.

Order: **S0 → B0 (go/no-go) → B1 → B2 → B3 → B4 → B5**. If B0 says no-go, build only S0, B1 and the image
part of B3 (a viewer for people to look at), and skip the automated alerts.

## As built (2026-10-15)

- **Diego Garcia has no Sentinel-1 coverage at all.** Planetary Computer lists no scenes in 2025 or 2026, so the site is
  optical only (state `optical`).
- **Radar revisit at Al Udeid**: two orbits. In mid-2025 each passed about every 12 days (Sentinel-1A only). Since
  mid-2026 each passes about every 6 days (1C + 1D).
- The feasibility windows start in December 2024, so every orbit has 8 earlier scenes before each case
  ([BASESPIKE_PLAN.md](BASESPIKE_PLAN.md)).
- `basewatch.ALERTS` stays `False` until the feasibility test says GO. Until then no site can be "out" or "in", the
  theatre counts stay empty, and the tell and alerts cannot fire. The layer still shows images and z values.
- `basewatch.layer()` is standard library only. The build calls it for the map payload.

## What the free imagery can and cannot see

| | Sentinel-1 radar (10 m) | Sentinel-2 optical (10 m) |
|---|---|---|
| Revisit, 2026 | 1C + 1D (1A retired June 2026). 1 to 3 days over Europe, about 3 days near the equator, counting both orbit directions. Same orbit geometry every 6 days. 2022–2024 had one satellite only (1B failed in Dec 2021), so history is sparser. | 2B + 2C, with 2A in an extension campaign to end-2027. 2 to 3 days at mid-latitudes, up to 5 at the equator. |
| Clouds and night | Sees through both | Blocked by cloud; daylight only (Olenya gets no light in winter) |
| What shows | Metal objects as bright points: parked large aircraft, ships alongside, vehicle parks. Texty.org.ua used it in 2021 to measure equipment build-up on Russian bases. | Large aircraft (Tu-95s at Olenya counted on a Feb 2024 Sentinel-2 image), ships, new earthworks and construction, burn scars |
| What does not show | Aircraft in hangars or shelters. Fighters show only as one or two bright pixels. Identity. | The same, plus anything under cloud |

The Al Udeid case (from about 40 aircraft to 3, around 19 June 2025) was seen in **Planet** imagery (paid), not
Sentinel. Whether 10 m radar sees it is unproven. That is why B0 comes first.

Data access (no key): Microsoft Planetary Computer STAC with anonymous SAS signing. `warwatch/sar.py` already reads
`sentinel-1-rtc` and `esa-worldcover` this way in production every night. For `sentinel-2-l2a` use Planetary
Computer, with Element 84 Earth Search `https://earth-search.aws.element84.com/v1` collection `sentinel-2-c1-l2a`
as the fallback. A user reported Planetary Computer's Sentinel-2 running 10 days late in April 2026. Licence:
Copernicus Sentinel data is free and open; captions must say "Contains modified Copernicus Sentinel data {year}".

---

## S0. Shared imagery plumbing (also used by FIRECLASS F5)

1. **Workflow** `.github/workflows/imagery.yml`. Copy `sar.yml`, then change:
   - cron `40 */6 * * *` plus `workflow_dispatch` (inputs: `only` = `fires|bases|all`, `dry_run`);
   - concurrency group `warwatch-imagery`;
   - install `numpy scipy rasterio pillow`;
   - steps, each `continue-on-error: true`, so one failing does not block the other:
     `python3 warwatch/firereview.py` (once F5 exists), then `python3 warwatch/basewatch.py`;
   - commit CSVs to `main`: `warwatch/history/basewatch_*.csv`, `warwatch/history/cache/base_*`,
     `warwatch/history/cache/bases_*`, `warwatch/history/cache/fire_review.csv`. Use the same retry loop as `sar.yml`.
   - push chips: see 3.
2. **Shared helpers** `warwatch/imagery.py`:
   - `stac_search(collection, bbox, start, end)`: POST to Planetary Computer, with retry on 429/5xx. Copy `sar._post`
     and `sar._open`. When `collection` starts with `sentinel-2`, fall back to Earth Search on failure or when the
     newest scene is more than 7 days old.
   - `sign(href)`: Planetary Computer only; Earth Search hrefs are public.
   - `read_window(href, bbox_lonlat, res_m)` → `(array, transform, crs)`: a windowed read in the scene's CRS, as in
     `sar.count_scene`.
   - `clear_share(item, bbox)`: Sentinel-2 SCL band at 20 m. Clear means classes 4, 5, 6, 7 and 11.
   - `chip(item, bbox, bands, path, stretch)`: 256 × 256 px JPEG, quality 80. True colour = B04, B03, B02 with a
     2–98 percentile stretch per band. SWIR = B12, B8A, B04. Radar chip = VV in dB, stretched −25 to +5 dB, greyscale.
3. **Chip storage**: the orphan branch `imagery`, overwritten each run, so git history does not grow.
   - Chips are written into `chips/` in the job, as `chips/fires/...` and `chips/bases/...`.
   - Before pushing, delete fire chips older than 21 days and keep base chips for the current set only. Then:
     ```
     cd chips && git init -q && git checkout -q -b imagery && git add -A && git -c user.name=warwatch-bot -c user.email=warwatch-bot@users.noreply.github.com commit -qm "imagery $(date -u +%FT%H:%MZ)"
     git push -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" imagery
     ```
   - Restore the previous chips at the job's start: `git fetch --depth 1 origin imagery && git --work-tree=chips checkout FETCH_HEAD -- .` (ignore failure on the first run).
   - Size budget: about 40 KB per chip. Fires up to about 75 clusters × 3 chips; bases 30 × 4. Under 15 MB in total.
4. **Pages build** (`warwatch.yml`): add a step before `actions/upload-pages-artifact`:
   ```
   - name: Imagery chips (optional)
     run: |
       mkdir -p site/img
       git fetch --depth 1 origin imagery && git --work-tree=site/img checkout FETCH_HEAD -- . || echo "no imagery yet"
   ```
   The page loads `img/fires/...` and `img/bases/...` by relative path. Write image references into the data as `img`
   objects. Never use `u` or `url`, because the verify check `links-data` requires those to be http(s). The demo render
   has no chips; the page must show a "No image yet" placeholder when a chip 404s (`<img onerror>`).
5. **Attribution**: add rows to the source list in `dashboard.py`: "Copernicus Sentinel-1/-2 (ESA), via Microsoft
   Planetary Computer and Element 84 Earth Search: free and open", and "OpenStreetMap contributors (ODbL): base
   outlines".

Test (`TestImagery`): the `clear_share` maths on a synthetic SCL array; the chip stretch on a synthetic array
(output 256 × 256, 3 bands, uint8).

**Done when:** a dispatch run with `only=bases` (after B1) pushes `imagery`, and the next Pages build serves
`img/bases/<id>_a.jpg`.

---

## B0. Feasibility test (go/no-go), before building B2–B4

Script `warwatch/basespike.py` with workflow `basespike.yml` (dispatch only; installs numpy, scipy, rasterio,
pillow, matplotlib). It writes `docs/BASESPIKE.md`, plots and chips as a workflow artifact. **Commit the go/no-go
rule (below) before running it.**

Cases. Verify each date from a published report before the run, and cite it in `BASESPIKE.md`:

| Case | Window | Expected change |
|---|---|---|
| Al Udeid, Qatar: aircraft dispersed before Iran's strike on the base (around 19 to 23 Jun 2025) | 2025-04-01 to 2025-07-15 | apron bright area falls |
| NSA Bahrain / Mina Salman: US ships left port (around 26 Feb 2026, per `tells.py`) | 2025-12-15 to 2026-03-15 | harbour bright area falls |
| Diego Garcia: B-2 deployment (reported from late March 2025) | 2025-02-01 to 2025-05-31 | apron bright area rises |
| Olenya, Russia: bombers present, then the 1 Jun 2025 drone strike (Operation Spiderweb) | 2025-04-01 to 2025-07-15 | high before; bright area falls and burn scars after |

For each case, draw an apron and harbour outline by hand in `warwatch/data/bases_spike.json` (GeoJSON, lon/lat)
from OSM `aeroway=apron` / harbour polygons. Then, for every scene in the window:
- **Sentinel-1 RTC** (VV and VH, native 10 m, no downsampling): `bright_m2` = apron or harbour pixels with
  VV dB ≥ `T`, × 100 m². `blobs` = connected bright components of 3 to 150 pixels. Try `T` in {−6, −3, 0, +3} dB
  and report all four. Group by `sat:relative_orbit` + `sat:orbit_state`; never compare across orbits.
- **Sentinel-2 L2A**, scenes with apron clear share ≥ 0.9: a true-colour chip, plus `dark_px` / `bright_px` = apron
  pixels more than 0.06 reflectance below or above the apron median in B04 (aircraft are darker or brighter than
  concrete).

Output per case: a table of date, orbit and the metrics; a plot per metric with the case date marked; chips at the
nearest clear dates before and after.

**Go rule (fixed in advance).** In each case, z = (value − median of the same orbit's previous 8+ scenes) /
(1.4826 × MAD), with MAD floored at 5% of the median. GO if, for at least 2 of the 3 leading cases (Al Udeid,
Bahrain, Diego Garcia), the best `T` gives z ≥ 2.5 in the expected direction on some scene within ±7 days of the
case date, **and** that `T` gives |z| ≥ 2.5 on no more than 10% of the other scenes in the window. Olenya is
reported but does not count; it tests damage, not warning. Pick `T` and the metric (bright area or blobs) from the
spike, and freeze them in `basewatch.py`.

If NO-GO: write up why in `BASESPIKE.md`. Then build S0, B1 and a reduced B3 (a map layer with the latest chips
and Copernicus links, no status colours), and drop B2's alerts, B4 and the tell.

---

## B1. Site registry

Hand-written seed `warwatch/data/bases_seed.csv`:
`id,name,lat,lon,kind,side,theatres,why`.
- `kind`: `air`, `naval`, `air+naval`, `launch` or `port`.
- `side` is who operates it (plain text).
- `theatres` is a `;` list of `config.THEATRES` keys whose risk the site informs.

Coordinates below are approximate (±1 km). B1's script snaps them to OSM. The owner confirms the review sheet
before B2 runs.

| id | name | lat, lon | kind | side | theatres |
|---|---|---|---|---|---|
| al_udeid | Al Udeid Air Base, Qatar | 25.117, 51.315 | air | US/Qatar | iran;gulf |
| al_dhafra | Al Dhafra Air Base, UAE | 24.248, 54.548 | air | US/UAE | iran;gulf |
| prince_sultan | Prince Sultan Air Base, Saudi Arabia | 24.063, 47.580 | air | US/Saudi | iran;gulf;yemen |
| ali_al_salem | Ali Al Salem Air Base, Kuwait | 29.347, 47.521 | air | US/Kuwait | iran;iraq |
| muwaffaq_salti | Muwaffaq Salti Air Base, Jordan | 31.827, 36.782 | air | US/Jordan | iran;syria;israel |
| nsa_bahrain | NSA Bahrain and Mina Salman port | 26.205, 50.610 | naval | US | iran;gulf |
| diego_garcia | Diego Garcia | -7.313, 72.411 | air+naval | US/UK | iran;yemen |
| akrotiri | RAF Akrotiri, Cyprus | 34.590, 32.988 | air | UK | yemen;israel;lebanon;syria |
| incirlik | Incirlik Air Base, Turkey | 37.002, 35.426 | air | US/Turkey | syria;iran |
| lemonnier | Camp Lemonnier, Djibouti | 11.547, 43.159 | air | US | yemen |
| souda | Souda Bay, Crete | 35.532, 24.150 | air+naval | US/Greece | israel;lebanon |
| nevatim | Nevatim Air Base | 31.208, 35.012 | air | Israel | israel;iran;lebanon |
| ramon | Ramon Air Base | 30.776, 34.667 | air | Israel | israel;iran |
| hatzerim | Hatzerim Air Base | 31.234, 34.663 | air | Israel | israel |
| bandar_abbas | Bandar Abbas: 9th air base and naval base | 27.218, 56.378 | air+naval | Iran | iran;gulf |
| isfahan_8tab | Isfahan 8th Tactical Air Base | 32.751, 51.861 | air | Iran | iran |
| hamadan_3tab | Hamadan (Nojeh) 3rd Tactical Air Base | 35.211, 48.653 | air | Iran | iran |
| tabriz_2tab | Tabriz 2nd Tactical Air Base | 38.134, 46.235 | air | Iran | iran |
| dezful_4tab | Dezful (Vahdati) 4th Tactical Air Base | 32.434, 48.398 | air | Iran | iran;iraq |
| bushehr_6tab | Bushehr 6th Tactical Air Base | 28.945, 50.835 | air | Iran | iran;gulf |
| semnan_space | Imam Khomeini Spaceport, Semnan | 35.234, 53.921 | launch | Iran | iran |
| jask | Jask naval base | 25.650, 57.770 | naval | Iran | iran;gulf |
| ain_al_asad | Ain al-Asad Air Base, Iraq | 33.786, 42.441 | air | Iraq/US | iraq;iran |
| hmeimim | Hmeimim Air Base, Syria | 35.401, 35.949 | air | Russia | syria |
| hodeidah | Hodeidah port, Yemen | 14.830, 42.930 | port | Houthis | yemen |
| engels | Engels-2 Air Base | 51.481, 46.200 | air | Russia | ukraine |
| olenya | Olenya Air Base | 68.152, 33.464 | air | Russia | ukraine |
| shaykovka | Shaykovka Air Base | 54.226, 34.371 | air | Russia | ukraine |
| mozdok | Mozdok Air Base | 43.787, 44.603 | air | Russia | ukraine |
| novorossiysk | Novorossiysk naval base | 44.700, 37.790 | naval | Russia | ukraine |

Why these: clear skies for optical, published past cases, and coverage of both sides. The US/allied hubs empty or
fill before strikes on Iran and Yemen; Iranian bases disperse; Russian bomber bases move aircraft before mass
missile waves. Extra theatres come in B5.

Script `python3 warwatch/basesites.py build` (stdlib):
1. For each seed, query Overpass within 4 km for: `landuse=military`, `military=*`, `aeroway=aerodrome`,
   `aeroway=apron`, `man_made=pier`, `landuse=harbour`, `harbour=yes`, `natural=water`. Sleep 30 s between queries
   and send a User-Agent.
2. **Base outline** = the military or aerodrome polygon that contains, or is nearest to, the seed point.
   **Aprons** = `aeroway=apron` polygons inside or touching the outline. **Harbour** (naval/port) = water polygons
   within the outline + 1 km, clipped to a 1.5 km radius around the piers, plus the piers buffered by 60 m.
3. Simplify the polygons (Douglas–Peucker, 5 m) and write `warwatch/data/bases.json`: a list of
   `{id, name, lat, lon, kind, side, theatres, why, outline, aprons, harbour, apron_m2, src}`.
4. If no apron is found, write `aprons: []` and flag the site in the review sheet. The owner then draws aprons by
   hand in a GeoJSON file `warwatch/data/bases_manual.geojson`, which wins over OSM. OSM mapping of military sites
   in Russia, Iran and China is uneven, so expect several such sites.
5. Write `docs/BASES_REVIEW.md`: one row per site with the apron area, harbour area, the OSM ids, a Copernicus
   Browser link (S0 link format) and an "OK?" column for the owner.

Licence: `bases.json` contains OSM-derived geometry, so the ODbL attribution goes in the file's `src` field and the
page's source list.

---

## B2. Monitoring job

`warwatch/basewatch.py` (numpy, scipy, rasterio, pillow) runs in `imagery.yml`. Use `sar.py` as the model:
remember done scenes in a CSV and process a budget per run.

**Radar, per new Sentinel-1 RTC scene that covers a site's apron or harbour:**
- Window = the site outline's bounding box + 200 m. Read VV and VH at native 10 m. Rasterise apron and harbour
  polygons to the window with `rasterio.features.rasterize`.
- `area_m2` = valid pixels × 100 inside the polygons. `bright_m2` = pixels with VV dB ≥ `T` (frozen in B0) × 100.
  `blobs` = connected components of 3 to 150 bright pixels.
- Skip the scene for that site if `area_m2` < 50% of the polygon area (the scene clips it).
- Append to `warwatch/history/basewatch_scenes.csv` (append-only, union merge):
  `scene_id,site,date,orbit,part,area_m2,bright_m2,blobs`. `orbit` = `A` or `D` + relative orbit number (e.g.
  `A087`); `part` = `apron` or `harbour`.
- Budget: 120 scene-site reads per run. Order: newest scenes first for the live window, then backfill oldest-first.

**Optical, per Sentinel-2 L2A scene with clear share ≥ 0.9 over the outline:**
- `chg_ha`: pixels in the outline where max(|Δ B02|, |Δ B04|, |Δ B08|, |Δ B11|) > 0.06 against the per-pixel
  median of the previous 3 clear scenes (B11 resampled to 10 m). This catches construction, earthworks and new camps.
- `burn_ha`: dNBR ≥ 0.27 against the previous clear scene, at 20 m.
- Append to `warwatch/history/basewatch_optical.csv`: `scene_id,site,date,clear,chg_ha,burn_ha`.
- Chips: keep `bases/{id}_a.jpg` (latest clear true colour), `bases/{id}_b.jpg` (a clear scene 25 to 60 days
  earlier), `bases/{id}_r.jpg` (latest radar VV chip) and `bases/{id}_rb.jpg` (radar from the same orbit, 25 to 60
  days earlier). Write the dates to `warwatch/history/cache/base_chips.csv`: `site,kind,date,scene_id`.

**Scores (also in `basewatch.py`, written to caches the build reads):**
- Per scene: `z` = (metric − median of the same site, part and orbit over the previous 8 to 20 scenes within 240
  days) / (1.4826 × MAD), with MAD floored at 5% of the median and 200 m². Leave `z` empty if there are fewer than 8
  previous scenes. Metric = the one frozen in B0.
- Per site and day: `warwatch/history/cache/base_{id}.csv` (date, z), using the mean z of that day's scenes.
- **Change state** per site:
  - `out` when the latest two scored scenes within 7 days (any orbits) both have z ≤ −2.5;
  - `in` when both have z ≥ +2.5;
  - `changed` when only one does;
  - `normal` otherwise;
  - `nodata` when there is no scored scene in 10 days.
  Requiring two scenes cuts single-scene noise.
- Per theatre: `bases_out_{t}.csv` and `bases_in_{t}.csv` (date, count of sites in that state that day, over the
  sites whose `theatres` list includes `t`). Write a 0 for every day the theatre had at least one scored scene.
- Optical flag (does not change the state): a site gets the note "New construction or earthworks" when `chg_ha` is
  ≥ 3 × its median and ≥ 2 ha. It gets "Burn scars" when `burn_ha` ≥ 1.

**Backfill**: `basewatch.py --backfill-from 2022-01-01 --site <id>`, dispatched as a matrix over sites
(`max-parallel: 10`). Estimate: 30 sites × about 10 scenes a month × 46 months ≈ 14,000 reads at 2 to 4 s each. That
is about 30 minutes per site job.

Tests (`TestBaseWatch`): bright-area and blob counts on a synthetic dB array with three "aircraft" blobs, a
building edge outside the apron and noise; the orbit grouping (no z across orbits); the two-scene state rule; the
MAD floor; and that the theatre counts include each site only in its own theatres.

---

## B3. Dashboard

Build side (stdlib), in `extras.py` / `dashboard.py`:
- Read `bases.json`, `base_{id}.csv`, `base_chips.csv`, the latest optical row and the state.
- Map payload `bases`: `[{id, n, xy, th (first theatre), ths, k (kind), side, st (out|in|changed|normal|nodata),
  z (latest), last (latest scene date), pts (last 30 z values), why (plain sentence), note (optical note),
  img: {a, ad, b, bd, r, rd, rb, rbd}, ll: [lat, lon]}]`.
- `why` by state:
  - `out`: "Radar shows far fewer bright objects on the aprons than usual on two passes ({dates}). Aircraft may have left."
  - `in`: "... far more than usual ... Aircraft or vehicles may have arrived."
  - naval: use "in the harbour" and "ships".
  - `changed`: "One radar pass differed from usual ({date}); waiting for the next pass to confirm."
  - `normal`: "In its usual range."
  - `nodata`: "No usable radar pass in 10 days."
- `demo.py`: add about 6 demo bases covering all states (no `img`).

Page (`page.html`):
- A new map layer `bases` ("Military bases (satellite)", in the "Warnings and ground" group, default on). Add an
  icon `base` to the icon set (search `fire:'<path`). Marker colour: grey for `normal`/`nodata`, the existing
  warning purple for `changed`, and the strong pink (`--c-strong`) for `out`/`in`. No other new colours; see
  `docs/COLOUR.md`.
- Drawer: name, side, kind, state sentence, optical note, a sparkline of `pts`, chip pairs (radar before/after,
  optical before/after) with dates and the caption "Contains modified Copernicus Sentinel data {year}", and buttons
  "Copernicus Browser" (at the site, last 30 days; same URL format as the fire drawer) and "Theatre".
- Alerts: one alert per site in state `out` or `in`: "{name}: aircraft may have {left|arrived} (radar, {date})".
- Activity page: a "Bases" card listing sites sorted by |z|, with the state and the last scene date.
- The help text (search `Reading the map`): one line saying what the base layer shows and its limits ("10 m
  images; aircraft in shelters do not show; a change is a reason to look, not proof").

---

## B4. Series, tell and the fixed test plan

1. `catalog.py`: add `bases_out_{t}` and `bases_in_{t}` for each theatre that has sites. Read them from cache like
   `_sar`. Daily, geospatial, `sub="Satellite"`, label "Bases with far fewer aircraft than usual, {theatre}
   (Sentinel-1 radar)" / "... far more ...". Add the prefix `bases_` to `ZERO_WEIGHT` and as a count in `SCALE`.
2. `tells.py`: turn on the existing `bases` tell. It currently has `series: []` and `rule: None`:
   ```python
   {"id": "bases", "name": "Aircraft leave a named base, ships leave port",
    "series": ["bases_out_{t}", "bases_in_{t}"], "rule": lambda p, d: any(v >= 1 for v in _before(p, d, 0, WINDOW - 1)),
    "says": "Radar images show a watched base with far fewer, or far more, aircraft or ships than usual, on two passes.", ...}
   ```
   `_arity` = 1, so the tell fires when either series fires. Keep `cases`. Run `python3 warwatch/tells.py record` to
   refresh `data/tells_record.json` and `docs/TELLS.md`.
3. **Commit `docs/BASEWATCH_STUDY_PLAN.md` before the backfill's results are read.** Use the Senkaku format:
   - events from `events.csv` + `events_added.csv` from 2022-03-01, in theatres with at least one site;
   - hit = `bases_out` or `bases_in` ≥ 1 in the 14 days before the event;
   - compare with calm 14-day windows in the same theatre;
   - pass when the hit rate beats the calm rate with p < 0.05 (one-sided Fisher) **and** the tell fires in no more
     than 15% of calm windows;
   - also report each B0 case and the per-site firing count.
   A failed result is recorded and not tuned.

---

## B5. Expansion (after B4, or by owner decision)

**As built (2026-10-16): 120 sites.** 90 seeds were added to `bases_seed.csv`, by theatre: Taiwan Strait 13 (Fujian
air bases, Taiwan's main air and naval bases, Kadena, Andersen), South China Sea 9 (Yulin, Zhanjiang, the Paracel and
Spratly islands, Philippine and Vietnamese bases), Korea 7 (Sunan, Sohae, Wonsan-Kalma, Sinpo, Osan, Kunsan, Jinhae),
Eastern flank 6 (Rzeszow, Powidz, Kogalniceanu, Siauliai, Amari, Chkalovsk), Russia, Belarus and Ukraine 20 (Belbek,
Saky, Sevastopol, Baltiysk, Soltsy, Severomorsk, the Su-34 and MiG-31K bases, Belaya, Ukrainka, Machulishchy and four
Ukrainian air bases), Venezuela and the Caribbean 4 (with Roosevelt Roads), India and Pakistan 8, Libya 4, Sudan 4,
and 15 more in the Middle East and Red Sea.
- Each seed point was checked against OpenStreetMap (QLever): the aerodrome or naval base within 3 km by name.
  Longtian and Shuimen were found by name; Konarak and Jinhae seeds moved to the naval bases.
- `harbour_lat`/`harbour_lon` in the seed name a second point for air+naval sites whose piers lie away from the
  airfield (Souda, Bandar Abbas, Cam Ranh, Port Sudan, Berbera). Naval sites now accept OSM port outlines.
- Hand-drawn from Sentinel-2 in `bases_manual.geojson`: aprons at Shaykovka, Chiayi, Tel Nof and Al Jufra (plus Al
  Jufra's outline) and the harbour at Jinhae. The record's `src` names them.
- Radar reads per window: a site whose parts lie more than 12 km apart gets one window per part.
- `imagery.yml`'s budget of 120 radar reads per run gives one new scene per site per run (four runs a day), which
  keeps up with the 6-day repeat of each orbit.

- More sites: up to about 80 to 120 in total. Taiwan Strait (Fujian air bases, Yulin on Hainan), Korea (Sunan,
  Sohae launch site, Wonsan-Kalma), the Eastern flank, more Russia (Belbek, Saky, Sevastopol, Baltiysk, Soltsy) and
  Venezuela. Cloudy regions run on radar only.
- **Ground forces**: vehicle parks near borders (as Texty did in 2021). Use the radar metric over a polygon of the
  park. Same pipeline, `kind=ground`.
- **Free high-resolution extras**: Umbra's open SAR archive (CC BY 4.0, public bucket, `sar-data/tasks/...`) has a
  few scenes over sites such as Bandar Abbas and Bushehr (Dec 2025). Optionally list any Umbra or Capella open scene
  that falls inside a site outline in the drawer as "High-resolution image available ({date})". This is ad hoc only,
  not monitoring.
- **ADS-B per base** (already collected for boxes): departures from a named base would corroborate the radar state.
  This is a separate study.
