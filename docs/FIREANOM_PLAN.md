# Unusual-fire counts: test plan, fixed before any replayed count is read

Committed 2026-10-15 with `warwatch/firecls.py` and `warwatch/fireref.py`, before `fireref.py replay` ran
([FIRECLASS_PLAN.md](FIRECLASS_PLAN.md), stage F4).

**Why this series.** The raw FIRMS count (`firms_<box>`) mixes gas flares, farm burning and fighting. Counting only the
detections `firecls` calls unusual (`anom` or `hot`) should keep the fighting and drop the rest. If it does, the count
should rise before events more reliably than the raw count.

**Series.** `firms_anom_<box>`: per day, the VIIRS S-NPP standard-processing detections that `firecls.classify` marks
`anom` or `hot`. Low-confidence detections are dropped, as the live map drops them. Each day is classified with
reference data from earlier years only: static cells use the five years before, the seasonal baseline the years
before (wars left out, `config.FIRE_CLIM_YEARS`), and "never burned" means before that year. The FRP and per-day
detection percentiles of industrial cells come from all years. This is a small leak, accepted and noted here. The
replay runs from 2018-01-01 to the archive's last day (2025-12-31).

**Weights.** Frozen at the starting values in `firecls.W` and `firecls.ANOM_AT` as of this commit. They are **not tuned**:
we have no labelled set of conflict and non-conflict fires to tune on, and tuning on events would leak the test. The
plan's 2018–2021 calibration step is therefore dropped. Those years are only the start of the scored history.

**Theatres per box.** ukraine → ukraine; europe_east → europe_east; iran → iran, iraq, gulf; yemen → yemen;
israel → israel, lebanon, syria; korea → korea; libya → libya. Each theatre is scored on its box's series.

**Scoring and test.** As for Wikipedia and Senkaku (`warwatch/sourcestudy.py test`): scored day by day as the live build
scores a daily count (`stats.score_series`), a day's count public the next day. For each event, take the highest z in the
30 days before it, and compare with calm 30-day windows of the same theatre. One family, pooled over the theatres above.

**Pass rule.** All three:
1. On the added events (`events_added.csv`), the hit rate at z ≥ 2 beats the calm false-alarm rate with p < 0.05.
2. On the original events, the same with p < 0.10.
3. AUC above 0.55 on both halves.

A family that passes goes into the feature study as a candidate. A failure is recorded and not tuned. For comparison
only, not as a pass criterion, the same test is reported on the raw `firms_<box>` archive series.

**Case checks** (recorded, not part of the pass rule). The class the replay gives at each place and day, from
`warwatch/data/fire_cases.csv`. Each case needs a published source; cases outside the archive (2026) are checked on the
live map instead.

**Precision audit** (owner, after the result). 50 random `anom` detections from 2022–2025, each opened with the Copernicus
link, labelled conflict, industrial, farm/wild or cannot tell. There is no pass mark; it tells us whether the label
"unusual" can be trusted.

## Amendment (2026-10-15, before the test ran)

The first replay put 11% of the Ukraine box's detections in the class "offshore". NASA's `type` 3 marks every detection
over water, not just platforms. Reed fires in river deltas, and fires along the Dnipro front line, were being hidden as
"offshore platform or flare". The offshore rule now requires a persistent source: at least 60 days a year in at least
2 of the 5 years before, the same persistence as the static rule. The replay was run again.

This change was decided from the class shares alone. No event comparison, z value or hit rate had been computed. The
weights stay as frozen above.

**Second amendment (same day, again before the test ran).** After the first fix, the Ukraine box still had 10% offshore.
The cells were waterside steel works: Zaporizhstal on the Dnipro, NLMK Lipetsk, Alchevsk, and Azovstal and Illich in
Mariupol (and POSCO Pohang in Korea). Their edge pixels touch water. As "offshore" they skipped the "hotter than its
normal" test, so a strike on such a plant would have been hidden. Offshore now also needs water detections (type 3) to
outnumber static-land ones (type 2). The replay was run again. This was decided from class shares and the cells'
locations only.

**Third amendment (same day, before the test ran).** A case check failed. The Shahran fuel depot fire in Tehran (night of
14 June 2025, 43 MW) came out as "seasonal farm fire". The seasonal rule looks at a ~33 km area, and the fields around
Tehran burn every June. Seasonal now also needs the spot itself (~3 km) to have burned in at least 3 earlier years. Shahran's
spot had two tiny detections in 12 years. The ~1 km first-burn grid became a grid of the years each cell burned, to
count this. This was decided from that one case check. No event comparison had been
run. The replay is run again after the OpenStreetMap site list is built, so the test uses the full site list.

**Fourth amendment (same day, before the test ran).** The OpenStreetMap site list could not be built today. The public
Overpass servers were at capacity for more than six hours (single and parallel runner jobs, and four mirrors). The test
therefore runs with the site list as it stands: World Bank GGFR flares and WRI power plants, with no OSM military sites,
airfields, ports, fuel depots or substations. The "near a sensitive site" score term (+25) and the rule that sensitive
sites block "seasonal" therefore never apply. This tests the classifier without that part. When `fireref.yml` next runs
(monthly: sites, then replay), the test is run again with the full list, and both results are reported. Nothing else
changes.

## Result (2026-10-15)

**Fails** ([FIREANOM.md](FIREANOM.md)).
- **Original events**: unusual-fire counts reached z ≥ 2 before 70% of them (p = 0.016, AUC 0.59).
- **Added events**: only 53%, against a calm false-alarm rate of 50% (p = 0.37, AUC 0.50).
- **Why the false-alarm rate is so high**: the daily counts are small, so a handful of fires is a large jump.
- **Raw count of all detections, for comparison**: hit 21% and 24% against a false-alarm rate of 21%.

Recorded as failed and not tuned. `firms_anom_<box>` stays at zero weight. The classes stay on the map as a reading aid.

Case checks (`python3 warwatch/fireref.py cases`):
- Baba Gurgur and Rumaila are routine industry, as expected.
- Abqaiq (14 Sep 2019): the S-NPP passes that day saw only the field's normal 1–3 MW flares. The attack fires were not
  seen, which is a data limit.
- Hodeidah (20 Jul 2024): no S-NPP detection within 5 km for four days.
- Shahran (14 Jun 2025): "unexplained" (score 30), not "unusual". Without OpenStreetMap depots the site is not known to be
  sensitive. The Sentinel-2 check finds the smoke plume and the fire in images from 12 and 15 June ([docs/firereview](firereview/)).
