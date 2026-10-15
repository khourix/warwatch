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
