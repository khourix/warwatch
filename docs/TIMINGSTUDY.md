# Timing study: can the 30-day chance be validated on past events?

Written by `warwatch/timingstudy.py` to the plan fixed before any candidate was run ([TIMINGSTUDY_PLAN.md](TIMINGSTUDY_PLAN.md)). 161 events, the 13 theatres, test years 2021 to 2026, each fitted on earlier years only. The three gates are unchanged; with 13 tries a candidate counts as validated only when its shuffled-timing p is below 0.05 / 13 = 0.0038 (2,000 shifts).

## Result

**No candidate is validated.** None passes even at the uncorrected 0.05 line.

| Id | Change | Families | Brier skill | AUC (95% interval) | Within-theatre AUC | Shuffle p (95th pct of shifted AUC) | Events flagged at 10% | False alarms per hit | AUC, original / added events | Brier vs baseline (p) | Validated |
|---|---|---:|---:|---|---:|---|---:|---:|---|---|---|
| base | Baseline (published model) | 75 | +0.0054 | 0.632 (0.564 to 0.696) | 0.534 | 0.1810 (0.654) | 33/98 | 1.6 | 0.67 / 0.60 | – | fails |
| D1 | Archive feeds in the fit | 85 | +0.0023 | 0.633 (0.562 to 0.699) | 0.537 | 0.1945 (0.655) | 31/98 | 2.2 | 0.66 / 0.60 | -3.1e-4 (0.79) | no |
| D2 | Newly held series | 88 | +0.0067 | 0.633 (0.564 to 0.697) | 0.538 | 0.1675 (0.653) | 34/98 | 1.4 | 0.67 / 0.60 | +1.4e-4 (0.16) | no |
| D3 | Iraq and GCC rows in training | 75 | +0.0042 | 0.619 (0.546 to 0.688) | 0.532 | 0.2855 (0.652) | 29/98 | 1.9 | 0.66 / 0.58 | -1.2e-4 (0.58) | no |
| T1 | Hot-state level (GDELT violence) | 77 | +0.0063 | 0.634 (0.567 to 0.697) | 0.536 | 0.1725 (0.655) | 33/98 | 1.7 | 0.66 / 0.61 | +0.9e-4 (0.01) | no |
| T2 | Acceleration (GDELT, 7 days against 60) | 83 | +0.0047 | 0.632 (0.564 to 0.696) | 0.534 | 0.1850 (0.654) | 33/98 | 1.6 | 0.67 / 0.60 | -0.7e-4 (0.98) | no |
| T3 | Fewer weights (own families + world tempo) | 44 | +0.0057 | 0.618 (0.547 to 0.685) | 0.507 | 0.4610 (0.660) | 26/98 | 2.2 | 0.64 / 0.60 | +0.4e-4 (0.48) | no |
| L1 | Weights trained on a 10-day target | 75 | +0.0107 | 0.630 (0.563 to 0.695) | 0.527 | 0.2710 (0.659) | 28/98 | 3.5 | 0.67 / 0.59 | +5.4e-4 (0.28) | no |
| L2 | Weights trained on a dense violence proxy | 75 | +0.0059 | 0.615 (0.542 to 0.684) | 0.486 | 0.4960 (0.659) | 29/98 | 1.6 | 0.64 / 0.59 | +0.5e-4 (0.47) | no |
| K1 | Cleaning: one-day glitches removed | 75 | +0.0058 | 0.633 (0.564 to 0.697) | 0.534 | 0.1795 (0.654) | 33/98 | 1.6 | 0.67 / 0.60 | +0.4e-4 (0.04) | no |
| K2 | Cleaning: standing drift removed | 75 | +0.0028 | 0.620 (0.554 to 0.687) | 0.517 | 0.3555 (0.655) | 27/98 | 2.8 | 0.65 / 0.59 | -2.6e-4 (0.67) | no |
| K3 | Cleaning: late data dropped | 42 | +0.0058 | 0.628 (0.557 to 0.694) | 0.523 | 0.2490 (0.658) | 28/98 | 2.2 | 0.67 / 0.59 | +0.5e-4 (0.48) | no |
| K4 | Cleaning: duplicate families merged | 72 | +0.0052 | 0.632 (0.564 to 0.696) | 0.534 | 0.1825 (0.653) | 33/98 | 1.5 | 0.66 / 0.60 | -0.2e-4 (0.98) | no |

AUC by test year, 2021 to 2026:

| Id | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| base | 0.67 | 0.61 | 0.52 | 0.68 | 0.52 | 0.89 |
| D1 | 0.67 | 0.61 | 0.52 | 0.69 | 0.51 | 0.90 |
| D2 | 0.67 | 0.62 | 0.53 | 0.68 | 0.52 | 0.89 |
| D3 | 0.67 | 0.55 | 0.55 | 0.69 | 0.50 | 0.89 |
| T1 | 0.67 | 0.62 | 0.53 | 0.68 | 0.52 | 0.89 |
| T2 | 0.67 | 0.61 | 0.52 | 0.68 | 0.52 | 0.89 |
| T3 | 0.67 | 0.56 | 0.55 | 0.68 | 0.49 | 0.92 |
| L1 | 0.69 | 0.59 | 0.54 | 0.68 | 0.52 | 0.90 |
| L2 | 0.64 | 0.53 | 0.53 | 0.68 | 0.52 | 0.90 |
| K1 | 0.66 | 0.61 | 0.53 | 0.68 | 0.52 | 0.89 |
| K2 | 0.68 | 0.57 | 0.54 | 0.68 | 0.53 | 0.88 |
| K3 | 0.70 | 0.55 | 0.55 | 0.68 | 0.51 | 0.88 |
| K4 | 0.67 | 0.61 | 0.52 | 0.68 | 0.52 | 0.89 |

Combination (C1): not run, since no candidate passed the gates at the uncorrected 0.05 line.

Baseline for reference: within-theatre AUC 0.534. The plan's check puts the pass line at a within-theatre AUC of about 0.58 to 0.63.

## What it means

- The best within-theatre AUC of any candidate is 0.538 (D2), against 0.534 for the baseline. Across all 12 candidates it moves by -0.048 to +0.004. Passing needs roughly +0.05 to +0.10.
- Adding data, reshaping it, cleaning it and training on other targets all leave the timing where it was. The held data says which theatres are risky; it does not say when. That is a limit of the information, not of how it is processed, and it agrees with the six earlier studies.
- Changes that cut the number of weights or drop inputs (T3, K3) or move the target away from the events (L2) lose timing skill: what little timing there is is spread thinly over many inputs.
- The honest routes to a validated number are the forward record (scored on days the model had not seen) and inputs that time events within days (the timing tells and the 7-day strike-wave target), whose histories are still short. Keeping the event list's "complete through" date current is what lets the 30-day forward record mature.
