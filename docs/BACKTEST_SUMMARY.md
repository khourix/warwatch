# How WarWatch performed against past events: results in plain words

Written 2026-10-08 from the generated reports: [BACKTEST_EVENTS.md](BACKTEST_EVENTS.md) (event by event, out of sample), [BACKTEST_FASTFEEDS.md](BACKTEST_FASTFEEDS.md) (the back-filled aircraft, fire, ship and radar feeds) and [MODEL.md](MODEL.md) (the gates). Re-run with `python3 warwatch/eventstudy.py` and `python3 warwatch/fastfeeds.py`; both also run in the monthly refit, so the numbers here are a snapshot, the reports stay current.

## What was tested

The published 30-day probability per theatre, as the live page would have shown it, replayed day by day from 2021 to August 2026. Each year is scored by weights fitted on earlier years only, so nothing is judged on data it was fitted on. Targets are the 78 events in [EVENTS.md](EVENTS.md); 60 of the 65 from 2021 on can be scored (5 sit inside the 30-day aftermath of an earlier event in the same theatre). "Up" means the probability was at or above Watch (5%), Elevated (10%) or Critical (25%) on the day before the event.

## Result

- **It is better than a coin flip, but only modestly, and mostly in the Middle East.** AUC 0.63 (interval 0.55 to 0.71); on its top 10% of days an event follows within 30 days about twice as often as on an average day (12.7% against 6.0%).
- **Lead time.** Watch was up the day before 18 of 60 events, Elevated 6 of 60, Critical 1 of 60. Watch fired at some point in the 30 days before 25 of 60. When a line was up the median lead was 30 days or more, but in most of those cases the line had simply been up for a long time (Iran, Israel).
- **Much of that is recent history, not indicators.** A model with only theatre base rates and recent-event history reaches Watch before 13 of the 18; the indicators added five (the Russian invasion on the eastern flank, the Hodeidah strike, the Libya oil shutdown, the Beirut pager attacks, the US campaign on the Houthis), none at Elevated, and the one Critical (the February 2026 war on Iran). Outside Iran and Israel the full model's AUC is 0.59 against 0.51 for history alone, and its Brier skill against the base rate is slightly negative (-0.005).
- **False alarms.** Watch is up on 16.3% of calm days and Elevated on 6.0%. Counted as alert episodes: Watch 88 episodes, 14 followed by an event (16%); Elevated 48, 9 hits (19%); Critical 15, 4 hits (27%). Critical rises about as often as its stated 25% or more would suggest; Watch and Elevated are noisy.
- **Notable misses.** Nothing moved before Hamas's 7 October attack (2.6% the day before), the 2022 invasion of Ukraine itself (3.5%, middling percentile), the Pelosi drills, the 2021 Gaza war, the first Red Sea attacks or any Korean launch. Surprises and build-ups were flagged at similar rates (33% and 28% at Watch), so the build-up label is not what separates hits from misses.
- **Back-filled fast feeds.** None of the 15 feed families (military aircraft by class, fires, hazard warnings, vessel counts, radar ships, PLA counts) clears the model's own bar: best AUC 0.53 (radar ship counts) and 0.52 (fighter counts), intervals include 0.5. ADS-B only goes back to March 2024, so power is low; this says the feeds are not proven, not that they are useless.

## Calibration

- The published probabilities are too low on average: mean 2.5% in the Normal band against 6.3% of days followed by an event in 2023 to 2026, because event frequency rose (1.6% of days in 2021, 10.5% in 2024, 11.6% in 2025) faster than base rates fitted on earlier years. The Elevated band (mean 14.8%) saw 9.2% events, less than Watch (11.0%), so those two bands are not cleanly ordered.
- Recalibrating on earlier years does **not** help out of sample (Brier skill +0.018 published, +0.014 with a two-parameter fix, -0.016 with a level shift), because the shift is a regime change, not a stable bias.

## What this suggests

1. Leave the weights alone. The data does not support tuning them: no feed earns weight, and the one clear gain is the conflict-history term.
2. Read Watch and Elevated as one tier ("something is up"), and Critical as the real alarm. Merging the two lower bands, or relabelling them, is a presentation change that needs no model change; your call.
3. Make base rates follow recent frequency (for example a trailing three years) and test that nested before shipping; this is the one calibration fix the evidence points at.
4. Do not expect advance warning of surprise onsets from public data alone. The tests show this on Ukraine 2022 and Israel 2023.
5. The clean test is the forward log (`forward/log.csv`), which has no look-ahead; revisit feeds and bands when it has a year.

## Caveats

- The event list was built for the methodology review, and the ridge strength was chosen on the same test years, so the gates are a little optimistic.
- 60 scorable events in 13 theatres, with 18 in Iran and Israel; per-theatre numbers are small and wide.
- Dates are the first day an event qualified; a different date convention would shift lead times by days.

## Calibration proposal: which indicators earn weight

Full tables: [CALIBRATION.md](CALIBRATION.md). Two questions were asked of the 2018 to 2026 events: which indicators rose before them, and would a different weighting have forecast better out of sample.

**Which indicators reliably rose before events** (within-theatre AUC interval above 0.5, and above 0.5 in both 2019 to 2022 and 2023 to 2026): the GDELT news-tone families (pre-force share 0.61, threat 0.60 to 0.61, posture 0.56), VIX (0.57), and the Taiwan and India equity indices (0.62 and 0.76, few events). Their lift is real but small: AUC 0.55 to 0.62, nothing like a clean signal. Korea's equity index and the won rose before the Korean events (AUC 0.81 and 0.78) but on three events, too few to judge. Everything else, including every back-filled fast feed, shows no stable rise.

**Where the model's weight is ahead of the evidence** (weight of 1 or more, interval includes 0.5): tanker equities (2.18), container equities (2.05), EU gas (1.96), US armor awards (1.44), EU truck exports (1.37, AUC 0.42, below chance), ACLED demonstrations (1.33), US individual-equipment awards (1.05) and US ammunition NAICS awards (1.04). The news-tone families that do show stable evidence carry 0.4 to 0.6.

**But re-weighting by hand does not beat the fit.** Seven schemes were compared in the model's own rolling-origin test. The published ridge is best on Brier skill (+0.0148). Keeping only the families that look good in training (+0.0047), one coefficient per domain (+0.0051), an AUC-weighted index (+0.0110) and adding the fast feeds (+0.0010) all do worse. Shrinking thinly-supported families harder (+0.0137) is level on skill and slightly better outside Iran and Israel (-0.0027 against -0.0051), within noise of the published model.

**Proposal**
1. Keep the weights as fitted; do not hand-edit them. No scheme tested improves on them out of sample.
2. Treat the eight above as a watch-list, not a verdict: when the forward log (`forward/log.csv`) has a year, test whether they pull their weight there. If the support-weighted ridge is level or better on the forward record, switch to it (it caps exactly these).
3. Do not promote any fast feed. None clears the bar alone (BACKTEST_FASTFEEDS.md) and adding them lowers skill (+0.0010). Revisit when ADS-B has two or more years and more events.
4. The one calibration change the evidence points at is base rates that follow recent event frequency (see Calibration above), not family weights; that needs its own nested test before shipping.

## Improvement tests: how to catch more of the next events

Tables and method: [IMPROVEMENTS.md](IMPROVEMENTS.md). Everything below is out of sample and none of it is shipped.

1. **Nothing tried on the model's inputs helps reliably.** Extra history terms (events 30 to 90 days ago, in linked theatres such as Iran-Israel-Yemen, anywhere else), recency-weighted training and a three-year base rate each move Brier skill by less than a year-to-year swing, and none beats the published model on skill and AUC together. The model is near what these 78 events and public indicators can give.
2. **Alerting on the rise in probability looks better and is not.** It flags 19 of 51 events against 14 at the same share of calm days, but raises 181 separate false alarms against 55. Taking the highest of the last 7 days of the published probability catches the same events with 43 false episodes instead of 55. That is the one small, safe change, and it is now in the live model (`model.recent_max`, `ALERT_DAYS = 7`): a theatre's level is set from the highest probability of the last 7 logged days and today's; the displayed probability and the forward record still hold the day's own value, so scoring is unaffected.
3. **Training on armed-force events only (onset, strike, maritime) helps modestly.** Judged on those events it flags 16 of 39 at 10% false alarms against 13 of 39, AUC 0.667 against 0.658, lift 3.1x against 2.6x, and is better in 5 of 6 years (not 2022). Drills and "other" events are close to unforecastable from these data and add noise to the target. Three events is within noise, so treat it as the leading candidate, not a result.

What would actually raise capture is new information, not tuning: leading indicators with real history before 2024, and more labelled events. My recommended order: (a) adopt the 7-day maximum for alerts; (b) run the armed-force target in parallel with the current model and score both on the forward log; (c) keep adding events as they happen.
