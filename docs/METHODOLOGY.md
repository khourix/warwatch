# Warwatch v7 aggregation method

How a pile of indicators becomes one level per theatre. Code: `warwatch/engine.py` (aggregation), `warwatch/stats.py` (per-signal scoring), weights in `warwatch/weights.json`. Every step is deterministic, runs on the Python standard library, and the numbers behind each theatre are written to `audit.json` on every build.

The old method counted how many of five groups were over a threshold (0/5 to 5/5). That threw away how far over, treated two signals from one event as two events, let one strong group stand in for the rest, and moved in whole steps. The new method keeps the same five domains but replaces the counting.

## The seven stages

| # | Stage | What it does | Where |
|---|---|---|---|
| 1 | Baseline | Each signal is compared with its own past: for daily signals the latest 7-day mean against the rolling 7-day means of the year before the newest 30 days (the latest month is left out so a slow build-up is not absorbed into its own yardstick; needs 120 such means, otherwise the last 90 days), the last 36 months with calendar-month seasonality removed for monthly ones. Gaps of up to 2 days are carried forward (LOCF); longer gaps stay missing and lower confidence. | `stats.score_series` |
| 2 | Modified z | `z = 0.6745 * (x - median) / MAD`, winsorized at +-5. The unclamped value is kept as `z_raw` in the audit log. A zero MAD (flat history) falls back to the mean absolute deviation. | `stats.modified_z` |
| 2c | Noise floor | Small counts and small shares cannot claim a spread below their counting noise: a daily count's spread is at least the Poisson spread of a 7-day mean, `sqrt(max(median, 1) / 7)`; a count over a trailing window (warnings in the last 30 days) at least `sqrt(max(median, 1))`; a share at least one percentage point. Without it one aircraft a week over an empty year, or 0.12% jammed against 0.04%, scored the maximum. The family table is `catalog.SCALE`. | `stats.noise_floor` |
| 2a | One-sided evidence | Only evidence in the warning direction counts: each signal's z is floored at 0 (`max(0, z)`), so a calm reading in one source never cancels an alarm in another. Signals flagged `scored=False` in the catalogue (zero-weight families, below) are skipped. | `engine.theatre_items` |
| 2b | Early-warning focus | Confirming (late-published) signals have their z multiplied by `LAG_K = 0.25` before grouping, in the live scores and in the calm-world simulation, so they can corroborate but not drive a level. Set `LAG_K = 0` to exclude them. | `engine.LAG_K` |
| 3 | Redundancy | Within one theatre and domain, signals whose last 30 daily changes (24 monthly) correlate above 0.8 are merged into one group scored at their mean, so one event seen by three sources is counted once. | `engine.groups_of` |
| 4 | Domain score | The strongest 6 groups are combined with an ordered weighted average (exponential weights, orness 0.7). Orness 0.7 leans towards the strongest evidence: with one-sided scoring, one or two strong groups move a domain, and the weaker ones add little. At 0.3 the weakest of six groups carried six times the weight of the strongest, so quiet series buried real signals. A domain with a single group is shrunk to 70%. | `engine.domain_score` |
| 5 | Theatre composite | Domain scores are put on a 100 +- 10 scale (`100 + 10 z`) and combined with the theatre's versioned domain weights by a weighted Mazziotta-Pareto index, `MPI = M + S * S / M` (M weighted mean, S weighted standard deviation). The penalty is added because higher means worse: a lopsided profile reads higher than an even one with the same mean. | `engine.mpi` |
| 6 | Level and scores | Level from calibrated thresholds (below). Threat score 0 to 100 is a logistic of the composite z, 50 at the Watch line and 90 at the Critical line. Also reported: imbalance (S), worst offender (largest single-signal z), confidence, and each domain's contribution `w * z`. | `engine.theatre_composite` |
| 7 | Hierarchy | Region level = worst child level (a crisis is not averaged away); region score = highest child score. Global Threat Index = MPI+ of the region scores (0 to 100), level = worst region level. | `engine.rollup` |

### Levels and thresholds

Watch, Elevated and Critical are the 90th, 95th and 99th percentiles of the composite in a calm world. The calm world is simulated, not observed: 2,000 draws per theatre, each signal group a standard normal in which 10% of draws are twice as wide (fatter tails than a normal), winsorized at +-5, run through the same stages 3 to 5 with the theatre's own series counts and weights. The generator is seeded, so a theatre always gets the same thresholds.

Thresholds come from the simulation alone. An earlier version re-fitted them each build on the day's live domain scores (an empirical null, after Efron); that made levels jump whenever feeds dropped out of the sample (Iran moved from Watch to Critical when key-gated inputs went missing), so it was removed. The page data still carries `calib` as `[0, 1]`. `docs/BACKTEST.md` checks the simulated thresholds against real calm-day percentiles where the slow series have enough history.

So a theatre at Watch is in the top 10% of calm-world readings: expected by chance about one day in ten. Elevated is one in twenty, Critical one in a hundred. A level says "this reading is rare if nothing is happening", not "war is coming".

Percentile thresholds from real history are better in principle, but most live signals have months, not years, of data. `docs/BACKTEST.md` compares the simulated thresholds with real calm-day percentiles wherever the slow series have enough history.

Fewer than two domains with a score gives **insufficient data**. Elevated or Critical with no fast (leading) domain firing is labelled **lagging only**.

### Confidence

`confidence = domain weight covered x share of the theatre's signals that have a score x (1 - mean share of the 97-day window that was missing)`. The label is Low when more than 20% of the theatre's signals have no score, Medium above 10%, otherwise High.

## Pseudocode

```
compute_composite_score(metrics, weights, baseline_window = None):   # None = 1-year baseline, 90 days if too short
    for each metric m:
        s[m] = score_series(m.points, m.kind, baseline_window)       # stage 1-2
        z[m] = max(0, direction(m.direction, s[m].z))                # up: z, down: -z, both: |z|; one-sided
    for each domain d:
        groups = merge metrics of d whose recent changes correlate > 0.8      # stage 3
        zg     = mean z within each group
        top    = strongest 6 of zg, sorted descending
        w      = exponential OWA weights solved for orness 0.7
        D[d]   = sum(w * top)  (x 0.7 if only one group)             # stage 4
    live     = domains with a score  (need at least two)
    I[d]     = 100 + 10 * D[d]
    M, S     = weighted mean and standard deviation of I over live, weights renormalised
    MPI      = M + S * S / M                                         # stage 5
    zc       = (MPI - 100) / 10
    thresholds = percentiles 90/95/99 of the calm-world simulation for this theatre's shape
    level    = Normal | Watch | Elevated | Critical by zc against thresholds
    score    = 100 / (1 + exp(-(zc - t90) / ((t99 - t90) / ln 9)))
    return level, score, zc, imbalance = S, worst = argmax z[m], confidence, contribution[d] = w[d] * D[d] / sum(w[live])
```

`engine.compute_composite_score(metrics, weights, baseline_window=90)` runs exactly this on a plain dictionary of series, so it can be called from a notebook or script.

## Weights

`warwatch/weights.json` holds every version with date, change note, per-theatre domain weights (each row sums to 1) and a one-line rationale per theatre. `docs/weights_<version>.csv` is the same table for spreadsheets (`python3 warwatch/backtest.py weights`). The weights are expert priors based on how each theatre's war signature appears in open data (Taiwan leans on information and geospatial, Yemen on shipping, Sudan and DR Congo on events and fires). They are **not fitted**: there are too few wars to fit them without overfitting, and the backtest does not tune them. To change them, add a new version, keep the old one, and say why.

## Where this departs from the brief, and why

| Brief | What was built | Reason |
|---|---|---|
| STL/MSTL decomposition | Monthly series: per-calendar-month median seasonal factor on log values. Daily series: 1-year rolling baseline (90 days for short histories), no seasonal term. | STL needs years of data per series; the live daily series have under 6 months. Weekly seasonality is absorbed by the 7-day mean. |
| NumPy/Pandas | Python standard library | Keeps the build dependency-free on free GitHub runners. The maths is vectorisable if needed. |
| REST API | `audit.json` and `index.json` published with the site, plus a Python entry point | The site is static (free hosting). A REST service would need a server. |
| `MPI = M +- S(S/M)` | `+` for higher = worse | The sign of the penalty depends on the direction of the index. The brief's text allows either; with risk rising, `+` stops a single extreme domain being averaged away. |
| Correlation on levels | Correlation on recent changes | Two trending series correlate by construction. |
| OWA across all signals | OWA over each domain's strongest 6 groups | With 40 quiet signals in one domain, a pure OWA would bury a real signal. |
| Choquet integral | Not used | Needs an interaction capacity for each domain pair, which cannot be set without outcome data. The redundancy step covers the same ground. |
| Backtests on Ukraine 2022, Houthi 2024, Hamas-Israel 2023, Taiwan 2022 | Run on the slow indicators only (`docs/BACKTEST.md`) | The leading feeds do not exist before 2026. |
| Shapley values | Exact additive contributions `w * z` | The mean part of the index is additive, so these are its Shapley shares. The imbalance penalty is an extra term. |
| Percentile thresholds from history | From a calm-world simulation, checked against history | Not enough live history yet. |

## References

OECD/JRC (2008) *Handbook on Constructing Composite Indicators*. Mazziotta and Pareto (2016) "On a generalized non-compensatory composite index for measuring socio-economic phenomena", *Social Indicators Research*. Yager (1988) "On ordered weighted averaging aggregation operators", *IEEE Trans. SMC*. Grabisch (1996) "The application of fuzzy integrals in multicriteria decision making", *EJOR*. Nardo et al. (2005) *Tools for Composite Indicators Building*, JRC. Iglewicz and Hoaglin (1993) *How to Detect and Handle Outliers* (modified z-score).

## Phase 1 changes (October 2026 review)

Six changes from the methodology review, each measured in `docs/PHASE1.md`:

1. **One-sided evidence**: `max(0, z)` per signal (`engine.theatre_items`), in the calm-world simulation too.
2. **1-year baseline leaving out the latest 30 days** (`stats.score_series`), falling back to the 90-day baseline for series with under 120 baseline means.
3. **Orness 0.7** (`engine.ORNESS`).
4. **No refit of the thresholds on today's readings**: `engine.estimate_calib` is removed.
5. **Backtest replays equities and ETFs**: `fetch_market` added to `backtest.LONG` and `LAG`, with Twelve Data supplying the history because Yahoo refuses GitHub runners.
6. **Zero-weight families**: `catalog.ZERO_WEIGHT` (IODA, OONI, diesel, jet fuel, the shekel, DoD construction). They stay on the page (flag `w0` in the series data) and are still scored, but the composite ignores them. These had a noise-to-signal ratio of 1 or more on 78 labelled events. GPR acts, also flagged by the review, are not in the live catalogue, so nothing changes for them.

## Phase 2: the 30-day probability

The composite above ranks theatres by how unusual their readings are; it is not a probability. Phase 2 adds one. `warwatch/model.py` (live, standard library only) serves a model that `warwatch/validate.py` (offline, needs numpy, pandas and scipy) fits and tests; the report is `docs/MODEL.md`.

- **Target.** The probability of a qualifying event in the theatre within 30 days, defined in `docs/EVENTS.md` and labelled in `warwatch/data/events.csv` (78 events, 13 theatres, 2018 to 2026). Days in the 30 after an event are left out.
- **Evidence.** One value per family and theatre: `max(0, z)` for the strongest series of the family (a family is a source in a theatre, such as GDELT threats in Iran), at most 5. GDELT threat, posture, fight and pre-force shares join the counts as families (`backtest/history/gdelt_country_day.csv.gz` holds the 2018 on history, so the year baseline works from day one). Zero-weight families stay out.
- **Model.** Log-odds = theatre intercept (pooled toward the global one) + three conflict-history terms + the sum of family weight x evidence / 5. Family weights are constrained to be zero or positive, so more evidence can never lower the risk, and ridge-penalised. The ridge replaces the rare-events correction the review proposed (positives are about 5% of days); the shrink below does the rest.
- **Shrink.** The published probability is pulled toward the theatre's base rate in log-odds by gamma, floored at phi times the base rate and capped at the highest value seen out of sample. Gamma and phi are refitted on earlier test years only.
- **Interval.** The 5th to 95th percentile over 40 refits on resampled theatre-years. It covers parameter uncertainty, not event randomness, and it collapses to a point where the floor binds.
- **Levels.** Normal below 5%, Watch 5% to 10%, Elevated 10% to 25%, Critical 25% or more, fixed bands. A theatre is what the probability says, not a percentile of a simulated calm world.
- **Global.** The chance of an event in at least one theatre, `1 - prod(1 - p)`, an upper bound because theatres move together; its level cuts the odds against the climatological value where the theatre bands cut the pooled base rate. A second number multiplies each theatre's probability by its historical share of market-moving events.
- **Explanation.** Each probability lists the families that moved it in log-odds, so a reader sees what a change is made of.
- **Markets.** Liquid Polymarket war markets (at least $50,000 traded) for a theatre are put on a 30-day horizon, recalibrated with a curve fitted on 602 resolved markets priced 30 days out, averaged in log-odds by volume, and blended at 30%. The blend is computed and logged next to the model's number but does not set the level until the forward record shows it helps (`blend_active` in the model file, off).
- **Gates.** The model sets the page's levels only if, on rolling-origin out-of-sample tests, the Brier skill against each theatre's base rate is positive, the lower end of the AUC interval is above 0.5, and it beats a shuffled-timing control. `active` in `warwatch/data/model_weights.json` follows the gates. Otherwise it runs in shadow: probabilities go to the forward record, and the composite keeps the levels.
- **Forward record.** `forward/log.csv` gets every theatre's probability once per UTC day, before any outcome, each row hashed with the one before; `warwatch/forward_score.py` verifies the chain and scores matured forecasts quarterly (`docs/FORWARD.md`).
- **Refit.** `.github/workflows/refit.yml` runs monthly: extends the GDELT history, reruns validation, refits and commits the weights. Adding an event to `events.csv` as it happens, and moving `events_through.txt`, is what keeps the labels and the conflict-history terms current.

## Phase 3 changes (October 2026, after the indicator study)

Two faults found by testing every series against 161 events and calm periods, 2019 on (`docs/INDICATORSTUDY.md`):

1. **Prices are scored on their change, not their level.** A trending price sits above its own yearly baseline for months, so gold, copper, FX and the defence stocks read z >= 2 on 20% to 34% of calm days. `catalog.CHANGE_SCORED` marks them with `transform: "chg"`, and `stats.score_series` scores their % change over 20 trading days (3 months for monthly series) instead; the same series then read z >= 2 on 2% to 10% of calm days. VIX and power prices mean-revert and keep their level. The page charts these series as the change they are scored on.
2. **The calm world is measured, not assumed.** The thresholds' simulation drew each signal from a near-normal. Real signals are far heavier-tailed: on calm days the pooled series read z >= 2 on 11.6% of days and z >= 3 on 6.3% (normal: 2.3% and 0.13%). `warwatch/nullfit.py` writes 1,001 quantiles of that calm-day distribution (333 series) to `warwatch/data/null_z.json`, and `engine._null_draw` samples from them. In the replay (2021 to 2024, slow indicators) the share of calm days above Normal fell from 31% to 6%: Critical 11.6% to 1.2%, Elevated 12.5% to 2.6%, Watch 7.0% to 2.0%.

The levels now mean what they say: rare if nothing is happening. They still do not rise before events (replay AUC 0.45), so they describe what is unusual now, not what is coming.
