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
