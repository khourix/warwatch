# Warwatch: war early-warning dashboard (v0.2)

Internal decision support from public data only. It is not a prediction of
war and nothing here trades or contacts anyone. This file is the long-term
reference for the design; the thread it came from is linked in the PR.

Code: `warwatch/` in this repo.
Tests: `python3 warwatch/tests/test_warwatch.py` (26 pass).

## 1. What changed since the DeepSeek draft

The draft's structure holds: several independent domains, one spike is a
signal, several agreeing spikes are a warning, every alert explains itself.
Five things changed.

1. **Boots, pickups and blood are tracked, as asked.** None of them has a
   direct free feed, so each is watched through three routes: (a) US and EU
   *tenders*, which are published before awards and so lead; (b) *awards*,
   which confirm but lag; (c) *exports* of the product class to the Ukraine
   and Middle East destination sets, which show it moving toward a theatre.
   Whether these indicators actually moved before past wars is still unproven;
   the backtest in section 7 decides which survive.
2. **Lagging data is labelled and cannot masquerade as early warning.** DoD
   contract data is published about 90 days late (fpds.gov DoD data page),
   and trade statistics about two months late. A Warning or Alert with no
   fast domain firing is shown as "lagging only".
3. **Per-theatre views.** One global number hid the theatre. The dashboard
   has four tabs: supplier side (US and EU), NATO eastern flank, Ukraine,
   Middle East. Supplier-side series count in every tab.
4. **Scoring was calibrated, not assumed.** On 300 runs of pure noise the
   false-alarm rate per series is about 2 percent (monthly) and 3 percent
   (daily), checked by a unit test. A single outlier cannot fire a domain:
   a domain's score is the mean of its two strongest series.
5. **Everything is verified live or marked unverified.** Endpoints were
   probed from a GitHub runner (the build sandbox blocks data hosts).

## 2. Verified data routes (GitHub runner, 2026-10-06)

| Route | Used for | Key | Verified |
|---|---|---|---|
| USAspending `spending_over_time` | US awards by PSC or NAICS, monthly | none | yes |
| Eurostat Comext `DS-045409` (JSON-stat) | EU exports by HS code and destination, monthly | none | yes |
| TED `v3/notices/search` | EU tenders by CPV code, count per month | none | yes |
| IMF PortWatch (ArcGIS) | daily ship transits per chokepoint | none | yes |
| GDELT DOC 2.0 | daily news volume by theatre query | none, 1 request per 5 s | yes |
| Wikipedia pageviews | daily readers of chosen articles | none | yes |
| UK FCDO travel advice (GOV.UK content API) | advisory update history per country | none | yes |
| US State Dept advisories feed | advisory levels per country | none | yes |
| adsb.lol `/v2/mil` | military aircraft now, counted by theatre box | none | yes (snapshot only) |
| Polymarket gamma | crowd forecasts | none | reachable, not yet used |
| UN Comtrade public preview | annual and monthly trade | none, capped rows | reachable, not yet used |
| HDX HAPI conflict events | historical conflict counts | none | reachable, old data only |
| US Census trade (`intltrade/exports/hs`) | US exports by HS6 and partner | free key | **needs key** |
| SAM.gov opportunities | US tenders by PSC | free key | **needs key** |
| FRED | Brent, VIX | free key | **needs key** |

Dropped: AABB blood report page (404), OpenSky (returned no states from a
cloud runner), commercial AIS, customs bills of lading, dealer inventories.
No national blood-stock feed exists in the US or EU; blood is watched through
medical tenders, biologics awards, dressing and blood-fraction exports, and
reader attention.

## 3. The catalogue

56 series in seven domains (`catalog.py`; each carries a one-line reason):

- **Troop kit:** US footwear and armor awards, US and EU boot tenders, footwear
  exports to Ukraine and the Middle East (HS 6403, 640391, 640399).
- **Pickups and light trucks:** EU goods-vehicle exports (HS 8704) and US
  pickup exports (HS 870421, 870431, 870422, 870432) to the destination sets,
  US tactical vehicle awards, EU 4x4 tenders.
- **Blood and trauma:** US medical awards and tenders, biologics (NAICS 325414),
  EU medical consumable tenders, dressing and blood-fraction exports.
- **Forward infrastructure:** fencing and bridging awards and tenders.
- **Sea and air flows:** PortWatch transits (Hormuz, Bab el-Mandeb, Suez,
  Bosporus; a fall is the warning), ADS-B military and airlift counts.
- **Attention and advisories:** GDELT per theatre, Wikipedia readers, UK and
  US advisory activity.
- **Markets:** Brent and VIX.

Destination sets: Ukraine (UA); Middle East (Israel, Jordan, Lebanon, Saudi
Arabia, UAE, Kuwait, Qatar, Bahrain, Oman, Iraq); eastern flank (Poland,
Baltics, Finland, Romania). Gulf re-export hubs such as the UAE inflate
vehicle exports; the score looks at change, not level, which limits but does
not remove this.

## 4. Scoring

- **Monthly series:** log, remove the calendar-month seasonal factor (median
  over the years, leave-one-out so a point never sets its own factor), then a
  robust z (median and MAD) of the newest month against the previous 36.
  Needs 40 or more months.
- **Daily series:** latest 7-day mean against weekly means over the prior 26
  weeks. Needs 84 or more days. Snapshot sources (ADS-B, US advisory level)
  store their own history in `history/`, so they show "collecting history"
  until enough days exist.
- **Direction:** most series warn upward; ship transits warn downward; ADS-B
  counts either way. A flat history that changes scores the maximum (6).
- **Domain score:** mean of the two strongest series (a lone series is
  discounted to 70 percent).
- **Level per theatre:** Normal; Watch (one domain at 3.0 or more, or two at
  2.0 or more); Warning (two); Alert (three or more). Fewer than two
  scorable domains gives "insufficient data". The level counts agreeing
  domains and is not a probability.

## 5. Stack and cost: zero

- GitHub Actions cron every 6 hours. A public repo has no minute cap.
- Python standard library only; no database. History for snapshot sources is
  a few CSVs committed by the workflow (public data only).
- Output: one static HTML page and a JSON summary. Hosting options, all free:
  GitHub Pages (works once the repo is public) and Cloudflare Pages.
- Secrets live in the repo's Actions secrets, never in code or chat.

## 6. Accounts to open (all free)

| Secret name | Source | Unlocks |
|---|---|---|
| `CENSUS_API_KEY` | api.census.gov/data/key_signup.html | US exports of boots and pickups by country |
| `SAM_API_KEY` | sam.gov, Account Details, public API key | US tenders (leading) for boots, armor, medical |
| `FRED_API_KEY` | fredaccount.stlouisfed.org/apikeys | Brent, VIX |
| `ACLED_EMAIL`, `ACLED_PASSWORD` | acleddata.com/register | Conflict events, Ukraine and Middle East (phase 2) |
| `FIRMS_MAP_KEY` | firms.modaps.eosdis.nasa.gov/api/map_key | Fires and strikes (phase 2) |
| `COMTRADE_API_KEY` | comtradedeveloper.un.org | Trade to Ukraine and the Middle East beyond EU and US (phase 2) |

## 7. Roadmap

1. **Now:** collectors, scoring, tabs, workflow; the three key-less groups run.
2. **After keys:** Census and SAM series switch on automatically.
3. **Backtest (methodologist, trial registered first):** replay the scorer
   over 2021-2022 and quiet years; report false alarms per year and lead time
   per indicator; drop any indicator with no lead.
4. **Phase 2 sources:** ACLED, FIRMS, Polymarket, Ukraine air-raid alerts,
   EASA conflict-zone bulletins, EIA fuel stocks, Telegram digest on level change.
5. **Region scoping:** per-theatre query sets (Taiwan Strait, Korea) if wanted.

## 8. Limits

- Boots, pickups and blood are hypotheses; two of three routes lag.
- ADS-B sees only transponding aircraft, and only from first-run onward.
- GDELT and Wikipedia attention also rise on elections, exercises and films.
- With a few years of monthly history, seasonal factors rest on 3 to 5 points
  per month; scores are rough, which is why the level is a count.
- Terms: all sources used here permit this use; read ACLED's terms before
  adding it. No personal data is collected.
