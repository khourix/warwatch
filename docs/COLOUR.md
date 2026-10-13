# Colour

The dashboard uses one colour system with three families and one reference colour. The tokens live in `warwatch/page.html` (`:root`).

| Family | Tokens | Used for |
|---|---|---|
| Neutral | `n1` #3b4148 · `n2` #5a636c · `n3` #8a939c · `n4` #b6bec6 · `n5` #e8ecf0 | Structure, anything not validated (the shadow model), data quality (stale, collecting, needs a key), Normal |
| Evidence (brand cyan) | `e1` #2b6d7c · `e2` #2992a4 · `e3` #2bb8ca · `e4` #3bdfef | Everything observed: unusual readings (brighter = further from normal), timing tells (`e4`, diamond), map layers, the theatre in focus on comparison charts |
| Risk | `r1` #f4d846 Watch · `r2` #fb8e22 Elevated · `r3` #f0405a Critical | The level of a validated model, nothing else. `r3` with an icon also marks a failure or an emergency squawk |
| Reference | violet hatch, #776c9c to #bcabf1 | Third-party judgements on the map (US travel advisory levels 2 to 4). Subdued so it sits under the other layers |

Rules:

- Warm colour means a validated risk level. While the model is in shadow, levels are drawn in neutral greys.
- Text stays in ink; colour goes on marks (dots, bars, pills, map glyphs).
- On charts comparing theatres, the theatre in focus is `e3` and the others `n2`.
- Normal is `n3`, not green.

All pairs used for categories were checked for colour-blind separation (worst ΔE 9.8 under deutan/protan/tritan simulation, 17.3 with normal vision), and `e2`–`e4`, `n3`–`n5`, `r1`–`r3` reach at least 4.5:1 contrast on the page background.

## Structure

Theatres sit in six regions (Middle East, Europe, East Asia, South Asia, Africa, Americas). A theatre with no war of its own that is at risk because a neighbour's war reaches it is tagged **spillover** (`SPILLOVER` in `config.py`): Iraq and the GCC (from Iran, Israel and Yemen) and the Eastern flank (from Ukraine). The tag is descriptive. Separately, `SUBTHEATRES` lists the spillover theatres whose model pools its usual rate with the neighbouring wars because they have too few events of their own (Iraq and the GCC).
