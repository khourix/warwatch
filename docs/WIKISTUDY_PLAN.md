# Wikipedia page views: test plan, fixed before any view count is read

Committed 2026-10-09 with the article lists in `backfill/sources_wiki.py`, before the back-fill ran.

**Why this source.** Daily attention to a theatre's articles is the one new free daily series with a peer-reviewed lead result (Oswald and Ohrenhofer 2022: page views improved battle-death forecasts). It measures what readers in the region and worldwide turn to, which none of the current indicators does.

**Series.** `wiki_<theatre>`: summed daily human views of five to seven English articles per theatre. `wikiloc_<theatre>`: the main country or conflict articles in local languages. Lists are in `backfill/sources_wiki.py` and are not changed after the data is seen.

**Scoring.** Exactly as the live build scores a daily count: `stats.score_series` on the views available up to each day (7-day mean against the year before the newest 30 days), turned to the warning direction (up).

**Test.** The indicator study's method (`warwatch/indicatorstudy.py`): for each event since 2019 (161 listed, merged within 30 days), the highest z in the 30 days before it against the same measure in calm 30-day windows of the same theatre. Two families, `wiki` and `wikiloc`.

**Pass rule, per family.** All three:
1. On the 83 added events (`events_added.csv`), the hit rate at z >= 2 beats the calm false-alarm rate with p < 0.05.
2. On the 78 original events, the same holds with p < 0.10 (the direction must agree).
3. AUC of the 30-day maximum above 0.55 on both halves.

A family that passes goes into the feature study as a candidate, judged by that study's pass rule on the added events. One that fails is recorded here as failed and not tuned (no change to the articles, windows or cut-off).

## Result (2026-10-09)

Neither family passes ([WIKISTUDY.md](WIKISTUDY.md)). English views beat the false-alarm rate on the original events (50% against 35%, p = 0.016) but not on the added ones (40%, p = 0.23, AUC 0.53). Local-language views do not beat it on either half. Recorded as failed; the article lists, windows and cut-off stay as they were. One listed article does not exist under that title (`Bolivarian Armed Forces of Venezuela`) and was skipped, as the plan says.
