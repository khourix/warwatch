# Event codebook

What counts as an event, so the target the model forecasts is fixed in writing and not judged after the fact. The labelled list is `warwatch/data/events.csv`; `warwatch/data/scares.csv` lists build-ups that did not end in an event (13 windows), kept for reference and not used as labels.

## Qualifying events

One row per event, in the theatre where it happens. An event qualifies if it is one of:

| Type | Definition |
|---|---|
| `onset` | A war onset, or a major new ground offensive by a state. |
| `strike` | A wave of state strikes on another state's territory, or a missile or drone exchange between states. |
| `maritime` | An attack on commercial or naval shipping, or a blockade. |
| `exercise` | A named, large-scale military exercise or drill around a contested border or strait, announced or run by the state that disputes it (the Taiwan Strait and Korean Peninsula cases in the seed list). |
| `other` | A coup with fighting, or another event the first four do not cover but that meets the spirit of the list: organised armed force used across or within a border in a way that changes the theatre's risk. |

Not events: diplomacy, sanctions, leadership changes without fighting, territory changes without new fighting, and continuation of an operation already under way (the 30 days after an event are left out of the labels for this reason).

## Fields

`date` (the first day it qualified), `theatre`, `site_theatre` (when the event happened in a sub-theatre, that sub-theatre: `iraq`, `gulf`, `lebanon` or `syria`, several joined by `;` when it struck more than one, such as `iraq;syria`; it then labels each of them as well as `theatre`, whose labels do not change), `type`, `surprise_or_buildup` (`buildup` if there were public signs in the preceding 30 days, else `surprise`), `description`, `market_moving` (Brent, gold or a local asset moved 2.5 standard deviations or more around the date; `largest_mover` and `move_sd` record which and how much), `source`.

## Adding an event

Add a row to `warwatch/data/events.csv` with the date it qualified, a `source` (a named public report), and the fields above. Do not change `date` or delete a row after the fact; correct it with a new row and a note in the pull request. The live model reads this file for its conflict-history inputs, and the monthly refit uses it as the label, so a missing recent event makes the model think its theatre is calmer than it is. Add events when they happen.

The list had 161 events, 2018-01 to 2026-09: the 78 of the seed list built for the methodology review, and 83 more from the public record, chosen by this codebook alone without looking at any indicator (also kept on their own in `events_added.csv`, which the feature study used to test the seed list's selection). They were adopted as the labels in October 2026 (assessment phase C). Two more were added on 2026-10-13, when the list was brought up to 12 October: the Houthi strikes on Saudi Aramco sites of 25 July 2026 (missed earlier) and the Houthi campaign on Saudi airports from 6 October 2026. Two more were added the same day with the Lebanon and Syria sub-theatres, both missed earlier: the militia drone attack on Tower 22 in Jordan of 28 January 2024 (filed under Iran, as the other militia attacks on US forces are) and Hezbollah's opening of the northern front on 8 October 2023, with Israel's strikes on southern Lebanon (filed under Israel). Israel's ground invasion of southern Lebanon on 1 October 2024 was not added: it continued the operation begun on 23 September, inside that event's 30 days. That makes 165: 115 are marked as having had a visible build-up, 50 as surprises, and 43 are market-moving.
