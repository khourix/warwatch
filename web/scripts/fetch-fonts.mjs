// Switzer and Sentient come from Fontshare under the ITF Free Font Licence. It allows serving them from our own site but not
// keeping the files in a public repository, so they are downloaded here before `vite` and `vite build` (predev, prebuild)
// and never committed. This always writes src/fonts/fontshare.css, with one @font-face per file that is present: if Fontshare
// cannot be reached the build still succeeds and the page falls back to the system fonts named in styles.css until the next build.
import { mkdir, writeFile, readFile, rename } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'fonts')
const FACES = [
  { family: 'Switzer', slug: 'switzer', axis: 1, style: 'normal', weight: '100 900', file: 'switzer-normal.woff2' },
  { family: 'Sentient', slug: 'sentient', axis: 1, style: 'normal', weight: '200 700', file: 'sentient-normal.woff2' },
  { family: 'Sentient', slug: 'sentient', axis: 2, style: 'italic', weight: '200 700', file: 'sentient-italic.woff2' },
]
const isWoff2 = buf => buf.subarray(0, 4).toString('latin1') === 'wOF2'
// a file already here is kept only if it is a real font, so a cut-off download is fetched again
const present = f => readFile(f).then(isWoff2, () => false)
const get = async url => {
  const r = await fetch(url, { signal: AbortSignal.timeout(20_000) })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r
}

async function download(face) {
  const out = path.join(dir, face.file)
  if (await present(out)) return true
  try {
    // the variable cut of each style: @1 upright, @2 italic
    const css = await (await get(`https://api.fontshare.com/v2/css?f[]=${face.slug}@${face.axis}`)).text()
    const url = css.match(/url\('?((?:https?:)?\/\/cdn\.fontshare\.com\/[^')]+\.woff2)'?\)/)?.[1]
    if (!url) throw new Error('no woff2 address in the stylesheet')
    const buf = Buffer.from(await (await get(url.startsWith('//') ? 'https:' + url : url)).arrayBuffer())
    if (!isWoff2(buf)) throw new Error('not a woff2 file')
    await writeFile(out + '.part', buf)
    await rename(out + '.part', out)
    return true
  } catch (e) {
    // on GitHub Actions this shows as a warning on the run, since the site would otherwise change its type silently
    console.warn(`${process.env.GITHUB_ACTIONS ? '::warning::' : ''}fonts: ${face.file} not downloaded (${e.message}); the page will use a system font in its place`)
    return false
  }
}

await mkdir(dir, { recursive: true })
const got = await Promise.all(FACES.map(download))
const css = FACES.filter((_, i) => got[i]).map(f =>
  `@font-face { font-family: "${f.family}"; src: url("./${f.file}") format("woff2"); font-weight: ${f.weight}; font-style: ${f.style}; font-display: swap; }`).join('\n')
await writeFile(path.join(dir, 'fontshare.css'), `/* Written by scripts/fetch-fonts.mjs. Not committed. */\n${css}\n`)
console.log(`fonts: ${got.filter(Boolean).length} of ${FACES.length} Fontshare files in place`)
process.exit(0)   // a proxy that never answers can keep the process alive after the timeout
