# Timing study: test plan (fixed before any result)

Written 2026-10-11, before any candidate below was run. The study code is `warwatch/timingstudy.py`; the results go to `docs/TIMINGSTUDY.md`. Nothing here changes the live page, `model_weights.json` or `events.csv`.

## Question

Can the data WarWatch now holds be transformed, added or used differently in training so that the 30-day model passes its three release gates on past events, with the gates unchanged?

## Why it fails today

On the 161 events the published model scores AUC 0.632 against a shuffled-timing control whose 95th percentile is 0.652 (p = 0.18). The control shifts each theatre's probabilities in time and keeps their level, so the part of the AUC that comes from knowing which theatres are risky (about 0.61) is in the control too. What the gate asks for is timing within each theatre, where the model scores 0.534.

A check run before this plan, with a synthetic timing signal added to the published probability (no candidate involved): the shuffle gate starts to pass when the pooled AUC reaches about 0.65 to 0.68, which takes a within-theatre AUC of about 0.58 to 0.63. So a candidate has to roughly double today's timing skill (0.534 against 0.5) to pass.

## Baseline

The published model as in `docs/MODEL.md` on the 161 events: 75 families, theatre intercepts, the three conflict-history terms, ridge strength chosen from the same grid by out-of-sample Brier, the nested shrink. Rolling origin, test years 2021 to 2026, each fitted on earlier years only with the 30-day embargo. It reproduces Brier skill +0.0054, AUC 0.632, within-theatre AUC 0.534, shuffle p 0.18.

## Candidates

Each is the baseline plus one change. Settings are fixed here, not tuned. Every candidate is judged on the same thing as the baseline: the 13 theatres' 30-day labels on the 161 events, test years 2021 to 2026.

### Data the earlier studies did not have in the fit

| Id | Change | Detail |
|---|---|---|
| D1 | Archive feeds | Aircraft by class, US advisories (scored as steps since PR #20), fires, navigation warnings, vessel presence and the strike-package index from `backfill/data`, as families, with the count and share scale floors from phase A. This is `WARWATCH_BACKFILL_FIT=1`. They were last tried on 2026-10-08, before those floors existed. |
| D2 | Newly held series | Wikipedia page views (`wiki_*`, `wikiloc_*`), the wider GDELT families (`gw_*`, eight of them), ConflictForecast's 3-month armed-conflict and any-violence probabilities and VIEWS, each scored point in time as the live build scores a series of its kind, one family each. Missing before a source starts. |
| D3 | Sub-theatre rows in training | Iraq's and the GCC's rows (their own events from `site_theatre`) join the training set with their own offsets, sharing every weight, so the weights see more positive days. They are not scored: the gates stay on the 13 theatres. |

### Transformations of the inputs

| Id | Change | Detail |
|---|---|---|
| T1 | Hot-state level | For GDELT assault and fight events (CAMEO 18 and 19), count and share: log of the 30-day mean against the median and MAD of every earlier 30-day mean from 2018 (at least 365 days), as a z. The yearly z forgets a war after a year; this does not. One day's lag. |
| T2 | Acceleration | For GDELT threat (13), posture (15), threat and posture, and assault and fight (18 and 19), count and share: the 7-day mean against the median and MAD of the 60 daily values before it. This works on the scale the shuffle control tests (it shifts by at least 60 days). One day's lag. |
| T3 | Fewer weights | The theatre's own families only, plus one "world tempo" term: the mean evidence of the global families. 32 global weights become one. |

### Transformations of the training target (the test label is unchanged)

| Id | Change | Detail |
|---|---|---|
| L1 | Sharper target for the weights | Stage 1 fits the family weights on "an event within 1 to 10 days" (training years only). Stage 2 fits the theatre intercepts, history terms and one coefficient on the stage-1 family index on the 30-day label. Then the usual shrink. |
| L2 | Dense proxy target for the weights | Stage 1 fits the family weights on a proxy with many more positive days: the theatre's 7-day count of GDELT assault and fight events, at any point in the next 30 days, above the 90th percentile of that count over the year before the day. GDELT families are left out of stage 1 so the proxy cannot predict itself. Stage 2 as in L1. |

### Cleaning the inputs (added 2026-10-11 07:30, at the owner's request, before any candidate had been run)

| Id | Change | Detail |
|---|---|---|
| K1 | One-day glitches removed | A family's evidence on a day is the smaller of that day's and the day before's, so a reading that is back to normal the next day never counts. Past days only. |
| K2 | Standing drift removed | Each family's evidence minus its own median over the 365 days before (floored at 0), so a series that sits above its baseline for a year because it trends (EU tenders, procurement) stops adding risk every day. Past days only. |
| K3 | Late data dropped | Families published too late to warn (the `confirming` ones in MODEL.md, mostly monthly procurement and trade) are taken out of the fit. |
| K4 | Duplicates merged | Families whose daily evidence correlates above 0.8 over all theatre-days are averaged into one (greedy, strongest pair first), as the composite already does for series. This looks only at the inputs, never at the events. |

### Combination

C1: the baseline plus every candidate above that passes the three gates at the uncorrected 0.05 line, run once. If none does, C1 is not run.

## Pass rule

The three gates as in `validate.py`, unchanged: Brier skill against each theatre's base rate above 0, the low end of the theatre-year bootstrap AUC interval above 0.5, and the shuffled-timing p below 0.05.

Because thirteen candidates are tried (twelve plus the combination), a candidate counts as **validated** only if its shuffled-timing p is below 0.05 / 13 = 0.0038. The shuffle uses 2,000 circular shifts per candidate instead of 300 so a p that small can be measured; this makes the gate stricter, not looser. A candidate that passes at 0.05 but not at 0.0038 is reported as **promising, not proven**, and gets no place on the page: the forward record decides.

A validated candidate is also checked, as information, on the 78 original events and on the 83 added ones, and year by year.

## Not done, and why

- **Loosening any gate**, including changing the shuffle (its minimum shift of 60 days, its per-theatre shifting) or the 30-day exclusion after events.
- **Changing what counts as an event** (armed force only, a different horizon on the page). That changes what the number means. Those targets exist already as hidden shadow models.
- **Resampling or synthetic events** (oversampling positives, SMOTE). They add no information about timing and the shuffle control is blind to them.
- **Leave-one-year-out testing**, which would score 2019 and 2020 too but train on later years. It lets the model learn the future trend; the rolling origin stays.

## Known limits, stated in advance

- The ridge strength is chosen on the test years for every candidate, as for the baseline, so all of them are a little optimistic in the same way.
- Earlier studies (FEATURESTUDY, IMPROVEMENTS, CALIBRATION, GDELTWIDE, WIKISTUDY, OUTSIDE) looked at some of these sources one at a time, so the author knew which looked weak. None of the candidates above was run in the fit before this plan.
- About 98 scorable events. The check above says the gap to close is large; a pass by one candidate at 0.0038 would be the first.
