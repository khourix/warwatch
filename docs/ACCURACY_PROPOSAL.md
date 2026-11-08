# Proposal: better accuracy and timing, with free LLMs

Written 2026-11-08. A plan, not a result. Nothing here changes the page, the model weights, the event list or the forward records. Each step below is tested by the rules already in force (out-of-sample checks before anything goes live, forward record before anything is promoted).

## 1. Where WarWatch stands

| Finding | Evidence |
|---|---|
| The 30-day model knows **where** risk is, not **when** | Within-theatre AUC 0.534 (0.5 is chance). The probability sits flat at about 1.35 times the theatre's normal level from 60 days out to the day before an event (`FEATURESTUDY_SUMMARY.md`). |
| More data and more processing do not fix it | 12 candidates in the timing study (new feeds, shapes, cleaning, other targets) moved within-theatre AUC by -0.048 to +0.004; passing needs +0.05 to +0.10 (`TIMINGSTUDY.md`). Same answer in the feature, lead, indicator, Wikipedia, GDELT-wide, trade and fire studies. |
| In the hot theatres the model is worse than chance at timing | AUC Ukraine 0.44, Iran 0.47, Korea 0.24 (`MODEL.md`). The conflict-history terms point the wrong way within a theatre (within theatre-year AUC 0.30, `PREDSTUDY_NEXT_PLAN.md`). |
| The timing signal that exists sits in **text and judgement** | CrisisWatch conflict-risk alerts: within-theatre odds ratio 2.1, p = 0.003, the one new source to pass its test (`PREDSTUDY_NEXT_PLAN.md`). Polymarket 7-day moves: within-theatre AUC 0.57 (description, few theatres). Among the held indicators, the only stable rise before events is in GDELT news tone (pre-force share 0.61, threat 0.60 to 0.61, `BACKTEST_SUMMARY.md`), which is also text. Radar base watch passed its own test (p = 0.043), the one physical exception. |
| The probability is too low at the low end | Days given 0% to 2% were followed by an event 6.2% of the time (`MODEL.md`); event frequency rose from 1.6% of days in 2021 to 10.5% in 2024 and 11.6% in 2025 (`BACKTEST_SUMMARY.md`). |
| The event list is out of date | `events_through.txt` is 2026-10-12. No forward forecast has matured (`FORWARD.md`: 0 of 90 days). All five forward records wait on it. |
| 2026 is probably under-labelled (guess, to be checked) | 12 events in 2026 to 12 October, against 33 in 2024 and 31 in 2025, in a year with a war on Iran, a Hormuz shipping campaign and Houthi strikes on Saudi Arabia. Missing events make a theatre look calmer than it is, in the fit and in the score. |
| The forward test cannot see small gains | Power study (`backtest/predstudy/diag/power.json`): one year of record at threshold 0.05 detects a true within-theatre AUC of 0.60 90% of the time and 0.55 only 55% of the time; at 0.0038 these fall to 71% and 34%. Today's threshold (0.05 / 5 = 0.01) sits between. Each extra forecast read lowers the threshold and the power for all of them. |

**Reading.** The timing information that exists in public data is in what people write and decide (analysts, markets, governments), not in counts of planes, ships, prices or contracts. An LLM (a text AI model) is a cheap way to read that writing every day, in the same way each day. That is where it can help accuracy. It does not replace the model; it adds the "when" that the model lacks, and it fixes the labels that every test depends on.

## 2. The proposal

Six work packages, in order. LLM packages are marked **LLM**.

### P1. Event desk (LLM): current, complete labels

| Item | Detail |
|---|---|
| What | A daily job reads the headlines and records we already collect (Google News incident headlines, GDELT, UCDP, CrisisWatch, the alert feeds) and proposes qualifying events under `docs/EVENTS.md`, each with a named public source. It opens one pull request a week with the candidates and moves `events_through.txt` only for days that were checked. Anthony (or a second model, then Anthony) approves. |
| Also | A one-off pass over 2026 to find events that were missed (see the 2026 count above), and a check of all 165 for the "continuation, not a new event" rule. Flags only; a person decides each change, and corrections follow the codebook (new row plus a note, no silent edits). |
| Why first | Every number in WarWatch is scored against this list. Without it, no forward forecast matures and the conflict-history terms go stale. |
| Test before use | Run it blind on 2024 to 2025 news and compare with the hand list. Pass: it finds at least 90% of the listed events, and at least half of its extra candidates are judged real on review. Recorded in `docs/`. |
| Risk | Labels that drift toward what the LLM likes. Control: fixed codebook prompt, pinned model version written to each row's note, human approval, and the blind test repeated each quarter. |

### P2. Analyst reading (LLM): a daily judgement per theatre

| Item | Detail |
|---|---|
| What | Rebuild `llmcast.py` (PR #61). Each day, for each theatre, the LLM gets the last 14 days of our own collected headlines and records (not a live web search), the codebook, the base rate and recent events, and never the model's number. It returns (a) a fixed checklist modelled on what passed: deteriorated or alert in CrisisWatch's sense, plus the costly signs analysts cite (evacuations, ultimatums, mobilisation, airspace and maritime warnings, leaders' threats with dates), each with the headline it rests on; and (b) a 30-day probability. |
| Why this design | Free Gemini models have no free Google Search today, so #61 as merged would fail or answer without news. Our own headlines make the input free, logged and repeatable: anyone can see what the model read. The leading LLM forecasting systems (ForecastBench tool-use leaderboard, October 2026: level with the superforecaster median) work from retrieved news. |
| Record | Hash-chained forward record, as now. The checklist items also go to the record, so they can be tested as tells. |
| Honest backtest, if possible | An LLM cannot be backtested on years it has read about. Open-weight models with a published training cutoff can be tested on news after that cutoff only. Example: `gpt-oss-120b` (free on Groq) states a cutoff of June 2024 (model card; to verify), which would give July 2024 to now: 63 listed events, more once 2026 is complete. Needs past headline text for that window (GDELT page titles through BigQuery, inside the free tier; size to be checked against the $1 budget first). If the spike shows it is not feasible at $0, the forward record alone decides. |
| Not done | No LLM output reaches the page until it passes the forward gates. |

### P3. One primary forecast, read once

| Item | Detail |
|---|---|
| What | Name one primary 30-day forecast for the forward test before it starts: the equal-weight average, in log-odds, of the model (S1, without the history terms), the analyst reading (P2) and, where they exist, the calibrated market and the CrisisWatch rating. Weights fixed in writing now, not fitted. The other records stay as descriptions. |
| Why | Pooling independent judgements is the most reliable gain in forecasting research, and it is the honest way to combine "where" (the model) with "when" (judgement). Reading one forecast instead of five raises the threshold back from 0.01 to 0.05; at 0.05 one year detects a real within-theatre AUC of 0.60 90% of the time (power study, section 1). |
| Needs | Your decision: it changes how the forward gates are read (`forward_score.py`, `METHODOLOGY.md`). Pre-registered in a plan file before the first day is logged. |

### P4. Fill the CrisisWatch gap

The one source that passed cannot be used in the model because its recovered archive stops in July 2024 (`PREDSTUDY_NEXT_PLAN.md`, C1). Recover July 2024 to October 2026 from other public copies (Crisis Group's monthly pages and RSS, web archives), parse each issue into the existing table (an LLM can do the parsing; the source text is what counts), then run C1 under its fixed plan. No new feed, small effort, and it tests the strongest lead we have.

### P5. Tells that nobody watches yet (LLM)

Two tells are listed as "none yet": civil-defence instructions and airspace closures (`TELLS.md`). Both appear as text (government notices, embassy alerts, NOTAM summaries in the news). The P2 checklist extracts them per theatre per day. They are scored as tells, by the fixed rules in `tells.py`, on the forward record.

### P6. Calibration, after P1

Once 2026 is fully labelled, rerun `validate.py fit` and `eventstudy.py` so the base rates and the shrink see the higher event frequency. No hand tuning; the monthly refit decides. Most of the low-end under-prediction is expected to come from missing labels and the regime change, and P3's pooling corrects level on the forward record.

## 3. What to stop

| Stop | Why |
|---|---|
| New indicator feeds for the 30-day model | 12+ studies, none passed. Keep the feeds that serve the map and the tells; do not expect timing from them. |
| More shadow forecasts read as tests | Each one lowers the bar for all of them (section 1, power). New ideas go in as descriptions unless they replace one. |
| LLM text on the public page | It can invent facts on a warning page. The page shows numbers and sourced items only. |
| LLM-made inputs inside the fitted model, tested on the past | The LLM already knows what happened, so the test would flatter it. Only the post-cutoff window (P2) or the forward record counts. |

## 4. Free LLM services

| Service | Use | Limits (as published 2026-11-08) | Note |
|---|---|---|---|
| Gemini API free tier (`gemini-3.5-flash-lite`, `gemini-3.8-flash`) | Main: P1, P2, P4, P5 | Free tokens; daily limits shown only in the AI Studio console. No free Google Search on Gemini 3 models. | Free-tier inputs may be used by Google to improve products. Our inputs are public data, so acceptable. Pin an exact model, never a `-latest` alias. |
| Groq free plan (`gpt-oss-120b`) | Backup, and the post-cutoff backtest in P2 | About 1,000 requests and 200,000 tokens a day per model (third-party summaries; check the console) | Open-weight model with a stated cutoff. |
| Local model on the ThinkPad | Last fallback only | No limit, $0 | 14 GB memory, no graphics chip: slow, and it shares the machine with the Telegram bots. |

Cost: $0. Keys go in Actions secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`); each route is marked verified only after a live probe on a GitHub runner.

## 5. Order and gates

| Step | Delivers | Gate before the next step |
|---|---|---|
| 1 | P1 event desk, blind test on 2024 to 2025 | Blind test passes; 2026 backlog reviewed and approved |
| 2 | P4 CrisisWatch gap, C1 run under its fixed plan | Result recorded, pass or fail |
| 3 | P2 analyst reading (rebuilt #61), plus the post-cutoff spike | Live probe on a runner; spike says feasible or not |
| 4 | P3 pre-registered primary forecast | Your decision on the forward-gate change |
| 5 | P5 tells, P6 refit | Monthly refit and tells record as usual |

What success looks like, stated now so it cannot move: the primary forecast passes the forward gates at its 365-day read with a within-theatre AUC of 0.60 or more. Anything less is reported as it is.
