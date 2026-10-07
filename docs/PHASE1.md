# Phase 1 of the methodology review: before and after

Six small changes to the scoring, each backed by the review's backtest (78 labelled wars, strikes and drills in 13 theatres, 2018 to 2026; 59 of them with enough history to score). The harness is the review's own (`review/analysis` on branch `claude/project-thread-k7j869`): every series scored point-in-time each day with the publication delay its source really has, then compared with whether an event followed in the next 30 days. Event windows plus the 30 days after each event are left out. 34,752 theatre-days, 1,729 of them in the 30 days before an event (5.0%).

## Result

| Measure | Before (v7) | After (Phase 1) |
|---|---|---|
| AUC, event within 30 days (0.5 = coin flip) | 0.526 | 0.656 |
| Events flagged at 10% false-alarm rate | 19 of 59 | 28 of 59 |
| Events flagged at 5% false-alarm rate | 10 of 59 | 14 of 59 |
| Median lead time when flagged (10% rate) | 30 days | 27 days |
| Chance of an event within 30 days on the top 10% of days (2021 on; base rate 6.0%) | 5.1% (0.86x base) | 12.1% (2.04x base) |
| Average percentile of the score 4 days before an event | 56th | 66th |
| Average percentile of the score 4 days after an event | 63rd | 72nd |

The score still ranks days after an event above days before it (66th against 72nd), because the fast feeds (aircraft, ships, fires, GNSS jamming, news) have no history to replay and only the slow indicators move ahead of events. Phase 3 back-fills them.

## What each change adds

AUC when changes are stacked, same data and labels:

| Step | AUC | Events flagged at 10% |
|---|---|---|
| v7 as built (90-day baseline, orness 0.3, signed z) | 0.526 | 19 of 59 |
| + one-sided evidence | 0.587 | 21 of 59 |
| + orness 0.7 | 0.614 | 26 of 59 |
| + 1-year baseline that leaves out the latest 30 days, equities replayed, noise families at zero weight | 0.656 | 28 of 59 |

The last row bundles three changes because the harness scores each series once. The remaining two (no refit of the thresholds, and the backtest fix itself) do not change the ranking of days: the refit shifts thresholds, not the composite.

The review estimated AUC 0.61 for the 1-year baseline and 0.63 with orness 0.7; the result is above both.

## Alert rates went up: read before merging

Ranking improved, but how often levels fire did too, and the thresholds were not re-tuned (the calm-world simulation is unchanged apart from being one-sided).

Share of calm days at or above Watch in the repo's own replay of the slow series (`docs/BACKTEST.md`; target 10%):

| Theatre | Before | After |
|---|---|---|
| Ukraine | 6.9% | 15.9% |
| Eastern flank | 37.3% | 35.9% |
| Yemen | 0.5% | 16.8% |
| Israel | 6.4% | 17.7% |
| Iran | 4.7% | 51.7% |
| Taiwan Strait | 8.1% | 43.4% |

The year baseline lags a market that trends for months (Brent in 2022 stays "high" against the previous year), so trending theatres sit above Watch for long stretches. The 90-day baseline adapted within weeks and rarely fired.

Offline replay of the live state from the committed caches (7 October 2026, keyed feeds absent): before, Iran Critical, Ukraine and South Asia Watch; after, Critical in Ukraine, Iran, Yemen, South Asia and Sudan, Elevated in Libya, Watch in Korea. The would-be empirical shift and stretch on that state are 0.12 and 1.14 (they were 0.40 and 1.38 under v7), so removing the refit changes little there; the extra Critical readings come from the scoring (GPS jamming at the +5 cap in five theatres, Brent, Bosphorus transits).

Phase 2's validation job should set Watch, Elevated and Critical from calm-day percentiles of the new score, and the probability model replaces the levels as the headline. Until then, treat the levels as a ranking, not a rate.

## Caveats

- Same events that motivated the changes, so the AUC gain is in-sample. The review's leave-one-theatre-out and rolling-origin tests are the out-of-sample check, and the ranking of methods held there. A forward record is Phase 2.
- 59 events, 13 theatres. Skill is concentrated in Iran, Israel and Yemen and in Ukraine; elsewhere it is weak.
- Levels are not probabilities. Phase 2 adds a calibrated 30-day probability.

## Reproducing

1. Before: check out `main` at commit `2f3fce5`, run the review's `zhist.py`, `zhist2.py`, then `run_eval.py events_full.csv zhist.pkl`.
2. After: check out this branch, run `zhist.py` with the point window raised from 250 to 450 points (the year baseline needs about 400 days of daily values) and series with `scored=False` skipped, then `run_eval.py`. Row 3 of its output is the new engine.
3. `python3 warwatch/backtest.py run` regenerates `docs/BACKTEST.md` and `backtest/results.json` with the new engine, equities included.
