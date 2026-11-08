# Next timing test: plan, fixed before it is run

Committed 2026-11-05, after the prediction study (`docs/PREDSTUDY_PLAN.md`, report in the project's `prediction-study` folder) and before any of the candidates below has been run in the timing study's runner. Two of them were seen in exploratory checks on the same 2021 to 2026 record (`backtest/predstudy/diag/variants.py`, `equalweight.py`), so the backtest can only screen them; the forward record decides.

## Candidates

| Id | Change | Why |
|---|---|---|
| S1 | The published model without its three conflict-history terms (events in the last year, last three years, log days since the latest) | They point the wrong way within a theatre (within theatre-year AUC 0.304): they jump after each event, when the next one is not imminent. Exploratory: dropping them gave Brier skill +0.0066 against +0.0050, AUC 0.640 against 0.633, shuffled-timing p 0.12 against 0.19 |
| C1 | CrisisWatch as a family: the live `osint.crisiswatch_series` (2 for a conflict-risk alert on the theatre, 1 for a deteriorated situation), monthly, public on the 5th of its month, on the archive back-filled from the Wayback Machine (`backtest/predstudy/cw_backfill.py`; 51 issues, about half the months since November 2017) | The only new source to pass its pre-registered test (plan question 5: p = 0.003, within-theatre odds ratio 2.1). Months with no recovered issue are missing, not zero |
| S1+C1 | Both | |

## Test

The timing study's runner unchanged (`timingstudy.Study`, the three gates, 2,000 circular shifts). Pass: all three gates with the shuffled-timing p below 0.05 / 3. Also reported, not gating: within-theatre AUC and within theatre-year AUC, each against its own shifted null.

## Then

Whatever passes, or S1 if none does (it scores better on every measure and costs nothing), is logged as a shadow forecast in the forward record and read under the revised forward gates (`forward_score.gates`: one read at 365 matured days, shuffled-timing control at 0.05 / 3). The unweighted composite of the inputs (exploratory within-theatre AUC 0.555 to 0.560) is logged alongside as a description, not a candidate.

## Result (run 2026-11-05, `python3 warwatch/predstudy.py next`, output `backtest/predstudy/next_results.json`)

| Id | Brier skill | AUC (95% lower end) | Shuffled-timing p | Within-theatre AUC | Pass |
|---|---|---|---|---|---|
| Published | +0.0050 | 0.633 (0.564) | 0.19 | 0.536 | no |
| S1 | +0.0071 | 0.627 (0.560) | 0.29 | 0.532 | no |
| C1 | +0.0049 | 0.633 (0.564) | 0.19 | 0.536 | no |
| S1+C1 | +0.0072 | 0.627 (0.559) | 0.29 | 0.533 | no |

None passes. C1 is not a fair test yet: the monthly scorer needs about 40 issues of history, so CrisisWatch evidence only starts in May 2023, and the recovered archive has no issues from July 2024 to October 2026. It stays untested until those months are filled. Per the plan, S1 goes into the forward record as a shadow forecast; its better Brier skill comes from calibration, not timing.

## Revised forward gates, replayed (`backtest/predstudy/diag/fwdgate_new.py`)

37 windows of 365 days on the 2021 to 2026 record:

| Forecast | Old gates pass | New gates pass | Median shuffled-timing p |
|---|---|---|---|
| Published | 0.22 | 0.00 | 0.69 |
| Timing scrambled | 0.24 | 0.03 | 0.36 |
| History only | 0.11 | 0.00 | 0.97 |

The old gates passed a forecast with scrambled timing as often as the real one. The new gates almost never pass it (3%, close to the 1.7% the alpha allows).

## Shadow record (added 2026-11-05)

S1 is fitted by `python3 warwatch/validate.py fit-nohist` (monthly, in the refit workflow) to `warwatch/data/model_weights_nohist.json`, logged by every build to `forward/log_nohist.csv` and scored in `docs/FORWARD_NOHIST.md`. It never drives the page. Because it is a fourth forecast read under the forward gates, the shuffled-timing threshold is now 0.05 / 4 = 0.0125 for every target, not 0.05 / 3 as written above. The unweighted composite is not logged: its evidence would need a record of its own, and it is a description, not a candidate. The forward report also describes, without gating, the log score and, on days a liquid market was priced, the calibrated market and the 30% blend the page would publish if the blend were switched on.

## Addendum, 2026-11-05: the LLM forecaster

A fifth forecast is now read under the forward gates: a free LLM forecaster (`warwatch/llmcast.py`, recommendation 4 of the prediction study). Once a day, Google's Gemini API (free tier, with Google Search grounding) is asked the page's question for each theatre, with the event codebook, the theatre's base rate and its last three events, but never the model's probability. Its answers go to `forward/log_llm.csv` (hash-chained, the same format as the other shadow records) and are scored in `docs/FORWARD_LLM.md`, with its own read at 365 matured days. The shuffled-timing threshold is now 0.05 / 5 = 0.01 for every target. It cannot be backtested honestly, so only the forward record counts. GitHub Models, the first choice, was retired by GitHub on 30 July 2026.
