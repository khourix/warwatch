# Short-fuse study: plan (fixed before any candidate was run)

Written 2026-10-17, before `shortfuse.py` was run. Anything changed after the first run is listed at the end as an amendment.

## Question

Is there a per-theatre score that rises 1 to 7 days before a military event, more often than it rises in calm weeks?

## Target

- A **scoring day** d uses only data dated d-1 or earlier (one day of publication delay).
- The target is an **event onset in the same theatre on days d+1 to d+7**.
- Events: `warwatch/data/events.csv` (all 161). "Added" = also in `events_added.csv`; "original" = the rest.
- An event is an **onset** only if no earlier event in the same theatre fell in the 30 days before it (same rule as `leadstudy.py`).
- Event window: the 7 scoring days d = E-7 .. E-1. The event is a **hit** if the signal is "on" on any of them.
- A signal is **on** on day d if it fired on any data day d-7 .. d-1 (the trailing 7 days).

## Calm windows

- Per theatre, consecutive 7-day blocks of scoring days, not overlapping, stepped every 7 days.
- A block is calm only if the theatre has no event at all (onset or continuation) from 30 days before its first day to 30 days after its last day.
- A calm block is a **false alarm** if the signal is on on any of its 7 days. Same definition as the event window, so the rates compare.
- An event window or calm block counts only if the signal has data on at least 4 of the 13 data days it reads (d-7 of the first day to d-1 of the last).

## Theatres and boxes

A theatre's signal is the union over its own box and, fixed in advance: iran also reads iraq and gulf; israel also reads lebanon and syria.
Same aliasing for every family.

## Candidates (15 tests)

Each single family "fires" on a data day by a fixed rule. z = `leadstudy.zseries` (7-day mean against the 150 days ending 31 days earlier).

| Id | Domain | Rule (fires on a day when) | Source |
|---|---|---|---|
| base | ground/satellite | a watched base is out or in (`basestudy` two-pass rule) | backfill/data/basewatch/scenes.csv.gz, 2022-03 on |
| firms_anom | fire | z of unusual-fire count >= 2 | backfill/data/firecls/firms_anom_*, 2018-2025 |
| adsb_tanker | air | z >= 2 | adsb_<box>_tanker, 2024-03 on |
| adsb_fighter | air | z >= 2 | adsb_<box>_fighter |
| adsb_lift | air | z >= 2 | adsb_<box>_lift |
| nga | sea | z >= 2 of NGA navigational warnings | nga_<box> |
| sar | sea | z >= 2 of SAR ship detections | sar_<box> |
| gdelt_accel | attention | z >= 2 of GDELT material-conflict events per 1,000 events (loc_q4/loc_all) | backfill/data/gdeltwide |
| wiki | attention | z >= 2 of Wikipedia views | wiki_<box> |
| tells | diplomatic | any timing tell fires (`tells.py` rules: departure, leave, sea, wave, tankers), replayed day by day | history_lookup |
| fire_site (c) | fire | z >= 2 of unusual fires at energy/industrial sites (`esite` column) | firms_cls_* |
| conv2 (a) | combined | at least 2 of 6 domains on: air (any adsb), sea (nga or sar), ground (base), fire (firms_anom), diplomatic (tells other than tankers and sea), attention (wiki or gdelt_accel) | |
| conv3 (a) | combined | at least 3 of those 6 domains on | |
| sat_air (b) | combined | adsb_tanker or adsb_lift on AND base on, same theatre, same 7 days | |
| index (d) | combined | short-fuse index >= cut (below) | |

fire_site is compared with firms_anom: is the restricted version better? The file has no separate military-site count, so "energy and industrial site" is the restriction that exists.

### The short-fuse index (d), honest holdout

- Weights from the ORIGINAL events only: for each single family with lift > 1 on original events, weight = ln(lift), else 0.
- Index on a day = 100 x sum(weight x on) / sum(all weights). A family with no data counts as off.
- Cut: the lowest index value that keeps the false-alarm rate on calm blocks at 20% or less, picked on the original events' run.
- Tested on the ADDED events only. Its pass needs only the added events (the original events trained it).

## Pass rule

- One-sided Fisher exact test, event windows against calm blocks (`basestudy.fisher_greater`), separately for original and added events.
- Bonferroni over the 15 tests: alpha = 0.05 / 15 = 0.0033.
- **Pass**: p < 0.0033 on original AND on added (index: added only), and false-alarm rate <= 20%.
- **Close**: p < 0.05 on both sets (index: added p < 0.05), lift > 1 on both.
- Reported for every candidate: span, theatres, events scored, hits, hit rate, false-alarm rate, lift, p (original, added, pooled).
- Within-theatre AUC where a continuous score exists: day-level, positive = onset in d+1..d+7, negative = calm days (same 30-day rule); per-theatre AUC averaged with weights = positive days. Continuous score = max z over the trailing 7 days (singles), domain count (conv), index value (index).
- Low power (ADS-B: about two years; base watch: from 2022-03) is reported as a finding, not a failure.

## Profile

For the 3 best candidates by pooled p: mean score on each day -14 .. 0 before onsets, against the mean on calm days.

## Caveats known in advance

Event and calm windows overlap in data they read (13 days for 7 scoring days); families share data (adsb_tanker is both a single and a tell); the event list was not built blind to these feeds.

## Amendments (after the first run)

1. **Index weights (bug fix, seen after run 1).** Run 1's code smoothed the lift ((hits+0.5)/(n+1) over (false alarms+0.5)/(blocks+1)), which the plan does not say. It gave sar a weight of 0.35 with 0 hits. Run 2 uses the raw lift, as written above. Run 1 result, for the record: cut 1.82, original 18/57, added 16/71 (p 0.086), false alarms 15.7%. Run 2: added 16/71, p 0.071. The verdict is the same.
2. **Validity of combined candidates (decided in code before run 1, not written here).** conv2 and conv3 count a day only when at least 2 (or 3) of the 6 domains have data; sat_air only when both ADS-B and base watch have data; the index whenever any weighted family has data, a family without data counting as off. The 4-of-13 data-day rule applies to the single families.
3. **Calm days for the AUC and the profile** are days with no event of the theatre within 37 days either side (30 days plus the 7-day window).
4. The profile table also shows the index and conv2, because they are the shapes proposed for the metric.
