# Wider GDELT event types: test plan, fixed before any day is read

Committed 2026-10-09 with `backfill/sources_gdelt.py`, before the back-fill ran.

**Why this source.** POLECAT, the event data the research proposal named, is paid. GDELT 1.0 is free, daily since 2013 and already read by the live build, which keeps only four root codes counted by where events happen. This adds the parts of GDELT that come closest to what POLECAT offers: specific escalation codes, the hostility of what is happening (QuadClass, Goldstein), and events between the two sides of each theatre (dyads), rather than everything that happens on their soil.

**Raw counts.** Per theatre and day, from each day's file, the columns listed in `backfill/sources_gdelt.py`. The two sides of each theatre are fixed there (for example Russia and Belarus against Ukraine; China against Taiwan; for Libya and Sudan, two actors of the country, one armed).

**Eight families,** each a daily series per theatre:

| Family | Series | Warning direction |
|---|---|---|
| `gw_milthreat` | threats of military force (CAMEO 138x) per 1,000 located events | up |
| `gw_mobilise` | alert and mobilisation (152, 153, 154) per 1,000 located events | up |
| `gw_coerce` | reduce relations and coerce (roots 16, 17) per 1,000 located events | up |
| `gw_material` | material conflict (QuadClass 4) per 1,000 located events | up |
| `gw_goldstein` | mean Goldstein score of located events | down |
| `gw_dyadhostile` | conflict (QuadClass 3 or 4) per 1,000 dyad events | up |
| `gw_dyadforce` | dyad force events (138x, root 15, root 17), count | up |
| `gw_dyadgoldstein` | mean Goldstein score of dyad events | down |

Shares and means need at least 50 located events, or 10 dyad events, that day; other days are missing.

**Scoring and test.** Exactly as for Wikipedia (`docs/WIKISTUDY_PLAN.md`): each series scored day by day as the live build scores a daily count (`stats.score_series`), a day's file public the next day, then the highest z in the 30 days before each event (161 listed, merged within 30 days, from 2019) against calm 30-day windows of the same theatre.

**Pass rule, per family.** All three:
1. On the 83 added events, the hit rate at z >= 2 beats the calm false-alarm rate with p < 0.00625 (0.05 split over the eight families).
2. On the 78 original events, the same with p < 0.10.
3. AUC of the 30-day maximum above 0.55 on both halves.

A family that passes goes into the feature study as a candidate and must pass that study's rule on the added events before it reaches the model or the page. A family that fails is recorded as failed; codes, sides, minimum counts, windows and cut-offs are not changed after the data is seen.
