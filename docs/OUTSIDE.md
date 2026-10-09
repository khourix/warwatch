# Outside forecasts against past events

Written by `warwatch/outsidestudy.py` to the plan fixed before the data was read ([OUTSIDE_PLAN.md](OUTSIDE_PLAN.md)). ConflictForecast: the full-model probability of armed conflict, or of any violence, in the next 3 months, for each theatre the highest among its countries, public from the first day of the month after its vintage. VIEWS: the probability of 25 or more state-based deaths in the first forecast month, same lag.

## Test B: the probability itself, the day before each event, against calm days

Pass: AUC of 0.65 or more on the added events, with the bootstrap 95% interval above 0.5.

| Source | From | Calm days | Mean on calm days | Original events | Mean before | AUC (95% interval) | Added events | Mean before | AUC (95% interval) | Passes |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| cf_armedconf_3 | 2021-08-01 | 638 | 0.41 | 46 | 0.48 | 0.55 (0.45 to 0.64) | 48 | 0.40 | 0.50 (0.42 to 0.58) | no |
| cf_anyviolence_3 | 2021-08-01 | 638 | 0.64 | 46 | 0.68 | 0.58 (0.48 to 0.67) | 48 | 0.63 | 0.47 (0.39 to 0.55) | no |
| views | 2023-05-01 | 395 | 0.46 | 38 | 0.56 | 0.57 (0.49 to 0.65) | 32 | 0.49 | 0.53 (0.43 to 0.62) | no |

## Test A: does the forecast rise before events?

Each monthly series scored as the live build scores a monthly series (needs 40 months, so scores start late), then the indicator study's test. Pass: added events p < 0.05, original events p < 0.10, AUC above 0.55 on both.

| Source | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| cf_armedconf_3 | 179 | 34% | 16 | 56% | 0.052 | 0.60 | 10 | 50% | 0.217 | 0.53 | no |
| cf_anyviolence_3 | 179 | 35% | 16 | 62% | 0.024 | 0.66 | 10 | 60% | 0.097 | 0.57 | no |
| views | 0 | n/a | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a | no |

## Benchmark against our 30-day model (description, not a test)

On the theatre-days our model was tested out of sample (2021 on) where the outside forecast exists: AUC of each against the same label (an event in the theatre within 30 days), with intervals from resampling theatre-years. "Both" adds the two, each scaled by its spread.

| Source | Days | Days before an event | Our model | Outside forecast | Both |
|---|---:|---:|---|---|---:|
| cf_armedconf_3 | 22382 | 1488 | 0.59 (0.51 to 0.68) | 0.55 (0.45 to 0.64) | 0.57 |
| cf_anyviolence_3 | 22382 | 1488 | 0.59 (0.51 to 0.68) | 0.56 (0.47 to 0.65) | 0.59 |
| views | 14437 | 1158 | 0.60 (0.50 to 0.69) | 0.58 (0.48 to 0.67) | 0.61 |
