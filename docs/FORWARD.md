# Forward record

Every day the live build appends its probabilities for all theatres to `forward/log.csv` before any outcome is known. Each row carries the hash of the row before it, so a later edit anywhere breaks the chain from that row on; `python3 warwatch/forward_score.py` checks it. This report scores the forecasts that have matured: made at least 30 days before `warwatch/data/events_through.txt` (2026-09-30), outside the 30 days after an event.

Chain: **intact**, 0 rows.

Matured forecasts so far: 0. Too few to score; the first report with numbers needs about a quarter of daily forecasts.

