# Taiwan's daily PLA counts against past events

Written by `warwatch/sourcestudy.py pla`. Daily counts of PLA aircraft and naval vessels around Taiwan from Taiwan's Ministry of National Defense (back-filled from August 2022), scored as the live build scores a daily count and tested on the Taiwan events with the indicator study's method.

Hit = z reached 2 in the 30 days before an event; false-alarm rate = share of calm 30-day windows where it did.

| Family | Calm windows | False-alarm rate | Original events | Hit rate | p | AUC | Added events | Hit rate | p | AUC | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| pla_aircraft | 27 | 19% | 2 | 0% | 1.000 | 0.36 | 1 | 0% | 1.000 | 0.56 | no |
| pla_vessels | 28 | 29% | 2 | 0% | 1.000 | 0.26 | 1 | 100% | 0.286 | 0.96 | no |

Too few Taiwan events fall inside the archive to judge either series. The archive starts in August 2022 and the yearly baseline needs most of a year, so only the events from mid-2023 can be scored. Read the table as a description, not a test.

## Events where the series reached z 2 or more in the 30 days before

| Family | Theatre | Date | Event | Max z | List |
|---|---|---|---|---:|---|
| pla_vessels | taiwan | 2023-08-19 | PLA drills after Lai stopover in the US | 4.5 | added |
