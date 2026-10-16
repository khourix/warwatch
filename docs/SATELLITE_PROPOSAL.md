# Proposal: telling strikes from flares, and watching military bases from space

Written 2026-10-15 for the owner's approval. Free data only. Implementation plans:
[FIRECLASS_PLAN.md](FIRECLASS_PLAN.md) (fires) and [BASEWATCH_PLAN.md](BASEWATCH_PLAN.md) (bases).

Decisions already made (owner, 2026-10-15):
- Start with a pilot of about 30 bases.
- Show image chips plus links.
- New signals go on the map and into the tells; they enter the model only if they pass a fixed test.
- Explained fires stay on the map, faded, with a filter to hide them.

## 1. Fires: which ones matter

**The problem.** The map shows every NASA FIRMS heat detection in seven theatre boxes. Most are gas flares,
refineries, steel works and farm burning. Today one rule separates them: a ~2 km cell that burned on 3 of the last
7 days is "routine". That rule fails both ways:
- A flare that was off for a week shows as new.
- A town shelled three days running turns "routine" and fades.
- A strike on a refinery looks like the refinery's normal flare.

**Is fire power (MW) enough?** No. Flares, small strike fires and farm fires all fall in the same range, a few MW
to a few tens of MW per pixel. No published source gives a clean FRP range for flares. FRP helps in one place:
**a known site burning far hotter than its own normal** (Abqaiq 2019, a fuel depot hit by a drone).

**What separates them is history and place.** Methods assessed:

| Method | Verdict | Why |
|---|---|---|
| NASA's own "static source" flag (`type` = 2 in the archive) plus 14 years of history per 1 km cell | **Use (core)** | Free, no key, back to 2012. A flare burns on most days, year after year. A strike site does not. |
| Map of industrial and sensitive sites: OpenStreetMap, World Bank flare list, Global Energy Monitor, WRI power plants | **Use** | Names the source ("gas flare at Rumaila") and finds fires at military sites, depots, ports and substations. These count more, not less. |
| Seasonal history per 10 km area and month (farm burning) | **Use** | Ukraine, Syria and Iraq burn stubble in the same months every year. The baseline leaves out war years, so the front line is not learned as "normal". |
| Hotter than its own normal at a known site | **Use** | Catches strikes on refineries and depots, which a plain flare mask would hide. |
| Sentinel-2 before/after images for each anomaly: burn scar check, land cover, image chips | **Use (for the top anomalies)** | 10 m images, free. Shows a burn scar in a town or a burnt field. 2 to 5 days later, and blocked by cloud. |
| The Economist's open war-fire model (MIT code, CC BY data) | **Optional second opinion for Ukraine** | It uses the same idea (expected fires per cell) and is updated several times a day. Reading its output is cheap. Retraining it ourselves is not. |
| VIIRS Nightfire flame temperature (flares burn at about 1,400–1,800 K, vegetation at about 1,000 K) | **Not now** | Since Jan 2025 it needs a licence application (free for non-commercial use). Add it later if the history rules miss flares. |
| Flare goes dark (production stopped) | **Later** | A real signal after strikes on gas fields. It needs cloud handling first. |

**What you get.**
- Each fire gets one of six classes, a score and a reason in plain words. The map shows **anomalies** bright,
  **unexplained** fires as normal dots, and **explained** fires (industry, farm burning, volcano, offshore) as faint
  rings you can hide.
- Each fire opens straight in Copernicus Browser (Sentinel-2) and NASA Worldview. The top anomalies get
  before/after image chips and a burn-scar verdict.
- A new daily series, "unusual fires per theatre". It is tested against our event list under a test plan fixed
  before results are read (2018–2021 for tuning, 2022+ for the test).

**Limits.**
- Clouds hide fires from VIIRS and from Sentinel-2.
- A small strike can leave no visible scar.
- "Unusual" means "worth a look", not "an attack". Wording on the page never says "confirmed strike".

## 2. Military bases: change as a leading indicator

**The idea.** Before strikes, bases change: aircraft disperse or surge, ships leave port, camps and earthworks
appear. Al Udeid emptied on 19 June 2025, four days before Iran struck it, and every US ship left Bahrain on 26
February 2026, two days before strikes. WarWatch already lists "aircraft leave a named base, ships leave port" as a
timing tell, marked "not watched yet".

**What free imagery can do.** Methods assessed:

| Method | Verdict | Why |
|---|---|---|
| **Sentinel-1 radar** (10 m, sees through cloud, day and night, every 1 to 3 days): bright metal objects on aprons and in harbours, compared with the same orbit's recent passes | **Use (core)** | Already working in `sar.py` for ships. Texty.org.ua used it in 2021 to measure Russian equipment build-up. All weather, so Europe and Korea are covered too. |
| **Sentinel-2 optical** (10 m, every 2 to 5 days, when clear): image chips, construction and earthworks, burn scars | **Use** | People can read it. Large aircraft show (Tu-95s at Olenya were counted on Sentinel-2 in Feb 2024). |
| Free high-resolution radar (Umbra, Capella open data) | **Extra, when present** | Under 1 m and CC BY, but only a handful of one-off scenes over a few sites. |
| Machine-learning aircraft detection | **No** | At 10 m a fighter is one or two pixels. Change statistics work better than object detection here. |
| Planet, Maxar, Airbus | **Excluded** | Paid. Planet's free NICFI programme ended in 2025, and it covered the tropics only. |

**What 10 m cannot do.**
- It cannot count fighters or identify types.
- Aircraft in hangars and shelters do not show.
- The Al Udeid emptying was seen in Planet's paid imagery. **Whether free radar sees it is unproven.**

So the plan starts with a **go/no-go test** on four known cases (Al Udeid 2025, Bahrain 2026, Diego Garcia 2025,
Olenya 2025), with the pass rule written before the test runs.
- **Go**: build the 30-site monitor, the base layer, alerts and the tell, then a fixed test against our event list.
- **No-go**: keep a base layer with the latest images for people to look at, and no automated alerts.

**Pilot sites (30).**
- US and allied hubs: Al Udeid, Al Dhafra, Prince Sultan, Ali Al Salem, Muwaffaq Salti, Bahrain, Diego Garcia,
  Akrotiri, Incirlik, Djibouti, Souda.
- Israel: Nevatim, Ramon, Hatzerim.
- Iran: Bandar Abbas, Isfahan, Hamadan, Tabriz, Dezful, Bushehr, Semnan spaceport, Jask.
- Iraq, Syria and Yemen: Ain al-Asad, Hmeimim, Hodeidah.
- Russian bomber and fleet bases: Engels, Olenya, Shaykovka, Mozdok, Novorossiysk.

Most of these sites have clear skies, several have published past cases, and they cover both sides. Taiwan, Korea
and more Russia come after the test.

## 3. Shared plumbing, cost and order

- A new workflow, `imagery.yml`, runs every 6 hours (numpy, rasterio, pillow). The dashboard build stays
  standard-library only.
- Image chips (about 40 KB each, under 15 MB in total) live on a separate `imagery` branch that is overwritten each
  run, so the repo does not grow. The Pages build copies them into the site.
- Cost: GitHub Actions minutes only, plus the existing free FIRMS key. Everything else is open data with no key:
  - NASA FIRMS archive files;
  - Copernicus Sentinel-1/-2 via Microsoft Planetary Computer, with Element 84 as the fallback;
  - OpenStreetMap;
  - World Bank;
  - WRI;
  - Global Energy Monitor (free form).
- Attribution: Copernicus, OpenStreetMap (ODbL) and Global Energy Monitor and WRI (CC BY 4.0) are credited on the
  page.

**Build order:**
1. Fires F1 (reference tables).
2. Fires F2 (live classes on the map). This is the first visible win and needs no imagery.
3. Fires F3 (optional, the Economist second opinion).
4. Fires F4 (series and test).
5. S0 (imagery plumbing).
6. Bases B0 (go/no-go).
7. Bases B1 to B4.
8. Fires F5 (image checks).
9. Bases B5 (expansion).

One PR per stage. Each stage in the plans lists its files, data formats, thresholds, tests and a "done when" check.

**Risks.**
- Planetary Computer has run late on Sentinel-2 at times; Element 84 is the fallback.
- OSM outlines of military sites in Russia, Iran and China are patchy. A review sheet and hand-drawn aprons cover
  the gaps.
- Overpass and FIRMS file names must be checked live at the start. This sandbox could not reach them; F1.0 does
  that check first.

## 4. Built and tested (2026-10-15)

**Fires: built (F1–F5).**
- Every map fire now has a class, a score and a reason. The map reads all three VIIRS satellites.
- Explained fires fade, and a layer switch hides them. Each fire links to Copernicus Browser and NASA Worldview.
- `imagery.yml` checks the top anomalies against Sentinel-2. Tested on the Shahran depot strike (Tehran, 14 June 2025): it
  found clear images on 12 and 15 June, the smoke plume over the tank farm and the fire in short-wave infrared
  ([docs/firereview/](firereview/)).
- Three rule bugs were found and fixed before the event test, each recorded in [FIREANOM_PLAN.md](FIREANOM_PLAN.md):
  - water detections were treated as "offshore";
  - waterside steel works were treated as "offshore";
  - a city fire was called a farm fire.
- Case checks:
  - the flare controls pass;
  - Abqaiq 2019 and Hodeidah 2024 left no unusual heat in the S-NPP archive (a data limit);
  - Shahran 2025 comes out "unexplained" until OpenStreetMap depots are in the site list.
- **Event test: fails** ([FIREANOM.md](FIREANOM.md)). Unusual-fire counts rose before 70% of the original events
  (p = 0.016). On the added events they did no better than calm periods (53% against 50% false alarms). The daily counts
  are small and jumpy.
- Because of that, `firms_anom_<box>` stays at zero weight. The classes stay on the map as a reading aid. That was the
  main aim: telling a flare from a fire worth a look.
- The test ran without OpenStreetMap sites, because Overpass was overloaded all day (fourth amendment). The monthly
  `fireref.yml` run rebuilds the sites and the replay, and the test can then be run again.

**Bases: feasibility test NO-GO** ([BASESPIKE.md](BASESPIKE.md)).
- Free radar caught 2 of 3 leading cases. Al Udeid's two passes before the June 2025 strike both fell to z −2.7. But
  single-scene false alarms were 10.3% against a 10% limit.
- As the plan says, the base layer is an image viewer: 30 sites, radar and optical chips every 6 hours, the latest radar
  z as text, and no alerts or tell.
- A fixed test of the two-pass rule is suggested.

**For the owner.**
1. Read [BASES_REVIEW.md](BASES_REVIEW.md) for the 120 sites and mark the rows that look right.
2. Optional: Global Energy Monitor's oil and gas, steel and coal trackers ask for an email on a form, so they were not
   downloaded. OpenStreetMap through QLever now covers plants and depots. If you want them, download them into
   `warwatch/data/raw/` and run `python3 warwatch/fireref.py sites`.
3. Precision audit: label 50 random "unusual" fires, as in FIREANOM_PLAN.md.

## 5. Follow-ups done (2026-10-16)

- **OpenStreetMap fixed.** Overpass servers only admit a query when the memory and time it declares are free, and ours
  declared 1 GB and 600 s, so they were refused all day. One server also cuts cloud connections and the mirrors were down.
  OSM now comes from QLever (University of Freiburg's SPARQL copy of the planet), with small Overpass queries as the
  fallback (`warwatch/osmsource.py`). The fire site list has 51,676 sites, and every base box answers.
- **Missing aprons**: four of the six now come from OSM. Shaykovka was drawn by hand. Semnan is a launch site and has no
  aprons. Souda and Bandar Abbas now find their naval piers, and Hodeidah has a port outline.
- **Strike cases** have source links in `fire_cases.csv`.
- **Bases B5**: 120 sites (see BASEWATCH_PLAN.md, B5).
- **Fire test rerun with OSM sites**: still fails (added events 57% against 51% calm false alarms). Shahran now scores
  55 near "Fuel tanks", just under the bar of 60 ([FIREANOM_PLAN.md](FIREANOM_PLAN.md)).
- **Hand runs**: `fireref.py replay`, `cases` and `econ` ran here. `imagery.yml` ran on GitHub runners with the repo's
  FIRMS key, through temporary branch workflows, because a workflow must be on main before it can be started by hand.
  The image chips are on the `imagery` branch. The runs found and fixed:
  - **`imagery.yml` and `fireref.yml` committed nothing.** One unmatched path in a single `git add` made it stage nothing,
    and the error was hidden. Files are now added one at a time.
  - **Offshore flares marked unusual.** New South Pars platforms flare every night and have no fire on record before
    2026. Fixed with OpenStreetMap platforms in the site list, and open water in the image check now reads as offshore.
  - **Base chips.** Most sites had no "before" image, and naval sites were framed on a small compound instead of the
    harbour. Both are fixed.
  - **Optical change measure.** It counted haze, sun glint, cloud outside the aprons and the season as "construction",
    and the note fired at 46 sites. It is now measured on the base's clear land only. It compares visible bands against
    clear scenes from the last 30 days, after taking out each scene's overall shift. Only brightening counts, and burns
    must be dark. The note needs two different days. Al Dhafra's 944 ha of false change became 4, and the notes went
    from 46 sites to a few.
  - **Run time.** Planetary Computer's anonymous signing limits requests per IP. Signing every file met "too many
    requests" and 85 s of retry waits on about every other read, and live runs read 8–11 optical scenes per site. With
    120 sites a 6-hourly run would have needed many hours. Now one token per storage container, and live runs read only
    sites with a new scene: about 5 minutes a run.
  - **Radar history.** Sites with one pass every 12 days (much of Asia, Africa and Yemen) need history back to March for
    a z value. It was read back that far.
