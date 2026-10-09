# Senkaku vessel counts against past events

Written by `warwatch/sourcestudy.py senkaku` to the plan fixed before the data was read ([SENKAKU_PLAN.md](SENKAKU_PLAN.md)). Daily China Coast Guard vessels around the Senkaku Islands (Japan Coast Guard), parsed by `backfill/senkaku_parse.py` and checked against each month's printed totals, tested against the Taiwan and South China Sea events. Pass rule: added events p < 0.025, original events p < 0.10, AUC above 0.55 on both.

Hit = z reached 2 in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.

| Family | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| senkaku_contig | 156 | 8% | 8 | 12% | 0.473 | 0.37 | 8 | 0% | 1.000 | 0.59 | no |
| senkaku_terr | 156 | 52% | 8 | 75% | 0.171 | 0.72 | 8 | 12% | 0.997 | 0.30 | no |

## Events where the series reached z 2 or more in the 30 days before

| Family | Theatre | Date | Event | Max z | List |
|---|---|---|---|---:|---|
| senkaku_contig | scs | 2024-06-17 | Second Thomas Shoal boarding | 2.0 | original |
| senkaku_terr | taiwan | 2022-08-04 | PLA drills after Pelosi | 3.7 | original |
| senkaku_terr | taiwan | 2023-04-08 | Joint Sword | 5.0 | original |
| senkaku_terr | scs | 2023-12-09 | Water cannon at Scarborough and ramming at Second Thomas Shoal | 4.2 | added |
| senkaku_terr | taiwan | 2024-05-23 | Joint Sword-2024A | 4.7 | original |
| senkaku_terr | scs | 2024-06-17 | Second Thomas Shoal boarding | 5.0 | original |
| senkaku_terr | taiwan | 2025-04-01 | Strait Thunder-2025A | 4.1 | original |
| senkaku_terr | scs | 2025-08-11 | Scarborough collision | 4.2 | original |
