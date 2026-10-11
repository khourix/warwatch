# Forward record

Every day the live build appends its probabilities for every theatre it covers to `forward/log.csv` before any outcome is known. Each row carries the hash of the row before it, so a later edit anywhere breaks the chain from that row on; `python3 warwatch/forward_score.py` checks it. This report scores the forecasts that have matured: made at least 30 days before `warwatch/data/events_through.txt` (2026-09-30), outside the 30 days after an event.

Chain: **intact**, 72 rows, 2026-10-07 to 2026-10-11.

Matured forecasts so far: 0. Too few to score; the first report with numbers needs about a quarter of daily forecasts.


## Forward gates

Brier skill against the base rate above 0, and the lower end of the AUC interval (resampling theatre-months) above 0.5, read once 90 days have matured. The first of the three targets (any event in 30 days, armed force in 30 days, a strike wave in 7 days) to pass is the one to promote.

Not read yet: 0 of 90 matured days.
