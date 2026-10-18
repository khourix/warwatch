# Colour

The tokens live in `warwatch/page.html` (`:root`). The look is "night ops": cool neutrals that step back, so the few warm marks stand out. There are three rules.

1. **Warm means unusual, and nothing else.** One warm scale carries every measure: amber, then orange, then red. Grey and near-white are the calm state and context.
2. **Cyan means you can click it, or you picked it.** Links, the selected tab, focus rings and buttons. Cyan never carries data.
3. **Groups are told apart by name, icon and position, not by colour.** The five signal groups have no hue of their own.

## Neutrals

| Token | Hex | Use |
|---|---|---|
| `--bg` | #0b0e12 | Page |
| `--panel` · `--panel2` · `--panel3` | #12161b · #181d23 · #20262d | Panels, rows on hover, raised controls |
| `--line` · `--line2` | #252c34 · #343c46 | Dividers, outlines |
| `--ink` | #eef1f4 | Main text (16:1 on the panel) |
| `--mute` | #b0b8c1 | Secondary text (9.1:1) |
| `--dim` | #868f99 | Labels and hints (5.5:1) |
| `--faint` | #59626c | Decoration only, never text (2.9:1) |
| `--ocean` · land · theatre land | #090c10 · #161b21 · #1d242c | Map |

## The warm scale

| Step | Hex | Means |
|---|---|---|
| Calm | #222930 | Below 1.5 SD from normal (a cell fill) |
| Mild | #38414a | 1.5 to 2 SD |
| Watch | #f4ad62 | 2 SD or more: unusual. Also a fired timing tell |
| Elevated | #ec7838 | 3 SD or more: strong |
| Critical | #e14d44 | 4.5 SD or more |

The theatre levels use the same three colours, always with the word: Watch #f4ad62, Elevated #ec7838, Critical #e14d44. Normal is grey #6b747e and shows as an outlined pill. A level says how unusual a theatre's signals are now. It is a description, not a forecast, so it is coloured whether or not the 30-day model has passed its release checks. The standing risk, which comes from that model, stays grey until it passes.

The experimental Activity chip ([ACTIVITY.md](ACTIVITY.md)) sits beside the level with a dashed outline, so it never reads as a second level. It is amber text when ACTIVE and grey when QUIET.

Text on a warm fill is #1a1009: 9.8:1 on Watch, 6.5:1 on Elevated, 4.8:1 on Critical.

## The map

A theatre's land takes its level: a tint of the level colour at about 26% over land (#504132, #4e3327, #4b282a), a soft glow along the inside of the border (the level colour, 9 px, 16% opacity, clipped to the country) and a crisp 1.4 px rim in the full colour. Normal theatres get a slightly lighter land (#1d242c) and no rim.

Every mark must read on every tint, so every mark has a dark halo (#07090c) under it.

- **Alert pins** are warm, with a white ring: emergency squawks (red circle), maritime incidents (orange diamond with "!"), unusual fires (amber dot), bases where satellite passes differ from usual (amber square for one pass, orange for two). A warm pin on a warm tint can fall to 2.5:1, so the white ring, not the fill, carries the contrast: 9.8:1 or more on every tint.
- **Context marks** are near-white (#dfe5ea, 7.7:1 or more on every tint): aircraft by role silhouette, ships by hull, hazard warnings (triangle), airspace bulletins (diamond), bases with nothing unusual (hollow square), chokepoints. Hollow means a support role or a civil ship. Unexplained heat is a small grey dot (#aab3bc); explained heat is a dashed grey ring.
- **Labels** are dark pills: a dot and a rim in the level colour, the name, and the level word when it is not Normal. Only Critical pulses. An amber ring round a name means a timing tell fired this week.
- **US travel advice** is a third party's judgement, so it is a neutral lift of the land by step (#1f262e, #262e37, #2e3741), never warm.

Fainter means older on every alert layer: last 24 hours solid, 1 to 3 days dimmed, older a faint outline.

## Panels

The theatre panel leads with the ladder: the five signal groups ordered slow to fast (Logistics, Markets, People, News, Physical), each with a strip of its distance from normal on each of the last 60 days on the warm scale. The region panel leads with the matrix: theatres by groups, a grey cell unless a group moved. Charts draw their line in light grey (#c9d0d7) with the warm scale for thresholds.

## Motion

`--d1` 120 ms for hover and highlights, `--d2` 200 ms for a ladder line opening or closing, `--d3` 320 ms kept for larger moves. Easing `--ease` is cubic-bezier(.2,.7,.2,1). With reduced motion on (the system setting or Settings > Motion), nothing moves.

## Structure

Theatres sit in six regions (Middle East, Europe, East Asia, South Asia, Africa, Americas). A theatre with no war of its own that is at risk because a neighbour's war reaches it is tagged **spillover** (`SPILLOVER` in `config.py`): Iraq and the GCC (from Iran, Israel and Yemen), Lebanon (from Israel), Syria (from Israel and Iran) and the Eastern flank (from Ukraine). The tag is descriptive. Separately, `SUBTHEATRES` lists the spillover theatres whose model pools its usual rate with the neighbouring wars because they have too few events of their own (Iraq, the GCC, Lebanon and Syria).
