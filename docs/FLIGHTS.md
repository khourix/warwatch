# Civil flights

Reports before strikes often mention flights diverted away from an airport, airlines cancelling, and private jets leaving. WarWatch counts these from public flight-tracking data, one day behind.

Code: `warwatch/flights.py`, fed by `backfill/sources_adsb.py`. Jobs: `adsb-daily.yml` (the last few days, daily) and `backfill.yml` with `source=adsb` (history from 2023, one job per quarter).

## Source

The adsb.lol daily archive: every aircraft trace of the day, as GitHub releases (Open Database License). The archive pass that counts military aircraft reads each trace once. Traces that never come near a theatre airport are skipped before they are parsed, so a day takes about two minutes.

Routes and airports come from [vradarserver/standing-data](https://github.com/vradarserver/standing-data) (CC0, updated daily): about 620,000 callsigns, each with the airports it flies between.

## How a trace becomes a flight

Each trace is cut into legs, from a take-off to a landing.

- A take-off or landing is a switch between ground and air reports. Where receivers lose the aircraft low down, it is the first or last point below 3,000 ft within 15 km of an airport.
- A gap in coverage while the aircraft is high, over Iran or the open sea say, does not end the leg. So a Doha to London flight stays one leg.
- A new callsign, a gap of 30 minutes while low, or any gap over 5 hours ends a leg.

Only airline flights are judged: an ICAO airline callsign (three letters, then a digit) on an airliner. The emitter category decides (A2 to A5), or the type designator when the category is missing. Flight schools and helicopter operators use airline-style callsigns too, which is why the aircraft is checked.

## What is counted

| Series | What it counts |
|---|---|
| `flights_dep_<t>` | airline departures from the theatre's airports |
| `flights_div_<t>` | diversions: the flight came down below 20,000 ft within 150 km of the airport its route goes to, then landed at least 50 km away at an airport not on its route |
| `flights_turnback_<t>` | turnbacks: landed back where it took off, after 20 minutes to 4 hours, in view the whole time |
| `flights_hold_<t>` | holds: circled at least twice (720 degrees of turning) below 20,000 ft within 60 km of where it landed |
| `bizjet_dep_<t>` | business-jet departures from the theatre's airports |
| `bizjet_out_<t>` | business jets that took off in the theatre and landed in another country |
| `flights_legs` | airline legs that touched any theatre airport: coverage, and the mark that a day was read |

A theatre's airports are those in its countries (`flights.THEATRE_ISO`). Western Russia's airports count for Ukraine.

The diversion rule is strict on purpose. Route tables go stale: charters, cargo and reused flight numbers land "elsewhere" every day. A flight that never began its descent into the planned airport may never have been going there. The rule misses flights turned away far out, for example when a closure is announced en route. Those show in the departures and turnbacks instead.

A flight whose callsign is not in the route table is not judged.

## Privacy

Business jets are counted, never listed. Aircraft whose owners asked not to be shown (the LADD and PIA flags) never appear by name in anything WarWatch writes. Military aircraft are left to the military pass.

## Files

`backfill/data/` holds the series as `date,value` CSVs. `backfill/data/flights/` holds:

- `airports-YYYY-MM.csv`: per day and theatre airport, departures, arrivals, diversions away and in, turnbacks, holds, business-jet departures and departures abroad;
- `events-YYYY-MM.csv`: each diversion and turnback, with time, callsign, type, airports and position (none for hidden aircraft);
- `places.csv`: name, country and position of every theatre airport seen, so the map never needs the route table.

## How it shows

- **Map.** Theatre airports are rings. An amber ring had diversions or turnbacks this week; a red ring had 60% or fewer of its usual departures (the median of the 28 days before). Quiet airports show from zoom 4.5. Diversions and turnbacks are arrows beside the airport they landed at. Each opens a card.
- **Signals.** Under Air (departures, diversions, turnbacks, holds) and Travel (business jets), labelled "not tested".
- **Tells.** "Flights diverted or turned back" fires at 3 or more a day for 2 days and three times the usual rate. "Business jets fly out" fires at 5 or more a day over 3 days and double the usual. The "Airliners thin out" tell also reads departures.

## Not tested

None of these series is in the score. Each enters only after a test on the event list (`docs/EVENTS.md`), written down before it is run, shows it moves before events. That needs the history back to 2023: dispatch `backfill.yml` with `source=adsb`, which reads only the days whose flights are missing.

## One day, checked

A full archive day, 22 October 2026, run on a GitHub runner on 24 October:

- 12,132 airline legs touched a theatre airport.
- One diversion in all theatres: Cebu Pacific CEB377, Manila to Cagayan de Oro, landed at Davao. Looser versions of the rule flagged several more flights that day, which turned out to be stale routes and charters.
- Three turnbacks: Air India Hyderabad, Ryanair Katowice, IndiGo Bengaluru.
- Business jets out of the theatre: Eastern flank 29, Israel 18, Gulf 13.

A quiet day, as it should be. The test of whether these series move before events needs the history.
