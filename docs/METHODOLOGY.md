# Warwatch v7 aggregation method

How a pile of indicators becomes one level per theatre. Code: `warwatch/engine.py` (aggregation), `warwatch/stats.py` (per-signal scoring), weights in `warwatch/weights.json`. Every step is deterministic, runs on the Python standard library, and the numbers behind each theatre are written to `audit.json` on every build.

The old method counted how many of five groups were over a threshold (0/5 to 5/5). That threw away how far over, treated two signals from one event as two events, let one strong group stand in for the rest, and moved in whole steps. The new method keeps the same five domains but replaces the counting.

## The seven stages

| # | Stage | What it does | Where |
|---|---|---|---|
| 1 | Baseline | Each signal is compared with its own recent past: the last 90 days for daily signals (7-day mean against rolling 7-day means), the last 36 months with calendar-month seasonality removed for monthly ones. Gaps of up to 2 days are carried forward (LOCF); longer gaps stay missing and lower confidence. | `stats.score_series` |
| 2 | Modified z | `z = 0.6745 * (x - median) / MAD`, winsorized at +-5. The unclamped value is kept as `z_raw` in the audit log. A zero MAD (flat history) falls back to the mean absolute deviation. | `stats.modified_z` |
| 3 | Redundancy | Within one theatre and domain, signals whose last 30 daily changes (24 monthly) correlate above 0.8 are merged into one group scored at their mean, so one event seen by three sources is counted once. | `engine.groups_of` |
| 4 | Domain score | The strongest 6 groups are combined with an ordered weighted average (exponential weights, orness 0.3). Orness 0.3 leans towards "all must agree" without being a minimum: one spike barely moves a domain, several agreeing signals do. A domain with a single group is shrunk to 70%. | `engine.domain_score` |
| 5 | Theatre composite | Domain scores are put on a 100 +- 10 scale (`100 + 10 z`) and combined with the theatre's versioned domain weights by a weighted Mazziotta-Pareto index, `MPI = M + S * S / M` (M weighted mean, S weighted standard deviation). The penalty is added because higher means worse: a lopsided profile reads higher than an even one with the same mean. | `engine.mpi` |
| 6 | Level and scores | Level from calibrated thresholds (below). Threat score 0 to 100 is a logistic of the composite z, 50 at the Watch line and 90 at the Critical line. Also reported: imbalance (S), worst offender (largest single-signal z), confidence, and each domain's contribution `w * z`. | `engine.theatre_composite` |
| 7 | Hierarchy | Region level = worst child level (a crisis is not averaged away); region score = highest child score. Global Threat Index = MPI+ of the region scores (0 to 100), level = worst region level. | `engine.rollup` |

### Levels and thresholds

Watch, Elevated and Critical are the 90th, 95th and 99th percentiles of the composite in a calm world. The calm world is simulated, not observed: 2,000 draws per theatre, each signal group a standard normal in which 10% of draws are twice as wide (fatter tails than a normal), winsorized at +-5, run through the same stages 3 to 5 with the theatre's own series counts and weights. The generator is seeded, so a theatre always gets the same thresholds.

So a theatre at Watch is in the top 10% of calm-world readings: expected by chance about one day in ten. Elevated is one in twenty, Critical one in a hundred. A level says "this reading is rare if nothing is happening", not "war is coming".

Percentile thresholds from real history are better in principle, but most live signals have months, not years, of data. `docs/BACKTEST.md` compares the simulated thresholds with real calm-day percentiles wherever the slow series have enough history.

Fewer than two domains with a score gives **insufficient data**. Elevated or Critical with no fast (leading) domain firing is labelled **lagging only**.

### Confidence

`confidence = domain weight covered x share of the theatre's signals that have a score x (1 - mean share of the 97-day window that was missing)`. The label is Low when more than 20% of the theatre's signals have no score, Medium above 10%, otherwise High.

## Pseudocode

```
compute_composite_score(metrics, weights, baseline_window = 90):
    for each metric m:
        s[m] = score_series(m.points, m.kind, baseline_window)       # stage 1-2
        z[m] = direction(m.direction, s[m].z)                        # up: z, down: -z, both: |z|
    for each domain d:
        groups = merge metrics of d whose recent changes correlate > 0.8      # stage 3
        zg     = mean z within each group
        top    = strongest 6 of zg, sorted descending
        w      = exponential OWA weights solved for orness 0.3
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
| STL/MSTL decomposition | Monthly series: per-calendar-month median seasonal factor on log values. Daily series: 90-day rolling baseline, no seasonal term. | STL needs years of data per series; the live daily series have under 6 months. Weekly seasonality is absorbed by the 7-day mean. |
| NumPy/Pandas | Python standard library | Keeps the build dependency-free on free GitHub runners. The maths is vectorisable if needed. |
| REST API | `audit.json` and `index.json` published with the site, plus a Python entry point | The site is static (free hosting). A REST service would need a server. |
| `MPI = M +- S(S/M)` | `+` for higher = worse | The sign of the penalty depends on the direction of the index. The brief's text allows either; with risk rising, `+` stops a single extreme domain being averaged away. |
| Correlation on levels | Correlation on recent changes | Two trending series correlate by construction. |
| OWA across all signals | OWA over each domain's strongest 6 groups | With 40 quiet signals in one domain, a pure OWA at orness 0.3 would bury a real signal. |
| Choquet integral | Not used | Needs an interaction capacity for each domain pair, which cannot be set without outcome data. The redundancy step covers the same ground. |
| Backtests on Ukraine 2022, Houthi 2024, Hamas-Israel 2023, Taiwan 2022 | Run on the slow indicators only (`docs/BACKTEST.md`) | The leading feeds do not exist before 2026. |
| Shapley values | Exact additive contributions `w * z` | The mean part of the index is additive, so these are its Shapley shares. The imbalance penalty is an extra term. |
| Percentile thresholds from history | From a calm-world simulation, checked against history | Not enough live history yet. |

## References

OECD/JRC (2008) *Handbook on Constructing Composite Indicators*. Mazziotta and Pareto (2016) "On a generalized non-compensatory composite index for measuring socio-economic phenomena", *Social Indicators Research*. Yager (1988) "On ordered weighted averaging aggregation operators", *IEEE Trans. SMC*. Grabisch (1996) "The application of fuzzy integrals in multicriteria decision making", *EJOR*. Nardo et al. (2005) *Tools for Composite Indicators Building*, JRC. Iglewicz and Hoaglin (1993) *How to Detect and Handle Outliers* (modified z-score).
