# Prediction study: plan, fixed before any candidate is run

Committed 2026-11-05 with `backtest/predstudy/fetch.py`, after the data were pulled and their columns listed, before any of them was compared with an event. Nothing here changes the live page, `model_weights.json`, `events.csv` or the forward records.

## Questions

1. **Where is the model's skill?** Within-theatre AUC of the published model's out-of-sample probability by lead time (1-3, 4-7, 8-14, 15-21, 22-30 days before the event), by theatre state (an event in the theatre in the year before, or not), by event type, and with the history terms alone. Description only, no pass rule.
2. **Can the gates detect a real timing signal?** (a) The number of independent events needed for the shuffled-timing gate to detect a within-theatre AUC of 0.55, 0.60, 0.65 and 0.70 with 80% power, and the years of forward record that takes at the 2022-2025 event rate. (b) How often the forward gates (`forward_score.gates`: Brier skill above 0 and the theatre-month bootstrap AUC lower end above 0.5, read on 90 days) pass on replayed 90-, 180- and 365-day windows of the 2021-2026 out-of-sample record, for the published model and for the same probabilities with their timing destroyed (circular shift within each theatre). Description only.
3. **Do the geopolitical-risk indices of Caldara and Iacoviello time events?** New families, scored as the live build scores a series (`stats.score_series`), evidence = max(0, z) as for every family:

| Id | Families | Source and timing |
|---|---|---|
| G1 | `aigpr_country` (sum of `<country>_all` over the theatre's countries) and `aigpr_milconf` (sum of `<country>_military_conflict`) | AI-GPR monthly country files; a month counts as public on the 5th of the next month |
| G2 | `aigpr_pair` (sum over the theatre's directed country pairs) | AI-GPR monthly bilateral file; same lag |
| G3 | `gprd_threat` (GPRD_THREAT) and `aigpr_threat` (THREATS_GPR_AI), global: they feed every theatre | Daily files; public 7 days later (the classic daily file is posted weekly) |
| G4 | `aigpr_oilregion` (GPR_OIL_MiddleEast for Iran, Yemen, Israel; GPR_OIL_Russia for Ukraine and the eastern flank; GPR_OIL_Venezuela for the Americas) | AI-GPR daily; public 7 days later |
| G5 | G1 to G4 together | |

   The theatre-to-country and theatre-to-pair maps are fixed in `warwatch/predstudy.py` (`COUNTRIES`, `PAIRS`) before any run.

   **Test.** The timing study's runner (`timingstudy.Study`) unchanged: 161-plus events, the 13 theatres, test years 2021 to 2026 fitted on earlier years only with the 30-day embargo, ridge strength chosen by out-of-sample Brier, the nested shrink, the three gates, 2,000 circular shifts. **Pass:** all three gates, with the shuffled-timing p below 0.05 / 5 = 0.01 (five tries). A candidate that passes is a lead for the forward record, not a change to the live model.

4. **Do crowd forecasts time events?** Polymarket daily prices for markets that name a theatre and a military action (`fetch.py polymarket`): for each event from 2024 on in a theatre with a market open the day before, the 7-day change in the market's log-odds before the event against the same change on calm days of the same markets. Description only: markets exist for few theatres and few years, so no pass rule is set.
5. **Do Crisis Group's monthly conflict-risk alerts time events?** If the Wayback pull recovers the CrisisWatch lists: for each theatre-month, alert (or deteriorated) against an event in that theatre in that month, as hit rate against false-alarm rate with an exact binomial test, 2018 on. Pass: hit rate above the calm-month alert rate with p < 0.05 on events from 2021 on.

## What would change the recommendations

- A G candidate passes: add it to the shadow models' inputs and let the forward record decide.
- The power calculation shows the gates cannot detect a plausible signal within a few years: the recommendations shift from adding inputs to adding labels (more, denser, consistently coded events) and to fixing the forward gates.
