# Feature lab

Written by `warwatch/featurelab.py`. The features, cuts and pass rule were fixed on 2026-10-09 before any result was seen (see the module docstring). Nothing was tuned afterward, and nothing here changes the live score or the fitted model.

Hit rate: share of buildup onsets where the feature reached its cut in the 30 days before. False-alarm rate: same in windows with no event within 30 days either side. p is an exact binomial test of the hit count against the false-alarm rate (windows overlap, so it is generous).

## Results at the pre-set cuts

| Feature | Era | Cut | Onsets scored | Hits | Hit rate | False-alarm rate | Lift | p | Theatres hit | Surprise events (hit/scored) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| any | A | 2.0 | 11 | 5 | 45% | 43% | 1.1x | 0.554 | 4 | 1/6 |
| F1 | A | 2.0 | 11 | 2 | 18% | 12% | 1.6x | 0.374 | 1 | 0/6 |
| F3 | A | 2.0 | 11 | 10 | 91% | 56% | 1.6x | 0.015 | 5 | 3/6 |
| F4 | A | 2.0 | 11 | 0 | 0% | 0% | 0.0x | 1.000 | 0 | 0/6 |
| F6 | A | 1.5 | 11 | 2 | 18% | 13% | 1.4x | 0.419 | 2 | 0/6 |
| F5 inside regime | A | 2.0 | 5 | 3 | 60% | 42% | 1.4x | 0.347 | 2 |  |
| F5 outside regime | A | 2.0 | 6 | 2 | 33% | 44% | 0.8x | 0.824 | 2 |  |
| any | B | 2.0 | 7 | 3 | 43% | 46% | 0.9x | 0.697 | 2 | 4/5 |
| F1 | B | 2.0 | 7 | 1 | 14% | 15% | 0.9x | 0.687 | 1 | 1/5 |
| F2 | B | 1.0 | 7 | 4 | 57% | 11% | 5.2x | 0.004 | 2 | 0/5 |
| F3 | B | 2.0 | 7 | 6 | 86% | 68% | 1.3x | 0.288 | 3 | 4/5 |
| F4 | B | 2.0 | 7 | 0 | 0% | 5% | 0.0x | 1.000 | 0 | 0/5 |
| F6 | B | 1.5 | 7 | 0 | 0% | 15% | 0.0x | 1.000 | 0 | 1/5 |
| F5 inside regime | B | 2.0 | 7 | 3 | 43% | 40% | 1.1x | 0.588 | 2 |  |
| F5 outside regime | B | 2.0 | 0 | 0 | 0% | 60% | 0.0x | 1.000 | 0 |  |

## F2 on every theatre with aircraft data (exploratory, cannot pass or fail)

Same feature, 13 theatres, 2024-09-16 to 2026-10-06, buildup onsets. Shown at three cuts, so read only the pre-set cut of 1.0 as the main line.

| Cut | Onsets | Hits | Hit rate | False-alarm rate | Lift | p | Theatres hit |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | 15 | 4 | 27% | 13.1% | 2.0x | 0.124 | 2 |
| 1.0 | 15 | 4 | 27% | 5.5% | 4.9x | 0.008 | 2 |
| 1.5 | 15 | 0 | 0% | 1.9% | 0.0x | 1.000 | 0 |

## Verdicts

| Feature | Passes | Detail |
|---|---|---|
| F1 | no | era A: fails; era B: fails |
| F2 | no | era B: fails |
| F3 | no | era A: fails; era B: fails |
| F4 | no | era A: fails; era B: fails |
| F6 | no | era A: fails; era B: fails |
| F5 inside regime | no | era A: fails; era B: fails |

A pass needs, in one era: 10 or more onsets scored, hit rate at least 3 times the false-alarm rate, p below 0.01, hits in at least 3 theatres, and a lift above the baseline's (for F5, above the same signal outside the regime). About 0.1 of the 12 tests would pass by chance.
