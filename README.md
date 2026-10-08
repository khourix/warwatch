# warwatch

A free, public-data early-warning dashboard for conflict risk. It watches
supply-chain signals (boots and armor, Toyota-class pickups, blood and trauma
supplies, forward infrastructure), sea and air flows, and public attention,
for the US and EU supply side and for the Ukraine and Middle East theatres.

It is decision support, not a prediction. Levels count how many independent
domains move together; since the Phase 2 model they are set from a fitted, validated
30-day probability per theatre (see [docs/MODEL.md](docs/MODEL.md), [docs/EVENTS.md](docs/EVENTS.md)). See [docs/PROPOSAL.md](docs/PROPOSAL.md)
for the design, the verified data routes and the limits.

- Runs on GitHub Actions every 6 hours, standard-library Python, no database.
- `python3 warwatch/run.py --out site/index.html` builds the page;
  `--demo buildup` shows a synthetic scenario.
- Tests: `python3 warwatch/tests/test_warwatch.py`.
- Keys (all free) go in Settings > Secrets and variables > Actions:
  `CENSUS_API_KEY`, `SAM_API_KEY`, `FRED_API_KEY`. Never commit a key.
- `warwatch/history/` holds small CSVs for sources that only expose "now"
  (ADS-B, US advisory levels). Public data only.
- `python3 warwatch/validate.py fit` refits the probability model and rewrites `docs/MODEL.md` (needs numpy, pandas, scipy; runs monthly in
  `.github/workflows/refit.yml`). `forward/log.csv` is the hash-chained forward record; `python3 warwatch/forward_score.py` scores it.
- `python3 warwatch/eventstudy.py` replays the model out of sample and writes the event-by-event backtest (lead times, false alarms, calibration) to `docs/BACKTEST_EVENTS.md`; `python3 warwatch/fastfeeds.py` tests the back-filled fast feeds against the same events (`docs/BACKTEST_FASTFEEDS.md`); `python3 warwatch/calibrate.py` ranks every indicator by how reliably it rose before events and compares weighting schemes out of sample (`docs/CALIBRATION.md`). `python3 warwatch/improve.py` tests candidate model changes out of sample (`docs/IMPROVEMENTS.md`). All run in the monthly refit. Results in plain words: [docs/BACKTEST_SUMMARY.md](docs/BACKTEST_SUMMARY.md).
