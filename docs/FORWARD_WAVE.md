# Forward record, 7-day strike-wave shadow model (hidden from the page)

Every day the live build appends its probabilities for every theatre it covers to `forward/log_wave.csv` before any outcome is known. Each row carries the hash of the row before it, so a later edit anywhere breaks the chain from that row on; `python3 warwatch/forward_score.py` checks it. This report scores the forecasts that have matured: made at least 7 days before the newest day of its alert-wave feeds (2026-11-05), outside the 7 days after a strike wave.

Chain: **intact**, 44 rows, 2026-10-11 to 2026-11-05.

Matured forecasts so far: 19. Too few to score; the first report with numbers needs about a quarter of daily forecasts.


## Forward gates

Read once, when 365 days have matured: Brier skill against the base rate above 0, the lower end of the AUC interval (resampling theatre-months) above 0.5, and the AUC beating a shuffled-timing control (each theatre's probabilities shifted in time against its outcomes, 1,000 shifts) at p < 0.05 / 3 = 0.0167, one share for each of the three targets (any event in 30 days, armed force in 30 days, a strike wave in 7 days). The first two alone pass as often for a forecast with its timing scrambled as for the real one, so the third is what tests timing. From 90 matured days the same numbers are shown as an interim description; only the read at 365 days can promote a target.

Not read yet: 19 of 90 matured days for the first interim report, 365 for the read.
