# Open sources from the Argos Atlas review (November 2026)

Argos Atlas (argosatlas.com) sells access to a map built on public feeds. Its own data is not open: its API comes only with a paid plan. Its attributions page names its upstream sources, though. The sources below are the ones WarWatch did not already read. Each is free, and each was read live on 26 November 2026 before it was wired in.

Every new series is untested (`catalog.NOT_TESTED`). Each one shows on the page and goes into the forward record, but it stays out of the score until a test, written down before it is run, shows that it leads events.

| Item | Source and licence | What WarWatch reads | Series | Code |
|---|---|---|---|---|
| 1 | hormuz.now, CC BY 4.0 | Ships crossing the Strait of Hormuz each day, ships waiting, and ships whose AIS went silent near the strait | `hormuz_cross_iran`, `hormuz_waiting_iran`, `hormuz_silent_iran` | `openfeeds.py` |
| 2 | GeoConfirmed public API | Events geolocated from photo or video, counted over 30 days in each theatre box, from January 2023. The newest 7 days are dropped because volunteers geolocate late. | `geoconf_<theatre>` | `openfeeds.py` |
| 3 | US Treasury SDN list (OFAC), public domain | Vessels by IMO number and MMSI, and aircraft by tail number and Mode S code, matched against AIS and the adsb.lol archive. `slow.yml` refreshes the list daily into `warwatch/data/sanctions_ofac.csv`. | `aisday_sanctioned_<region>`, `flights_sanc_<theatre>` | `sanctions.py`, `aiswatch.py`, `flights.py` |
| 4 | DeepStateMap | Km² held by Russia in each map version, and the 7-day gain. **Not on the page yet:** the project's reuse terms are still to be confirmed. | none yet | `openfeeds.py` |
| 5 | Global Affairs Canada; Australia's Smartraveller (CC BY 4.0) | Advisory level per country, summed per theatre, on the same 1 to 4 scale as the US series. Only Canada is in the catalogue: Smartraveller timed out from the cloud before, so its parser waits for a route that answers. | `ca_<theatre>` | `openfeeds.py` |
| 6 | GDACS (CC BY 4.0), NASA EONET | Wildfires and volcanoes listed in the last 30 days. The fire classifier marks a detection near one as natural heat. `imagery.yml` refreshes the list every 6 hours. | none (the fire classes on the map) | `openfeeds.py`, `firecls.natural_check` |
| 7 | none (a method) | An evidence grade on each event-desk candidate (several outlets, one outlet, or state media only), with the outlet count | none (`event_candidates.csv`) | `eventdesk.grade` |

## Limits

- **hormuz.now** history starts on 19 October 2026, so these series can't be backtested. They are a forward record only.
- **GeoConfirmed** depends on volunteer effort, which varies, so a count partly measures attention. The series show counts only, never GeoConfirmed's own descriptions. Its republishing terms are still to be confirmed.
- **Sanctions matching** uses today's list. A ship or aircraft designated in 2025 would be counted in 2023 as if it were already known then. A backtest on the adsb.lol archive must therefore use each designation's date. The SDN remarks don't carry it, but OFAC's recent-actions pages do. Days of the archive that are already read are not read again, so `flights_sanc_` fills only from the first day read after the list arrives.
- **Fire classifier:** in Ukraine, wildfires and shelling fires overlap, and The Economist's model already judges which fires are war-related. The natural-hazard check therefore skips Ukraine. Elsewhere, a listed wildfire takes 30 points off a detection's score. A volcano makes the detection "volcano".
- **Evidence grade:** the "verified with media" grade is given by the person who reviews a candidate, not by the code.
- **Not done:** WarSpotting's losses API was not sampled, and its terms are unread. The UK, EU and Canadian sanctions lists are not read yet. Feeding Canada and Australia into the "advisory raised" timing tell needs its own test first.
