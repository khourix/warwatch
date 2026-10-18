# Activity (experimental)

Activity says whether the fast signals in a theatre are busy this week. The page shows it as a small chip beside the level, ACTIVE or QUIET, marked EXP. It never sets or changes the level.

Code: `warwatch/activity.py`. Study: [shortfuse/RESULTS.md](shortfuse/RESULTS.md). Forward record: `forward/log_activity.csv`.

## What it reads

A family is on when it fired on any of the 7 days before today.

| Family | On when | Data | Weight |
|---|---|---|---:|
| Fighter aircraft | 7-day mean of fighter counts is 2 SD or more above its normal | `backfill/data/adsb_{box}_fighter.csv`, added daily by `adsb-daily.yml` | 2.51 |
| Wikipedia attention | the same rule on daily page views | `backfill/data/wiki_{box}.csv`, added daily by `activity-daily.yml` | 0.82 |
| Severe-event share in the news record | the same rule on severe GDELT events per 1000 located events (days with 50 or more) | `backfill/data/gdeltwide/{year}.csv`, added daily by `activity-daily.yml` | 0.63 |
| Timing tells | a departure, advisory, sea-warning, strike-wave or tanker tell fired | the run's own tells (`tells.py`) | 0.38 |
| Tanker aircraft | the fighter rule on tanker counts | `backfill/data/adsb_{box}_tanker.csv` | 0.35 |
| Bases by satellite radar | a watched base was out or in on two passes | the run's `bases_out_*` and `bases_in_*` series | 0.05 |

The normal is `leadstudy.zseries`: the 150 days that end 31 days before the day. Iran also reads the Iraq and Gulf boxes. Israel also reads Lebanon and Syria.

Index = 100 x (sum of the weights of the families on) / (sum of all weights). Activity is ACTIVE from 1.04, which is the base family alone. So in practice it is ACTIVE when any family is on, and the index only ranks theatres.

A family with no data in the window, or whose newest data is more than 4 days old, reads as missing. It counts as off and is named in the chip's explanation.

## What it is worth

The weights and the cut were set on the original event list only. On the added events, which they never saw, Activity was on before 16 of 71 onsets (23%), against 15% of calm weeks. One-sided Fisher p = 0.071. That is a 1.5x lift and it is not proven.

The index is about twice its calm level for the 14 days before an event and does not climb over the last week. So it marks a hot theatre, not an attack date.

## Forward record

Each live run appends one row per theatre per UTC day to `forward/log_activity.csv`, hash-chained like `forward/log.csv`. The rows are written before any outcome can be known, so the index can later be judged on days it has never seen. `verify-warwatch` checks the chain. Demo renders do not write it.

## Where it differs from the study

- **Timing tells.** The study replayed each tell day by day. Live, it reads the run's tells, which count a firing in the 7 days up to and including today.
- **Bases.** The study rebuilt base states from the archive scenes (`basestudy.py`). Live, it reads the same states from the run's `bases_*` series.
- **Wikipedia and GDELT.** Until `activity-daily.yml`, these were only collected when `backfill.yml` was run by hand. Without that job, both families read as missing within a few days.

## Theatres

Activity covers the 13 study theatres (`leadstudy.THEATRES`). The Iraq, GCC, Lebanon and Syria pages show no chip, because their boxes are read under Iran and Israel.
