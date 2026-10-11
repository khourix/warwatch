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

## Timing tells (October 2026, assessment phase B)

Each theatre carries two readings. **Standing risk** is the 30-day chance as a multiple of the theatre's usual chance (`p / base`); it is coloured only while the model passes its gates. **Timing tells** are yes-or-no checks over the last 7 days on costly, hard-to-reverse actions that came days before strikes in the cases analysts cite: US departures ordered or authorised, a US advisory raise with UK advice changing the same week, airliners thinning out, tankers parked forward, airspace closures, firing and missile warnings at sea, and strike waves in wars under way. Bases emptying and civil-defence instructions are listed as not watched. The rules are fixed by hand (`warwatch/tells.py`), never set a level and never enter the model. Each carries its record on our own history (`docs/TELLS.md`), and every day's state goes to the hash-chained `forward/tells.csv`, so they are tested on the forward record from day one.

## Iraq and the Gulf states (October 2026, assessment phase D)

Iraq and the Gulf states (Saudi Arabia, the UAE, Qatar, Bahrain, Kuwait, Oman) are sub-theatres of the Middle East: not fronts of their own, but countries struck or used to strike in their neighbours' wars. Each answers "will this country be struck, or used to strike, within 30 days?" and has its own tab under Middle East. The region level stays the worst child.

- **Inputs.** Their own advisories (US and UK), GDELT events located there (back-filled from 2018), headlines, NOTAMs (Baghdad; Kuwait, Bahrain, Qatar, the Emirates, Jeddah and Muscat), aircraft, GPS and warning boxes, port calls (Umm Qasr and Basra; Jebel Ali, Fujairah, Ras Tanura, Ras Laffan and Hamad), Gulf country equity ETFs, DoD spending there, ACLED and UCDP counts. Iran keeps Iraq's advisories and the Baghdad NOTAMs, and no Iran or Yemen input changes, so their histories stay as they were.
- **Labels.** Events are filed in `events.csv` under the theatre whose war they belong to, as before; `site_theatre` marks the 16 that happened in Iraq or the Gulf states (9 and 7, counting `events_added.csv`). Such an event labels both.
- **Model.** About 8 events each is too few for weights of their own. The theatres' model is fitted exactly as before, on the theatres' rows only. A sub-theatre then reads the stronger of its own and its parents' evidence in each family (Iran for both, Yemen too for the Gulf states), uses the theatres' family weights and history terms, and gets its own offset, a ridge-penalised step from the mean offset of the three Middle East theatres; its base rate is pooled toward theirs. Its out-of-sample record is reported on its own rows (`docs/MODEL.md`, "Sub-theatres") and kept out of the theatres' gates, since its events are its parents' too. Its chance is shown as validated only when the theatres' model and its own rows both pass the three gates; until then the page shows its signal pressure, and the chance goes to the forward record. The chance of an event anywhere counts the theatres only, so nothing is counted twice.

## Phase C: what is predicted (October 2026)

- **Labels: 161 events.** The 83 events added for the feature study (chosen from the public record by the codebook alone, `events_added.csv`) are now in `events.csv` with the 78 of the seed list. The seed list's skill was partly selection: the shuffle gate was failing on it already, so the model was in shadow and nothing on the page changes. Every test from here on has about twice the events.
- **Steps and actions are scored as events, not z-scores.** A US travel-advisory level is a decision that holds for months. Scored as a level, one raise read +5 against a flat year and kept reading high until the year baseline caught up, so the advisory sums sat at or above the signal line (z >= 3) on 6.0% of calm days in the 2018-2026 archive. `catalog` now marks them `transform: "step"`, and `stats.score_series` scores the change over the last 14 days instead, at 3 per level of one country: one raise reads +3, two read +5, and the series goes quiet two weeks later. The same archive then sits at the signal line on 2.5% of calm days and 2.8% of the 30 days before an event; the level score did so on 5.4% of the days before an event, less often than on calm days. A CrisisWatch rating is already a monthly judgement, so `transform: "event"` scores its newest value at 2.5 per point (an alert, rated 2, reads +5; a deteriorated situation +2.5). As a level it could not have been scored before 2029, since monthly scoring needs 40 issues and the record starts in October 2026. Neither family is in the fitted model (advisory steps failed its gates in the feature study, and CrisisWatch has no history), so this changes the page's readings and the composite, not the 30-day probability. The page charts them as the levels they are, with the score explained in the series label.
- **Trending series stay scored on their level (tested, not adopted).** The proposal was to score procurement, tenders and chronic GPS jamming on their change, as prices are. Each of their 33 families was scored day by day three ways (its level as now, its % change, and its absolute change, over 20 days or 3 months) and compared on the indicator study's measures: how often the 30-day maximum reached z 2 in calm windows, how often in the 30 days before events, and the AUC between the two. The level score, with its year baseline, its 30-day guard and the noise floor, already keeps calm false alarms at 2% to 17% in all but three families. % change raised them in 19 of the 33 families and absolute change in 27 (GPS jamming from 7% to 48% and 35%). The AUC rose by more than 0.02 in 9 and 13 families and fell by as much in 12 and 10: noise, for about 100 events. Of the three exceptions, EU medical tenders (32%) and US air-charter awards (21%) lost most of their hit rate when scored on change (44% to 1%, 23% to 10%), and US blood-bank awards (22%) did no better. Nothing changed.
- **A 7-day strike-wave target, in shadow.** For wars already under way the useful question is a strike wave next week, not an onset. `validate.py fit-wave` fits the same model to that target: a theatre-day is positive when a strike wave starts within 7 days, a start being the day the strike-wave tell turns on after 7 days off (alert waves in the last 7 days at least double the median of the 90 days before, and at least 5; `tells.wave_onsets`). Only theatres whose alert-wave feed holds a year enter the fit: Israel now (Tzeva Adom and the Home Front Command archive, 34 waves since 2017), Ukraine once alerts.in.ua has a year. On the backtest it fails every gate (AUC 0.36, Brier skill -0.004, 18 test waves; `docs/MODEL_WAVE.md`): a start is defined against the recent tempo, so the evidence that rises in a war marks the weeks when a further doubling is less likely. It is logged anyway, to `forward/log_wave.csv`, beside the armed-force model's `forward/log_armed.csv`, so all three targets are tested the same way on data nobody could tune.
- **Promotion is decided on the forward record.** `forward_score.py` scores each record against its own target and reads two forward gates once 90 days have matured: Brier skill against the base rate above 0, and the lower end of the AUC interval (resampling theatre-months) above 0.5. The first of the three targets to pass is the one to promote to the page; until then the page keeps its current reading.

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

- **Target.** The probability of a qualifying event in the theatre within 30 days, defined in `docs/EVENTS.md` and labelled in `warwatch/data/events.csv` (78 events, 13 theatres, 2018 to 2026; 161 since October 2026, see below). Days in the 30 after an event are left out.
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
