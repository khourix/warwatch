# Outside forecasts (ConflictForecast and VIEWS): test plan, fixed before any forecast is read

Committed 2026-10-09 with `backfill/sources_forecasts.py`, before the back-fill ran.

**Why these sources.** Both are free, open, peer-reviewed conflict forecasts that publish a new probability for every country each month: ConflictForecast.org (Mueller, Rauh and Seimon; news-text topic model, armed-conflict and any-violence risk over 3 and 12 months) and VIEWS (Uppsala and PRIO; state-based conflict, country-month). Each monthly vintage is kept as published, so the test only ever sees what existed on the day. They answer two questions: does an outside forecast rise before our events (a new indicator), and does it rank theatres and months better than our 30-day model (a benchmark, or an input).

**Theatre series.** For each theatre, the highest probability among its countries (the list is in `backfill/sources_forecasts.py`). ConflictForecast: the 3-month armed-conflict risk (`armedconf_3`; `anyviolence_3` as the second family). VIEWS: the probability of at least 25 state-based deaths (`main_dich`, or the run's equivalent field) for the first forecast month. A vintage counts as public on the first day of the month after the month it is labelled with, which is later than either project actually publishes. A vintage that is missing leaves the previous one in force.

**Test A, lead.** The monthly series is scored as the live build scores a monthly series (`stats.score_series`, kind monthly, direction up), then tested with the indicator study's method: highest z in the 30 days before each event (161 listed, merged within 30 days, from 2019) against calm 30-day windows of the same theatre. Pass rule, per family, as for Wikipedia: on the 83 added events hit rate at z >= 2 beats the calm false-alarm rate with p < 0.05; on the 78 original events p < 0.10; AUC above 0.55 on both halves.

**Test B, standing risk.** The probability itself on the day before each event, against the same measure on calm days stepped every 30 days, all theatres pooled (what our model's out-of-sample AUC of 0.605 measures). A family that reaches AUC 0.65 on the 83 added events, with a bootstrap 95% interval above 0.5, is a candidate input: it is added to the 30-day model and must pass the model's existing gates (Brier skill above 0, AUC interval above 0.5, beats the shuffled-timing control at p < 0.05) before it reaches the page.

**No tuning.** A family that fails is recorded here as failed. The countries, fields, publication lag, windows and cut-offs are not changed after the data is seen.
