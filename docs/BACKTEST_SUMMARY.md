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
