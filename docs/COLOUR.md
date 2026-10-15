# Colour

The tokens live in `warwatch/page.html` (`:root`). The rule: **hue says what kind of thing it is, shape says which type, fill says combat or strong, fading says age.** Every metric gets a colour, validated or not; a metric that is not validated yet is marked by a dashed outline and a "shadow" tag, not by greying it out.

## Categorical palette (dark background)

| Hue | Hex | Map | Metrics |
|---|---|---|---|
| Cyan (brand) | #3bdfef | Military aircraft, a silhouette per role; combat filled, airlift and tankers hollow, surveillance with a dashed ring | Unusual readings (2 to 3 SD, bold); the unusual-readings tile; chart lines |
| Blue | #6d8dff | Ships; warships filled, merchant ships hollow | |
| Pink | #ff6fb1 | Maritime incidents (diamond with "!") | Strong readings (3 SD or more, filled pill) |
| Lime | #b8e04a | Fires and heat (dots sized by heat, fading with age) | Timing tells (◆) |
| Violet | #b08cff | Hazard warnings and airspace bulletins (triangle, diamond) | Coverage tile |
| Grey | #b6bec6 | Chokepoints, cities (structure, not activity) | Readings below 2 SD (#c9d1d9 mild, #7d8790 normal) |

Checked with the dataviz palette validator against the map's land colour (#1b2128): cyan, blue, pink and lime clear the colour-blind target in every pairing (worst ΔE 10.1, target 8) and the normal-vision floor (worst 20.6, floor 15). Violet vs blue and lime vs the yellow Watch level are too close for some colour-blind readers, so they always differ in shape: triangles vs hulls, small dots vs labelled pills.

## Levels

Normal #46c28a · Watch #f4d846 · Elevated #fb8e22 · Critical #f0405a, always with the word. The same colours are used while the model is in shadow, with a dashed outline. Red with an icon also marks a failed feed or an emergency squawk.

## Reference

The US travel advisory is a muted violet tint on the map: #242435, #2d2a45, #383158 (#2e3245, #363553, #413a66 on theatre land), subdued so it sits under the other layers.

## Neutral

`n1` #3b4148 · `n2` #5a636c · `n3` #8a939c · `n4` #b6bec6 · `n5` #e8ecf0 for structure, borders and data quality (stale, collecting, needs a key).

## Structure

Theatres sit in six regions (Middle East, Europe, East Asia, South Asia, Africa, Americas). A theatre with no war of its own that is at risk because a neighbour's war reaches it is tagged **spillover** (`SPILLOVER` in `config.py`): Iraq and the GCC (from Iran, Israel and Yemen), Lebanon (from Israel), Syria (from Israel and Iran) and the Eastern flank (from Ukraine). The tag is descriptive. Separately, `SUBTHEATRES` lists the spillover theatres whose model pools its usual rate with the neighbouring wars because they have too few events of their own (Iraq, the GCC, Lebanon and Syria).
