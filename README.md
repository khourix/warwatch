# warwatch

A free, public-data early-warning dashboard for conflict risk. It watches
supply-chain signals (boots and armor, Toyota-class pickups, blood and trauma
supplies, forward infrastructure), sea and air flows, and public attention,
for the US and EU supply side and for the Ukraine and Middle East theatres.

It is decision support, not a prediction. Levels count how many independent
domains move together; they are not probabilities. See [docs/PROPOSAL.md](docs/PROPOSAL.md)
for the design, the verified data routes and the limits.

- Runs on GitHub Actions every 6 hours, standard-library Python, no database.
- `python3 warwatch/run.py --out site/index.html` builds the page;
  `--demo buildup` shows a synthetic scenario.
- Tests: `python3 warwatch/tests/test_warwatch.py`.
- Keys (all free) go in Settings > Secrets and variables > Actions:
  `CENSUS_API_KEY`, `SAM_API_KEY`, `FRED_API_KEY`. Never commit a key.
- `warwatch/history/` holds small CSVs for sources that only expose "now"
  (ADS-B, US advisory levels). Public data only.
