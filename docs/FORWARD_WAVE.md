# Forward record, 7-day strike-wave shadow model (hidden from the page)

Every day the live build appends its probabilities for every theatre it covers to `forward/log_wave.csv` before any outcome is known. Each row carries the hash of the row before it, so a later edit anywhere breaks the chain from that row on; `python3 warwatch/forward_score.py` checks it. This report scores the forecasts that have matured: made at least 7 days before the newest day of its alert-wave feeds (2026-10-29), outside the 7 days after a strike wave.

Chain: **intact**, 38 rows, 2026-10-11 to 2026-10-29.

Matured forecasts so far: 12. Too few to score; the first report with numbers needs about a quarter of daily forecasts.


## Forward gates

Brier skill against the base rate above 0, and the lower end of the AUC interval (resampling theatre-months) above 0.5, read once 90 days have matured. The first of the three targets (any event in 30 days, armed force in 30 days, a strike wave in 7 days) to pass is the one to promote.

Not read yet: 12 of 90 matured days.
