# Fonts

The app serves its own fonts and loads none from another site.

| File | Family | Use | Source | Licence |
| --- | --- | --- | --- | --- |
| `switzer-normal.woff2` | Switzer | the interface | Indian Type Foundry, [fontshare.com/fonts/switzer](https://www.fontshare.com/fonts/switzer) | ITF Free Font License 2.0 |
| `sentient-normal.woff2`, `sentient-italic.woff2` | Sentient | the dispatch sentence and summaries | Indian Type Foundry, [fontshare.com/fonts/sentient](https://www.fontshare.com/fonts/sentient) | ITF Free Font License 2.0 |
| `jet-brains-mono-normal.woff2` | JetBrains Mono | ids, coordinates, dates, eyebrow labels | [github.com/JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) | SIL Open Font License 1.1 |

## Switzer and Sentient are not in the repository

The ITF Free Font License lets a site serve these fonts from its own pages, but it does not allow the files to be passed on through
a public repository. So they are not committed. `scripts/fetch-fonts.mjs` downloads the official variable files from Fontshare
before `npm run dev` and `npm run build`, and writes `fontshare.css` with their `@font-face` rules. All three are git-ignored.

If Fontshare cannot be reached, the build still succeeds: `fontshare.css` is written without the missing faces and the page uses
the system fonts named in `styles.css` until the next build. Do not edit, subset or convert the files; the licence forbids it.
The licence text comes in each family's download from Fontshare (`License/FFL.txt`).

## JetBrains Mono

Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono). Licensed under the SIL Open Font
License, Version 1.1: https://openfontlicense.org/open-font-license-official-text/. The file is the variable upright cut, unmodified.
