# Metaculus community forecasts: test plan, fixed before any forecast is read

Committed 2026-10-09 with `backfill/sources_metaculus.py`, before the back-fill ran.

**Why this source.** Metaculus forecasters update their probabilities on military questions (an invasion of Taiwan, a Russian attack on a NATO member, an Israeli strike on Iran) as news arrives. If informed people see escalation coming, their forecasts should rise before it happens. The community history is free with an account token.

**Questions.** Every binary question whose title names a theatre's place and a military action, and does not ask about a ceasefire, settlement or withdrawal (the patterns `PLACE`, `ACTION` and `EXCLUDE` in `backfill/sources_metaculus.py`, fixed here). A question can count toward more than one theatre. Its community prediction is read as it stood at the end of each UTC day, from the aggregation the post carries (recency weighted where present).

**Two families,** each a daily series per theatre:
- `mc_rise`: the mean, over the theatre's questions with a prediction that day and seven days earlier, of the change in log-odds over those seven days. Direction up.
- `mc_new`: the number of the theatre's questions that opened that day (new questions follow new worries). Direction up.

**Scoring and test.** As for Wikipedia (`docs/WIKISTUDY_PLAN.md`): scored day by day as the live build scores a daily series (`stats.score_series`), public the next day, then the highest z in the 30 days before each event (161 listed, merged within 30 days, from 2019) against calm 30-day windows of the same theatre.

**Pass rule, per family.** On the added events, hit rate at z >= 2 beats the calm false-alarm rate with p < 0.025 (0.05 split over the two families); on the original events p < 0.10; AUC above 0.55 on both halves. A family that passes goes into the feature study as a candidate; one that fails is recorded as failed and the rule is not tuned.

## Status (2026-10-09): blocked on access

The question list works: 7,861 binary questions, of which 260 match the rule (`backfill/data/metaculus/questions.csv`). The forecasts do not come with it. With this account's token every post returns its aggregations with an empty history and no latest value, and the data download (`/api/posts/{id}/download-data/`) answers 403, "Use of this endpoint is restricted". No forecast has been read, so the plan above still stands unchanged for when access is granted.
