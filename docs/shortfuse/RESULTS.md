# Short-fuse study: results

Written 2026-10-17 by `shortfuse.py` (this folder) to the plan in [PLAN.md](PLAN.md), fixed before the run. Numbers are from `results.json`.
The study only reads the repo. The live index it led to is [ACTIVITY.md](../ACTIVITY.md).

## Bottom line

- **Nothing passes.** No candidate is on before events much more often than in calm weeks on both the original and the added events. The bar was p < 0.0033 (0.05 split over 15 tests).
- **Nothing is even "close".** "Close" means p < 0.05 on both event sets. Every candidate that clears one set fails the other.
- **What comes closest is the additive short-fuse index.** Its weights were set on the original events only. On the added events, which it never saw, it was on before 23% of them (16 of 71). It was on in 15% of calm weeks. p = 0.071. That is a 1.5x lift, and it is not proven.
- **Base watch does not carry a 7-day signal.** A base went out or in before 14% of event onsets and in 13% of calm weeks (p 0.45). The 14-day test it passed earlier does not hold here, where the window is 7 days and only onsets count.
- **The other satellite signals fail too.** Unusual fires were on before 10% of onsets against 11% of calm weeks. The energy-site version was worse (5% against 8%). SAR ship counts never fired before an event. Requiring a base move alongside an ADS-B tanker or lift surge left 1 hit in 39 events.
- **The scores sit high but do not climb.** Before an event, the index averages about 3.0–3.8 and calm days average 1.6. The level is flat from 14 days out to the event day, so it marks a hot theatre, not an attack a few days away. Within-theatre AUC is 0.55 at best, the same ceiling the timing study hit.
- **Power is the main limit for the newest feeds.** ADS-B covers September 2024 on: 41 events, only 14 of them added. Base watch covers 2022 on: 88 events. adsb_fighter fired before 2 of 27 original events against 0.6% of calm weeks. That is the biggest lift in the study, and 0 of 14 added events.

## How it was tested (short)

- A day is scored with data up to the day before. The target is an event onset in the same theatre within the next 7 days.
- An event counts as an onset only if the theatre had no event in the 30 days before it.
- An event is a hit if the signal was on on any of the 7 days before it.
- A calm week is any 7-day block with no event in the theatre from 30 days before to 30 days after. A calm week is a false alarm if the signal was on on any of its days.
- Single feeds fire at z >= 2 (the 7-day mean against its own 150-day normal, as in `leadstudy.py`). Base watch fires when a base is out or in, using `basestudy.py`'s rule. The tells use `tells.py`'s own rules.
- Iran also reads the Iraq and Gulf boxes. Israel also reads Lebanon and Syria.
- p is a one-sided Fisher exact test, events against calm weeks, run on original and added events separately.

## All candidates

Sorted by pooled p. The pooled column mixes the two event sets and is not part of the pass rule. For the index, the original events are in-sample, because they set its weights.

| Candidate | Span | Theatres | Calm blocks | False-alarm rate | Original: hits / n (rate) | p | Added: hits / n (rate) | p | Pooled lift | Pooled p | Within-theatre AUC | Verdict |
|---|---|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---|
| index | 2014-09 to 2026-10 | 13 | 4592 | 15.3% | 18 / 57 (32%) | 0.002 (in-sample) | 16 / 71 (23%) | 0.071 | 1.7x | 0.001 | 0.55 | fail |
| wiki | 2018-07 to 2026-10 | 13 | 4421 | 7.8% | 10 / 57 (18%) | 0.012 | 7 / 68 (10%) | 0.278 | 1.8x | 0.019 | 0.53 | fail |
| adsb_fighter | 2024-09 to 2026-10 | 13 | 997 | 0.6% | 2 / 27 (7%) | 0.017 | 0 / 14 (0%) | 1.000 | 8.1x | 0.037 | 0.49 | fail |
| conv2 | 2018-07 to 2026-10 | 13 | 4444 | 3.5% | 1 / 57 (2%) | 0.868 | 7 / 68 (10%) | 0.010 | 1.8x | 0.077 | 0.52 | fail |
| tells | 2014-09 to 2026-10 | 13 | 4227 | 6.2% | 5 / 55 (9%) | 0.262 | 7 / 67 (10%) | 0.127 | 1.6x | 0.084 | n/a | fail |
| nga | 2018-07 to 2024-05 | 13 | 3219 | 7.5% | 1 / 23 (4%) | 0.834 | 7 / 51 (14%) | 0.089 | 1.4x | 0.196 | 0.48 | fail |
| adsb_tanker | 2024-09 to 2026-10 | 13 | 997 | 2.6% | 1 / 27 (4%) | 0.519 | 1 / 14 (7%) | 0.317 | 1.9x | 0.304 | 0.46 | fail |
| base | 2022-01 to 2026-10 | 12 | 2095 | 12.7% | 6 / 45 (13%) | 0.518 | 6 / 43 (14%) | 0.472 | 1.1x | 0.447 | 0.48 | fail |
| gdelt_accel | 2018-07 to 2026-10 | 12 | 4013 | 3.0% | 3 / 54 (6%) | 0.220 | 1 / 65 (2%) | 0.859 | 1.1x | 0.476 | 0.52 | fail |
| firms_anom | 2018-07 to 2026-01 | 7 | 1931 | 11.0% | 3 / 34 (9%) | 0.740 | 6 / 52 (12%) | 0.521 | 0.9x | 0.618 | 0.49 | fail |
| sat_air | 2024-09 to 2026-10 | 12 | 923 | 2.8% | 1 / 26 (4%) | 0.533 | 0 / 13 (0%) | 1.000 | 0.9x | 0.678 | 0.48 | fail |
| fire_site | 2018-07 to 2026-01 | 7 | 1931 | 7.6% | 2 / 34 (6%) | 0.740 | 2 / 52 (4%) | 0.911 | 0.6x | 0.895 | 0.49 | fail |
| adsb_lift | 2024-09 to 2026-10 | 13 | 997 | 10.9% | 2 / 27 (7%) | 0.811 | 0 / 14 (0%) | 1.000 | 0.4x | 0.946 | 0.44 | fail |
| sar | 2018-07 to 2026-10 | 8 | 2546 | 0.8% | 0 / 43 (0%) | 1.000 | 0 / 52 (0%) | 1.000 | 0.0x | 1.000 | 0.50 | fail |
| conv3 | 2018-07 to 2026-10 | 13 | 4225 | 0.2% | 0 / 57 (0%) | 1.000 | 0 / 66 (0%) | 1.000 | 0.0x | 1.000 | 0.52 | fail |

Notes:
- **conv2** (2 or more of 6 domains on) wins on the added events (p 0.010) but fails on the original events (1 of 57). conv3 never fired before any event.
- **wiki** is the reverse: strong on the original events, weak on the added ones. That matches the 30-day result in docs/WIKISTUDY.md.
- **tells** hits come mostly from Israel's strike-wave tell, which reads alert counts in a war already under way.

## The short-fuse index

The weights are ln(lift) on the original events. Families with a lift of 1 or less get 0.

| Family | Weight |
|---|---:|
| adsb_fighter | 2.51 |
| wiki | 0.82 |
| gdelt_accel | 0.63 |
| tells | 0.38 |
| adsb_tanker | 0.35 |
| base | 0.05 |
| firms_anom, adsb_lift, nga, sar | 0 |

The cut is the lowest index value that keeps calm-week false alarms at 20% or less. It came out at 1.04, the smallest non-zero value.
So the fitted index is really an OR: it is "on" when any family with a weight above 0 is on. The weights only rank the days.
On the added events it scores 23% hits against 15% false alarms, p 0.071. That fails the plan's bar of 0.0033 and the looser 0.05.

## Does it climb? Mean score by day before the event

Day 0 is the event day. "Calm days" means no event in the theatre within 37 days either side.
The top 3 candidates by pooled p are shown, plus conv2.

| Candidate (score) | -14 | -13 | -12 | -11 | -10 | -9 | -8 | -7 | -6 | -5 | -4 | -3 | -2 | -1 | 0 | calm days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| index (index value 0-100) | 3.78 | 3.72 | 3.47 | 3.32 | 3.24 | 3.19 | 3.01 | 3.27 | 2.96 | 3.00 | 3.17 | 3.31 | 3.70 | 3.50 | 3.78 | 1.60 |
| wiki (max z, trailing 7 days) | 0.86 | 0.88 | 0.92 | 0.93 | 1.00 | 1.08 | 1.13 | 1.19 | 1.25 | 1.22 | 1.15 | 1.13 | 1.12 | 1.14 | 1.20 | 0.32 |
| adsb_fighter (max z, trailing 7 days) | 0.06 | 0.07 | 0.07 | 0.08 | 0.08 | 0.08 | 0.08 | 0.08 | 0.09 | 0.09 | 0.09 | 0.10 | 0.12 | 0.11 | 0.10 | 0.05 |
| conv2 (domains on, 0-6) | 0.42 | 0.41 | 0.41 | 0.38 | 0.38 | 0.38 | 0.36 | 0.38 | 0.36 | 0.34 | 0.34 | 0.34 | 0.34 | 0.34 | 0.37 | 0.23 |

Share of events with the signal on, by day:

| Candidate | -14 | -13 | -12 | -11 | -10 | -9 | -8 | -7 | -6 | -5 | -4 | -3 | -2 | -1 | 0 | calm days |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| index | 22% | 21% | 20% | 19% | 20% | 20% | 18% | 20% | 19% | 20% | 21% | 22% | 22% | 20% | 22% | 11% |
| wiki | 14% | 14% | 12% | 11% | 10% | 10% | 10% | 12% | 10% | 10% | 10% | 11% | 11% | 10% | 10% | 6% |
| adsb_fighter | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 5% | 5% | 5% | 0% |
| conv2 | 6% | 6% | 5% | 4% | 4% | 5% | 3% | 3% | 3% | 4% | 5% | 4% | 5% | 5% | 6% | 2% |

Before events, every score runs at about twice its calm level. It is already that high 14 days out and stays flat.
Wikipedia views rise slowly from -14 to -6 and then level off. The fighter count ticks up only over the last 2 days, on 2 events.
None of them shows the 1-to-7-day rise the metric needs.

## Caveats

- **Power.** ADS-B has 41 events (14 added) and base watch 88. One more or one fewer hit moves p a lot. Take a true 2x lift (20% hits against 10% calm): detecting it at p < 0.0033 with 80% power needs about 130 events per set. The biggest set here is 71.
- **Overlap.** One scoring week reads 13 days of data, and the tells reuse feeds that are also tested alone (tankers, NGA). The domains are not fully independent either: wiki and GDELT both measure attention.
- **Multiple testing.** 15 tests at 0.05 would give about 0.75 false passes. The two nominal p-values below 0.05 that fail on the other event set fit that.
- **Definitions differ from earlier studies.** The z rule here is `leadstudy.py`'s, which is stricter than `stats.score_series`. So firms_anom's false-alarm rate here (11%) is far from FIREANOM.md's 51%. Base watch passed with a 14-day window and every event counted. Here the window is 7 days and only onsets count.
- **The event list was not built blind** to these feeds. Some hits are attention to a crisis already in the news (Pelosi, Russia–Belarus drills).

## What would most likely change the answer

- More ADS-B history and more events since 2024. The fighter signal had the largest lift and needs about 3x more events to be judged.
- Base watch with fewer noisy sites. A handful of bases cause most calm-week firings (BASEWATCH_STUDY.md: Tel Nof, Sevastopol, Nur Khan), and their noise hides any 7-day signal.
- Feeds tied to a decision to strike, which this archive barely holds: NOTAM and airspace closures, airline cancellations, and civil-defence notices. Their tells have no history yet.

## Files

- `PLAN.md`: the plan and its amendments
- `shortfuse.py`: the study (`python3 docs/shortfuse/shortfuse.py`; about 20 s)
- `results.json`: every candidate's span, events scored, hits, rates, lift, p, verdict, hit events, and the -14..0 profiles
