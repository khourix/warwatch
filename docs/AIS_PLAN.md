# Ships: coverage plan, and the MarineTraffic question

Status: proposal for approval. 24 Oct 2026. This change adds one document and one link. No code.

## 1. The decision in one page

| Question | Answer |
|---|---|
| Can we scrape MarineTraffic? | No. Their terms forbid automated access and forbid publishing the data. |
| Is there a free route we are not using? | Yes. Open Waters AIS (openwaters.io) re-serves AISHub and aisstream. It needs no key and no payment. |
| Does it cover the Gulf? | The UAE coast and the southern Gulf, yes. The Strait of Hormuz, thin. |
| Does it cover the Red Sea? | No. Zero ships in every Red Sea box I tested. No free terrestrial network covers it. |
| What do we do about the Red Sea? | Counts only, from Global Fishing Watch, 4 to 5 days late. Live positions there need a paid feed. |
| Do we need a receiver in Dubai? | No. A volunteer station in Dubai already feeds this network. A second one adds little. |
| Cost | $0 for the free route. The only paid option is about EUR 199 a month, and it can wait. |

## 2. Where the current collector stops

PR #51 built the AIS collector. PR #52 fixed its workflow. It now runs every 30 minutes and works as designed.

Latest run, 24 Oct 2026 08:28Z: 12,486 messages in 542 seconds, 4,372 ships kept.

| Region | Ships heard today | Note |
|---|---|---|
| Baltic (Eastern flank) | 2,392 | Good |
| East Mediterranean (Israel) | 309 | Good |
| Black Sea (Ukraine) | 88 | Good |
| Gulf, 24 to 30 N, 48 to 58 E | 1 | One ship |
| Red Sea, 12 to 22 N, 38 to 45 E | 0 | None |

The code is not the problem. Free AIS is radio, received by volunteers on the coast. There are no volunteer receivers on the Red Sea coast in either free network. The Gulf has almost none.

## 3. MarineTraffic: the answer is no, and it is not a technical question

Kpler owns MarineTraffic. Their terms of use say three separate things that each stop this:

- "You are explicitly prohibited from using any automated tools, software, or scripts that extract, download, or manipulate content from MarineTraffic's website without prior written consent."
- "not copy, (sub)licence, (re)sell, reproduce, duplicate or publish the Service or the Data."
- The user agreement limits the data to "your own internal use only."

A stealth browser can probably get past the bot check. That is the weakest part of the argument, not the strongest. The data would still be theirs, the publication would still be a breach, and the site would still be public with your name on it.

Three practical points:

1. The scraper would live in a public repository with their domain in the code. That is a written record of the breach, kept by us.
2. Cloudflare changes break scrapers without warning. On a warning dashboard, that shows up as "ships disappeared".
3. Even a paid MarineTraffic API licence would not include republishing positions on a public page. That needs a separate agreement, negotiated and priced.

It also breaks our own rule 3: keep within each source's terms.

## 4. Sources compared

Measured or read on 24 Oct 2026.

| Source | Live positions | Gulf | Red Sea | History | Cost | Public display allowed |
|---|---|---|---|---|---|---|
| aisstream.io (in use) | Yes | 1 ship | 0 | Only what we store | Free | Yes, no stated limit |
| Open Waters AIS (openwaters.io) | Yes, and tracks | UAE coast good, Hormuz thin | 0 | Track per ship, length varies | Free | Per source, attribution given |
| AISHub direct | Yes | 4 UAE stations | 0 | No | Free, needs a station | Yes, with credit |
| GFW AIS presence | No, counts only | Yes | Yes | 2012 to 96 h ago | Free, key held | Yes, non-commercial |
| GFW radar (SAR) | No, counts only | Yes | Yes | 2017 to 5 days ago | Free, key held | Yes, non-commercial |
| IMF PortWatch (in use) | No, counts only | Yes | Yes | Yes | Free | Yes |
| Datalastic | Yes, satellite add-on | Yes | Claimed | Yes | EUR 199 a month | Yes, their FAQ allows dashboards |
| MarineTraffic / Kpler | Yes | Yes | Yes | Yes | By quote | No |
| Spire, ORBCOMM | Yes | Yes | Yes | Yes | Enterprise | By agreement |

Open Waters AIS is open source (MIT) and speaks the aisstream protocol. A client moves to it by changing one hostname.

## 5. What I measured

Probe of `https://ais.openwaters.io/v1/vessels` at 09:50Z on 24 Oct 2026, no key.

| Box | Vessels | Under way (2 kt or more) | Reading |
|---|---|---|---|
| Gulf, 24 to 30 N, 48 to 58 E | 1,034 | 129 | Mostly moored |
| UAE coast, 24.5 to 25.8 N, 54 to 56.5 E | 696 | | Good |
| Central Gulf, 26 to 29 N, 49 to 55 E | 124 | | Partial |
| Hormuz approach, 25.5 to 27 N, 55.5 to 57.5 E | 25 | 4 | Thin |
| Hormuz narrow, 26.3 to 26.9 N, 56.2 to 56.9 E | 4 | 1 | Not usable for a crossing count |
| Bab el-Mandeb, 12.2 to 13.2 N, 43 to 43.8 E | 0 | 0 | No coverage |
| Gulf of Aden, 11 to 15 N, 43 to 52 E | 0 | 0 | No coverage |
| Jeddah, 21 to 24 N, 38 to 40 E | 0 | 0 | No coverage |
| Suez, 27 to 31 N, 32 to 34 E | 1 | 0 | No coverage |
| East Mediterranean, 30 to 32 N, 32 to 36 E | 213 | | Good |
| Bosporus, 40.9 to 41.3 N, 28.9 to 29.2 E | 121 | 12 | Good |
| Oresund, 55.5 to 56 N, 12.4 to 13 E | 455 | 20 | Good |
| Taiwan Strait, 23 to 25 N, 118 to 121 E | 335 | 31 | Good |

Other findings from the same probe:

- Gulf tankers, type 80 to 89: 412. Gulf cargo, type 70 to 79: 578.
- 569 of the 1,034 came from one volunteer station, listed as "near Dubai, United Arab Emirates", 370 vessels, 1,166 in 24 hours, uptime 1.0. The other 465 came through AISHub.
- Density is concentrated: 581 of the 1,034 sit in one degree cell at 25 N 55 E, off Dubai and Sharjah.
- Each response carries an attribution string naming Open Waters AIS and AISHub.
- `/v1/vessels/{mmsi}/track` returns a track for a named ship, no key.

Reading: this is a large gain for the UAE coast and the southern Gulf. It is not a Hormuz transit counter. For Hormuz and Bab el-Mandeb, PortWatch already gives the transit count, a few days late.

## 6. Proposed approach

Four steps, in order. Each is one pull request. Each can be undone by reverting it.

**P1. Move the live AIS source to Open Waters AIS.** One free token from their token page, no account. The collector keeps its 30-minute rhythm and its state file. It gains every ship type, a track per ship, and the AISHub aggregate. Keep the aisstream path in the code as a fallback, selected by one setting. Feed it the Gulf and Taiwan boxes as well as Europe.

**P2. Gulf ship map with types and a filter.** All ships in the covered area, not only military. Colour by type, filter by type and by moving only, card with name, flag, destination, speed and a track link. Mark the area as partial coverage.

**P3. Gulf and Red Sea counts by type from GFW presence.** `public-global-presence` covers all vessel types from 2012 to about 96 hours ago, filtered by flag, vessel type, speed and vessel id. The key is already held. This is the first series that gives a full type breakdown for the Red Sea, at a known lag.

**P4. A "ships seen on radar" series for the Red Sea.** We already fetch both dark and lit radar detections. We publish only the dark count. Publishing the total gives a ship count per radar pass, 5 days back, where no AIS exists. It is a small change to code we already run.

Later, if approved: the ship watchlist (OpenSanctions maritime list plus the Ukraine war-sanctions list), matched against names and IMO numbers from P1.

Not proposed now:

| Item | Why not |
|---|---|
| A receiver in Dubai | A Dubai station already feeds this network. A second one duplicates it for about $100. |
| Paid satellite AIS | EUR 199 a month. Decide after two weeks of P3 and P4. |
| Scraping MarineTraffic | Section 3. |

## 7. Rules for showing coverage honestly

A zero is only a zero where a receiver exists.

| Region | Grade | What the page may say |
|---|---|---|
| Baltic, Black Sea, East Mediterranean | Good | Counts and trends |
| Gulf, UAE coast and south | Partial | Counts for the covered part only |
| Strait of Hormuz | Thin | Never a live crossing count |
| Red Sea, Gulf of Aden, Suez | None | Radar and presence counts only, with the lag |

Every ship layer and series carries its source, its coverage grade and its lag. A region with no coverage shows "no data", never "no ships".

## 8. What I did not verify

- Open Waters AIS calls its free tier "for a personal project or a hobby". A public dashboard is close to that, but they do not say it in writing. I drafted an email to ask (below). This is the one licence question open.
- GFW presence counts in the Gulf and the Red Sea. I have no token on this machine. The dataset description and filters are confirmed; the counts are not.
- Whether the EUR 199 Datalastic plan includes satellite positions, and whether it reaches the Red Sea.
- Whether Open Waters AIS stays up. It is beta, has no service agreement, and runs on about 50 volunteer stations plus upstream feeds.

Email to `hello@openwaters.io`, for you to send or for me to send from a project address:

> I run WarWatch, a free public dashboard that shows conflict risk from public data, with no advertising and no revenue. I would like to show live ship positions in the Gulf on it, with the attribution string your API returns. Is that inside your free personal tier, or do you want it treated as commercial? The site is khourix.github.io/warwatch.

## 9. Decisions I need from you

1. Approve P1 and P2, the free live source and the Gulf ship map.
2. Approve P3 and P4, the GFW counts for the Gulf and the Red Sea.
3. Red Sea live positions: hold at counts only (my recommendation), or start a paid feed now.
4. The email above: do you want to send it, or should I?

## 10. How to undo

This change is documentation only. Revert the commit.

## Sources

- Kpler and MarineTraffic terms of use: https://www.marinetraffic.com/en/p/terms
- MarineTraffic user agreement: https://www.marinetraffic.com/en/p/user-agreement
- AISHub terms, updated 8 Oct 2026: https://www.aishub.net/terms
- AISHub stations by country: https://www.aishub.net/countries
- Open Waters AIS API: https://openwaters.io/api/ais/
- Open Waters AIS limits: https://openwaters.io/ais/
- aiscast source (MIT): https://github.com/openwatersio/aiscast
- GFW datasets and filters: https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts
- GFW terms, CC BY-NC 4.0: https://globalfishingwatch.org/terms-of-use/
- Datalastic FAQ and pricing: https://datalastic.com/faq/ , https://datalastic.com/pricing/
