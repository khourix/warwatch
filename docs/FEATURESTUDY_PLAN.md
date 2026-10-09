# Feature and methodology study: test plan (fixed before any result)

Written 2026-10-09, before any candidate below was run. The study code is `warwatch/featurestudy.py`; the results go to `docs/FEATURESTUDY.md`. Nothing here changes the live page, `model_weights.json` or `events.csv`.

## Question

Can the data WarWatch already holds be turned into features, or the method changed, so that the published 30-day probability rises more reliably before past war and military events than it does today, out of sample?

## Baseline

The published model exactly as in `docs/MODEL.md`: 75 indicator families (evidence = max(0, z)/5), theatre intercepts, the three conflict-history terms, ridge strength chosen from the same grid by out-of-sample Brier, and the nested shrink toward the base rate. Rolling origin, test years 2021 to 2026, each fitted on earlier years only with the 30-day embargo. On the current 78 events it reproduces: Brier skill +0.0148, AUC 0.628, 14 of 51 events flagged at a 10% false-alarm rate.

## Events

1. **Current list**: `warwatch/data/events.csv`, 78 events.
2. **Extended list**: the current list plus past events from 2018-01 to 2026-09 that meet the codebook (`docs/EVENTS.md`), in `warwatch/data/events_added.csv`. They are chosen from the public record by the codebook alone, without looking at any indicator, and each has a date checked against a named source. The file is fixed before the candidates are scored on it.

The extended list is the primary yardstick; the current list is the robustness check. The baseline is re-run on both. Events in the extended list that the current list lacks also get their own column, since no part of the current model was built with them.

## Candidates

Each is the baseline plus one change. Hyperparameters are fixed here, not tuned.

| Id | Change | Detail |
|---|---|---|
| H1 | Decayed conflict history | Replace the three history terms with log(1 + sum of exp(-ln2 x age / h)) over the theatre's past events for half-lives h = 30, 180 and 730 days, plus the existing log days since the latest event. |
| H2 | Global tempo | Add one term: the same decayed count over events in every theatre, half-life 365 days (the documented under-calibration comes from event frequency rising everywhere). |
| F1 | Slow build-up | For the GDELT threat, posture and pre-force counts and shares, add a slow z: 30-day mean against the median and MAD of 30-day means over the two years ending 31 days earlier. New families `slow_*`. |
| F2 | Cross-theatre attention | The theatre's share of all 13 theatres' threat plus posture events (7-day sums), z against its own year ending 31 days earlier. New family `xshare_preforce`. |
| F3 | Smoothed evidence | Replace each family's daily evidence with its exponentially weighted mean, half-life 5 days (past days only). |
| F4 | Implied volatility | Oil (OVX) and gold (GVZ) implied volatility and the VIX/VIX3M term ratio from `backfill/data/vol_*`, scored like any daily series, as global families. |
| F5 | Advisory steps | From the US travel advisories (`backfill/data/state_*`, 7-day publication lag): the rise in the theatre's summed advisory level over the last 30 days (evidence = min(5, 2.5 x rise)), and new ordered departures over the last 30 days (evidence = min(5, 5 x new countries)). |
| F6 | Air co-occurrence | `featurelab.py` F2: min(z tanker, max(z ISR, z fighter)), 2024-09 on, missing before. |
| M1 | Monotone boosted trees | Gradient-boosted trees on the baseline's inputs, evidence constrained to raise risk only, depth 3, 150 rounds, learning rate 0.05, at least 300 days per leaf, L2 1.0; then the same nested shrink. |
| C1 | Combination | The baseline plus every candidate that meets rules 1 (uncorrected) to 5 below, run once. If none does, C1 is not run. |

## Metrics

- Brier skill against each theatre's base rate (the model's own gate metric).
- Pooled AUC, and within-theatre AUC (each theatre's AUC, weighted by its positive days), which asks only whether the probability rises at the right time, not which theatres are risky.
- Events flagged: events with the probability above the line that puts 10% of calm days in alert, on any of the 30 days before.
- False episodes per hit at that line (runs of alert days, gaps up to 7 days bridged, as in `improve.py`).
- Event by event: the within-theatre percentile of the day-before probability.

## Pass rule

A candidate beats the baseline only if all of these hold on the extended list:

1. Brier is lower than the baseline's, with a one-sided paired bootstrap p below 0.05 (2,000 resamples of the 78 theatre-years), Holm-corrected across the nine candidates H1 to M1. Uncorrected p below 0.05 without the correction is reported as "promising, not proven".
2. Pooled AUC and within-theatre AUC are not lower than the baseline's.
3. At least as many events flagged, and no more false episodes per hit.
4. Brier is better in at least 4 of the 6 test years.
5. It still passes the three model gates (positive Brier skill, AUC interval above 0.5, beats the shuffled-timing control).
6. On the current 78-event list its Brier skill is not lower than the baseline's.

A candidate that fails is reported as failed and not tuned. With nine candidates and p below 0.05, about 0.45 would clear rule 1 uncorrected by chance; the Holm correction is what separates a finding from that.

## Known limits, stated in advance

- Several of these ideas were looked at in earlier reports (`IMPROVEMENTS.md`, `LEADSTUDY.md`, `FEATURELAB.md`), so the author knew which families had looked weak. None of the candidates above was run before this plan was written.
- The ridge strength is chosen on the test years for every candidate, as for the baseline, so all of them are a little optimistic in the same way.
- About 50 to 100 scorable events: a difference of one or two events flagged is noise.
