# Base watch feasibility test: plan, fixed before any scene is read

Committed 2026-10-15 with `warwatch/basespike.py`, before it ran ([BASEWATCH_PLAN.md](BASEWATCH_PLAN.md), stage B0).

**Question.** Can free 10 m imagery see the base changes that came before past strikes? If not, the base layer only shows
images for people to look at, and nothing is automated (no alerts, no tell, no series).

**Cases and windows.** Each window starts early enough that every orbit has 8 earlier scenes before the case date. In
2024–2025 only Sentinel-1A flew, so a given orbit passed about every 12 days.

| Case | Site part | Window | Case date | Expected | Counts for the rule |
|---|---|---|---|---|---|
| Al Udeid: aircraft dispersed before Iran's strike of 23 Jun 2025 | aprons | 2024-12-01 to 2025-07-15 | 2025-06-19 | down | yes |
| NSA Bahrain: US ships left port before the strikes of 28 Feb 2026 | piers and harbour | 2025-07-01 to 2026-03-15 | 2026-02-26 | down | yes |
| Diego Garcia: B-2 bombers deployed (reported from late March 2025) | aprons, **optical only** (no Sentinel-1 coverage) | 2024-12-01 to 2025-05-31 | 2025-03-25 | up | yes |
| Olenya: bombers present, then struck on 1 Jun 2025 | aprons | 2024-12-01 to 2025-07-15 | 2025-06-01 | down | no (damage, not warning) |

The case dates come from WarWatch's own records (`tells.py`) and from reports of the day. They are the dates the change
was reported, not a measured onset.

**Radar metrics** (Sentinel-1 RTC, VV, native 10 m, inside the OSM apron or harbour shapes in `warwatch/data/bases.json`;
piers are widened by 60 m):
- `bright_m2`: the area of pixels with VV ≥ T dB;
- `blobs`: connected groups of 3 to 150 such pixels;
- T in {−6, −3, 0, +3} dB.
That makes eight metric–threshold pairs. A scene is scored only against earlier scenes of the **same orbit** (pass
direction plus relative orbit): z = (value − median of the previous 8 to 20) / (1.4826 × MAD), with MAD floored at 5%
of the median (and at 1 for counts).

**Optical metric** (Sentinel-2 L2A, scenes at least 90% clear over the aprons): `objects` = apron pixels whose red band
differs from the apron median by more than 0.06 reflectance. Scored against the previous 8 to 20 clear scenes, the same
way. True-colour chips at the clear dates nearest before and after each case.

**Go rule.** One radar pair (metric, T) is chosen for all radar cases: the pair that meets the rule in the most leading
cases, ties broken by the lower false-alarm rate. A case is caught when a scene within ±7 days of its date has z ≥ 2.5
in the expected direction. The false-alarm rate is the share of all other scored scenes in the case windows with
|z| ≥ 2.5. Diego Garcia uses the optical metric.

**GO** if at least 2 of the 3 leading cases are caught **and** the false-alarm rate of the chosen pair is 10% or less.
Otherwise **NO-GO**. Either way the result is written to `docs/BASESPIKE.md`, and the chosen pair (or none) is frozen
in `warwatch/basewatch.py`.
