# Prediction study diagnostics

One-off scripts behind sections 1 and 2 of the prediction-study report. Run from the repository root; the first run builds the published model's out-of-sample record once and caches it in `.cache/` (ignored by git).

| Script | What it prints |
|---|---|
| `base.py` | The cached baseline: published, history-only and base-rate probabilities, 2021 on |
| `diag.py` | Within-theatre AUC by lead time, hot and cold theatres, event type, theatre; Murphy decomposition; event rate by year |
| `power.py` | Power of the shuffled-timing gate by true AUC and years of record (semi-synthetic); writes `power.json` |
| `fwdgate.py` | How often the forward gates pass on replayed 90-, 180- and 365-day windows, for the published, timing-scrambled and history-only forecasts |
| `labels.py` | UCDP fatality escalations as labels: count, overlap with events.csv, the model's skill on them |
| `recal.py` | Exploratory: rolling recalibration and a theatre offset, 2022 on |
| `single.py` | Within-theatre AUC of every input family alone, against a circular-shift null for the best of them; writes `single.json` |

    python3 backtest/predstudy/diag/diag.py
