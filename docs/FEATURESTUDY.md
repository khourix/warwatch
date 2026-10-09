# Feature and methodology study

Written by `warwatch/featurestudy.py` to the plan fixed in advance in [FEATURESTUDY_PLAN.md](FEATURESTUDY_PLAN.md). Everything is out of sample: each test year 2021 to 2026 is scored by a model fitted on earlier years only (30-day embargo), with the shrink toward the base rate fitted on earlier test years only. Nothing here changes the live page, `model_weights.json` or `events.csv`.

Event lists: current 78 events (`events.csv`); extended 161 (`events.csv` plus the 83 in `events_added.csv`).

## Results on the extended list

| Candidate | Brier skill | AUC | Within-theatre AUC | Events flagged | of which added events | False episodes per hit | Brier gain vs baseline (x1e-4) | Bootstrap p | Years better | Gates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Baseline (published model) | +0.0084 | 0.625 | 0.541 | 31/98 | 15/52 | 2.4 | n/a | n/a |  | FAIL |
| Reference: history only, no indicators | -0.0021 | 0.606 | 0.453 | 22/98 | 10/52 | 1.2 | -10.74 | 0.820 | 3 | FAIL |
| Decayed conflict history | +0.0075 | 0.634 | 0.548 | 31/98 | 14/52 | 1.7 | -0.96 | 0.553 | 3 | FAIL |
| Global tempo | +0.0097 | 0.628 | 0.548 | 29/98 | 13/52 | 2.1 | +1.31 | 0.380 | 3 | FAIL |
| Slow build-up (GDELT) | +0.0095 | 0.626 | 0.540 | 30/98 | 15/52 | 2.0 | +1.05 | 0.230 | 4 | FAIL |
| Cross-theatre attention | +0.0079 | 0.625 | 0.539 | 31/98 | 15/52 | 2.3 | -0.56 | 0.990 | 3 | FAIL |
| Smoothed evidence | +0.0090 | 0.641 | 0.561 | 33/98 | 16/52 | 1.2 | +0.54 | 0.471 | 3 | FAIL |
| Implied volatility | +0.0121 | 0.631 | 0.551 | 33/98 | 16/52 | 2.5 | +3.75 | 0.213 | 4 | FAIL |
| Advisory steps | +0.0081 | 0.625 | 0.540 | 31/98 | 15/52 | 2.3 | -0.35 | 0.825 | 2 | FAIL |
| Air co-occurrence | +0.0084 | 0.625 | 0.541 | 31/98 | 15/52 | 2.4 | -0.02 | 0.807 | 5 | FAIL |
| Monotone boosted trees | -0.0097 | 0.607 | 0.490 | 22/98 | 11/52 | 1.6 | -18.46 | 0.889 | 3 | FAIL |

## Results on the current list

| Candidate | Brier skill | AUC | Within-theatre AUC | Events flagged | of which added events | False episodes per hit | Brier gain vs baseline (x1e-4) | Bootstrap p | Years better | Gates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Baseline (published model) | +0.0148 | 0.628 | 0.588 | 14/51 | 0/0 | 4.6 | n/a | n/a |  | pass |
| Reference: history only, no indicators | +0.0021 | 0.573 | 0.530 | 10/51 | 0/0 | 1.2 | -7.29 | 0.815 | 3 | FAIL |
| Decayed conflict history | +0.0216 | 0.638 | 0.628 | 18/51 | 0/0 | 5.9 | +3.89 | 0.318 | 4 | pass |
| Global tempo | +0.0135 | 0.618 | 0.574 | 15/51 | 0/0 | 4.8 | -0.75 | 0.585 | 3 | FAIL |
| Slow build-up (GDELT) | +0.0129 | 0.631 | 0.587 | 17/51 | 0/0 | 3.4 | -1.09 | 0.567 | 3 | pass |
| Cross-theatre attention | +0.0148 | 0.627 | 0.587 | 14/51 | 0/0 | 4.6 | -0.00 | 0.484 | 2 | pass |
| Smoothed evidence | +0.0131 | 0.628 | 0.588 | 13/51 | 0/0 | 2.5 | -0.94 | 0.630 | 3 | pass |
| Implied volatility | +0.0149 | 0.628 | 0.588 | 14/51 | 0/0 | 4.7 | +0.07 | 0.351 | 4 | pass |
| Advisory steps | +0.0144 | 0.627 | 0.588 | 15/51 | 0/0 | 5.2 | -0.24 | 0.636 | 1 | pass |
| Air co-occurrence | +0.0148 | 0.628 | 0.588 | 14/51 | 0/0 | 4.5 | -0.01 | 0.844 | 0 | pass |
| Monotone boosted trees | -0.0056 | 0.596 | 0.542 | 9/51 | 0/0 | 5.8 | -11.73 | 0.869 | 2 | FAIL |

## Verdicts (pass rule from the plan, on the extended list)

| Candidate | Holm-corrected p | Verdict | Detail |
|---|---:|---|---|
| Decayed conflict history | 1.000 | fails | Brier not better (p = 0.55); better in 3 of 6 years; fails a model gate |
| Global tempo | 1.000 | fails | Brier not better (p = 0.38); fewer events flagged or more false alarms per hit; better in 3 of 6 years; fails a model gate; worse on the current 78 events |
| Slow build-up (GDELT) | 1.000 | fails | Brier not better (p = 0.23); AUC lower; fewer events flagged or more false alarms per hit; fails a model gate; worse on the current 78 events |
| Cross-theatre attention | 1.000 | fails | Brier not better (p = 0.99); AUC lower; better in 3 of 6 years; fails a model gate; worse on the current 78 events |
| Smoothed evidence | 1.000 | fails | Brier not better (p = 0.47); better in 3 of 6 years; fails a model gate; worse on the current 78 events |
| Implied volatility | 1.000 | fails | Brier not better (p = 0.21); fewer events flagged or more false alarms per hit; fails a model gate |
| Advisory steps | 1.000 | fails | Brier not better (p = 0.82); AUC lower; better in 2 of 6 years; fails a model gate; worse on the current 78 events |
| Air co-occurrence | 1.000 | fails | Brier not better (p = 0.81); fails a model gate; worse on the current 78 events |
| Monotone boosted trees | 1.000 | fails | Brier not better (p = 0.89); AUC lower; fewer events flagged or more false alarms per hit; better in 3 of 6 years; fails a model gate; worse on the current 78 events |

Combination run (C1): not run, no candidate met rules 1 to 6.

## Gates of the published model on each list

| List | Brier skill | AUC interval | Shuffled-timing p | Gates |
|---|---:|---|---:|---|
| current | +0.0148 | 0.550 to 0.706 | 0.027 | pass |
| extended | +0.0084 | 0.558 to 0.690 | 0.217 | FAIL |

## How the probability moved before events (extended list)

Mean published probability as a multiple of the theatre's median out-of-sample probability, by day before each scorable event. A warning would show the line climbing toward day -1.

| Day | Baseline (published model) | Decayed conflict history | Global tempo | Slow build-up (GDELT) | Cross-theatre attention | Smoothed evidence | Implied volatility | Advisory steps | Air co-occurrence | Monotone boosted trees |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| -60 | 1.38 | 1.29 | 1.35 | 1.37 | 1.38 | 1.40 | 1.46 | 1.38 | 1.38 | 1.08 |
| -45 | 1.33 | 1.27 | 1.28 | 1.31 | 1.32 | 1.38 | 1.36 | 1.32 | 1.33 | 1.12 |
| -30 | 1.41 | 1.33 | 1.39 | 1.39 | 1.41 | 1.42 | 1.48 | 1.41 | 1.41 | 1.14 |
| -21 | 1.44 | 1.33 | 1.42 | 1.41 | 1.44 | 1.45 | 1.53 | 1.43 | 1.44 | 1.11 |
| -14 | 1.36 | 1.27 | 1.36 | 1.34 | 1.36 | 1.42 | 1.44 | 1.36 | 1.36 | 1.10 |
| -7 | 1.34 | 1.26 | 1.32 | 1.31 | 1.34 | 1.37 | 1.42 | 1.34 | 1.34 | 1.10 |
| -3 | 1.33 | 1.25 | 1.30 | 1.30 | 1.32 | 1.36 | 1.40 | 1.32 | 1.33 | 1.09 |
| -1 | 1.33 | 1.26 | 1.30 | 1.30 | 1.32 | 1.36 | 1.40 | 1.32 | 1.33 | 1.09 |

## Event by event (extended list)

Percentile of the day-before probability among the same theatre's out-of-sample calm days (50 = an ordinary day). Full table: `backtest/featurestudy_events.csv`.

| Events | Scored | Median percentile, baseline | Flagged by the baseline |
|---|---:|---:|---:|
| in the current list | 55 | 61 | 16 |
| added | 54 | 46 | 14 |
| buildup | 74 | 57 | 19 |
| surprise | 35 | 54 | 11 |
| all | 109 | 56 | 30 |

