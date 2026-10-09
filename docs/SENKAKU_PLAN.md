# Senkaku vessel counts: test plan, fixed before any count is read

Committed 2026-10-09 with `backfill/sources_senkaku.py`, before the back-fill ran.

**Why this source.** The Japan Coast Guard publishes, every day since September 2012, how many China Coast Guard vessels were in the contiguous zone around the Senkaku Islands and how many entered the territorial sea. It is a direct, official count of Chinese maritime pressure, free, with fourteen years of history. No current indicator measures it.

**Series.** `senkaku_contig`: vessels in the contiguous zone per day. `senkaku_terr`: vessels that entered the territorial sea per day. Read from the monthly PDFs as published; the first step only keeps their text so the table layout can be checked by eye before parsing. The parser may be fixed to read the table correctly; nothing about the test below changes.

**Theatres.** China's maritime pressure is one campaign, so each series is tested against both the Taiwan and the South China Sea events (Taiwan alone has one added event since 2019).

**Scoring and test.** As for Wikipedia (`docs/WIKISTUDY_PLAN.md`): scored day by day as the live build scores a daily count (`stats.score_series`), a day's count public the next day, then the highest z in the 30 days before each event against calm 30-day windows of the same theatre.

**Pass rule, per series.** On the added events, hit rate at z >= 2 beats the calm false-alarm rate with p < 0.025 (0.05 split over the two series); on the original events p < 0.10; AUC above 0.55 on both halves. A series that passes goes into the feature study as a candidate. One that fails is recorded as failed and not tuned.

## Result (2026-10-09)

Neither series passes ([SENKAKU.md](SENKAKU.md)). 168 of the 170 monthly PDFs parse to exactly the totals printed on them (`backfill/senkaku_parse.py`); September 2012 (a part month) and August 2016 (the PDF's own day rows do not add up to its total) are left out. Vessels in the contiguous zone almost never reach z 2 before an event (1 of 16). Territorial-sea entries reach it before 6 of the 8 original events but also in half of all calm windows, because the count is zero most days and any entry reads as a jump; on the added events they do worse than calm periods (AUC 0.30). Recorded as failed.
