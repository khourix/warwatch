# Feed

A reader subscribes to `feed.xml` (linked from the page head and the This week panel) and gets this week's timing tells and strong readings as RSS items.

## Sub-features

- `feed-built` the render writes `feed.xml` next to `index.html`.
- `feed-valid` it parses as XML and has items.
- `feed-linked` the page links to it and the link resolves inside the site folder.

## How to get to it (user POV)

- https://khourix.github.io/warwatch/feed.xml in a feed reader.
- The `RSS feed` button in the This week panel; `<link rel="alternate">` in the page head.

## Driving it with verify.sh

Preconditions:

- Demo render in `$T/site`.

- **Built and valid.** `outputs-parse` prints `feed.xml parses (N items)`; a copy is saved as `demo-feed.xml` in the evidence.
- **Linked.** `links-template` checks `href="feed.xml"` resolves to a file in the site folder.
- **By hand.** Run `python3 -c "import xml.etree.ElementTree as E; r=E.parse('$T/site/feed.xml').getroot(); print(len(r.findall('.//item')))"`. It prints the item count (20 on the buildup demo).

## Gotchas

- The item count depends on the scenario; the check requires valid XML, not a fixed count.
- `TestGeoAndPage.test_feed_is_valid_rss` covers the feed format in the unit tests.
