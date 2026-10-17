# Base watch against past events: test plan, fixed before the backfill is read

Committed 2026-10-15 with `warwatch/basewatch.py`, before any backfilled base scene was read
([BASEWATCH_PLAN.md](BASEWATCH_PLAN.md), stage B4). It applies only if the feasibility test says GO
([BASESPIKE.md](BASESPIKE.md)). On NO-GO the base layer stays a picture viewer, and this test is not run.

**Series.** `bases_out_<theatre>` and `bases_in_<theatre>`: per day, the number of watched sites (`warwatch/data/bases.json`)
listing that theatre whose last two scored radar passes within 7 days are both beyond z −2.5 ("out") or +2.5 ("in").
The radar metric, threshold, orbit grouping and z rule are those frozen by the feasibility test in `basewatch.py`. The
backfill starts on 2022-01-01. In 2022–2025 only Sentinel-1A flew, so a site has a scored pass every 3 to 12 days
depending on its orbits. This is accepted and noted in the result.

**Events.** Those in `events.csv` and `events_added.csv` dated from 2022-03-01 (allowing 8 same-orbit scenes of history),
in theatres listed by at least one site: iran, iraq, gulf, israel, lebanon, syria, yemen, ukraine.

**Test.** For each event, a hit is `bases_out` or `bases_in` at 1 or more on any day in the 14 days before it. Calm windows
are 14-day windows of the same theatres with no event within 30 days, stepped every 14 days. Compare the hit rate on
events with the firing rate in calm windows (one-sided Fisher exact test).

**Pass rule.** Both:
1. The hit rate beats the calm firing rate with p < 0.05.
2. The tell fires in no more than 15% of calm windows.

Also reported, with no pass mark: each feasibility case, and each site's firing count (a site that fires often in calm
times is the first to look at). A failure is recorded and not tuned: no change to sites, metric, threshold or windows.
The tell keeps its place on the page either way, because tells never set a level, but its record will show the result.

## Amendment (2026-10-17): run it after the NO-GO, at the owner's request. Fixed before any backfilled scene is read.

The feasibility test missed GO by 0.3 points (10.3% false alarms on single scenes against 10%). It also scored single
scenes, while the monitor's rule needs two passes to agree. On 17 Oct 2026 the owner asked for base movements (aircraft
and equipment) to count as a sign of coming military action, so this test is now run as written above, with these
details fixed before reading:

- **Scenes.** Sentinel-1 RTC (Planetary Computer) from 2021-09-01 to 2026-02-28 for every site in
  `warwatch/data/bases.json` (120 sites today, not the 30 of the first draft), read by `basewatch.py --backfill-from
  2021-09-01 --until 2026-02-28 --no-optical`, plus the live scenes in `warwatch/history/basewatch_scenes.csv` from
  2026-03-01. The backfill is kept in `backfill/data/basewatch/scenes.csv.gz`. Sites with no radar coverage drop out.
- **Frozen from the feasibility test:** `blobs` at VV ≥ −3 dB, z against the same orbit and part (8 to 20 earlier scenes
  within 240 days), two scored passes within 7 days both beyond ±2.5, and the state needs a pass in the last 10 days.
- **Events.** Every distinct (date, theatre) row of `warwatch/data/events.csv` (which holds the added events too) dated
  2022-03-01 or later, up to the last scene date, in a theatre listed by at least one site. An event whose 14 days
  before hold no scored pass at any of its theatre's sites is counted as "no data" and left out (reported).
- **Calm windows.** Per theatre, 14-day windows starting 2022-03-01 and stepped every 14 days, with no event of that
  theatre from 30 days before the window starts to 30 days after it ends. Same "no data" rule.
- **Test and pass rule:** unchanged (one-sided Fisher exact test; p < 0.05 and calm firing ≤ 15%). Original and added
  events are also reported apart, with no pass mark.
- **On a pass:** `basewatch.ALERTS` becomes `True` (the `bases_out_<t>` and `bases_in_<t>` series appear), the "bases"
  tell gets the rule "a base out or in on any of the last 7 days", and `bases_` leaves `catalog.ZERO_WEIGHT`, so the
  composite counts it. **On a failure:** recorded, not tuned. The map keeps showing two-pass movement with a note that it
  carries no weight.

`warwatch/basestudy.py` runs it and writes `docs/BASEWATCH_STUDY.md`.
