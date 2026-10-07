# Methodology review: analysis scripts

Reproduces the numbers in the review document. Nothing here is used by the live dashboard.

Inputs: `warwatch/backtest/history` (committed), `review/data/*.gz` (back-filled by `review/backfill.py` and
`review/polymarket.py` on GitHub's runners), and the labelled events in `events_full.csv`.
Scripts expect the repo's `warwatch/` package on the path (they insert `/home/claude/warwatch/warwatch`; change it to your checkout).

| Step | Script | Output |
| --- | --- | --- |
| Point-in-time z history of the 155 backtest series (+ 15 equities the repo backtest skips) | `zhist.py`, `zhist2.py` | `zhist.pkl` |
| Same series on a 1-year baseline and EWMA | `scorers.py`, `build_alt.py` | `zhist_long.pkl`, `zhist_ewma.pkl` |
| Back-filled feeds as series (GDELT, GPSJam, OONI, GPR, UCDP) and their z histories | `build_new.py`, `score_new.py` | `newseries.pkl`, `znew_*.pkl` |
| Theatre-day panel and 30-day-ahead labels | `panel.py` | |
| Aggregation methods compared, leave one theatre out | `evaluate.py`, `run_eval.py events_full.csv <pkls>` | `results/eval_*.txt` |
| Indicator families ranked by noise-to-signal | `famtable.py` | `results/famtable.csv` |
| Probability models, rolling origin, conflict-history baseline | `rolling.py`, `rolling2.py`, `ablate.py` | `results/event_hits.csv` |
| Event study and shuffled-timing control | `evstudy2.py` | `results/event_study_curves.csv` |
| Market-moving events | `marketmove.py` | `event_market_moves.csv` |
| Prediction markets | `polymkt.py review/data/polymarket_war.jsonl.gz` | `results/poly_*.csv` |
| Aggregation simulations (OWA, Mazziotta-Pareto, build-up) | `sims.py` | |
| Offline replay of today's live state from committed caches | `live_offline.py` | |
