import { useEffect } from 'react'
import { TERMS, ORDER } from './glossary'
import { Crumbs } from './views'
import { GroupBars } from './watch'
import { Lnk, NowMark } from './ui'
import type { Route } from './data'

/* The guide: how to read a row of the board, every term the explainers use (glossary.ts), and where the data comes from.
   Each part and each term has an anchor (#read, #sources, #sd, #tripwire) so a link or the command menu can open it there. */
export function GlossaryView({ go, term }: { go: (r: Route) => void; term?: string }) {
  useEffect(() => {
    if (!term) return
    let n = 0, id = 0
    const find = () => { const el = document.getElementById(term); if (el) { el.scrollIntoView({ block: 'start' }); el.focus({ preventScroll: true }) } else if (n++ < 40) id = requestAnimationFrame(find) }
    id = requestAnimationFrame(find); return () => cancelAnimationFrame(id)
  }, [term])
  const toc: [string, string][] = [['read', 'How to read it'], ['terms', 'Words and numbers'], ['sources', 'Sources and credits']]
  return (
    <div className="pb-8">
      <Crumbs back={{ v: 'brief' }} items={[['Watch', { v: 'brief' }], ['Guide']]} go={go} />
      <div className="px-5 pb-2 pt-2">
        <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em]">Guide</h1>
        <p className="mt-2.5 font-serif text-[17px] leading-[1.42] text-fg [text-wrap:pretty]">WarWatch watches public data for signs that a conflict is building up, and says plainly when the signs are there and when they are not. It is an instrument, not a forecast.</p>
        <nav aria-label="On this page" className="mt-3 flex flex-wrap gap-1.5">
          {toc.map(([id, label]) => <a key={id} href={`#${id}`} onClick={e => { e.preventDefault(); go({ v: 'glossary', term: id }) }} className="inline-flex h-8 items-center rounded-full border border-line px-3 text-[12.5px] text-fg2 transition-colors duration-[120ms] hover:border-line2 hover:text-fg">{label}</a>)}
        </nav>
      </div>

      <section id="read" tabIndex={-1} aria-labelledby="read-h" className="mx-5 mt-4 scroll-mt-4 outline-none">
        <h2 id="read-h" className="mb-2 text-[16px] font-semibold">How to read it</h2>
        <p className="mb-3 text-[13.5px] leading-[1.5] text-fg2">Every theatre gives two answers. <span className="text-fg">Now</span> says what is already happening there, set by hand. <span className="text-fg">Build-up</span> says whether the signals are rising, worked out from the data each run. A war can be steady, and a calm place can be building up.</p>
        <Anatomy />
      </section>

      <section id="terms" tabIndex={-1} aria-labelledby="terms-h" className="mt-6 scroll-mt-4 outline-none">
        <h2 id="terms-h" className="mx-5 mb-2 text-[16px] font-semibold">Words and numbers</h2>
        <p className="mx-5 mb-2 text-[13px] text-fg2">The same sentences open when you tap a dotted term anywhere in the app.</p>
        <dl className="mx-5 rounded-r3 border border-line bg-s1 px-4">
          {ORDER.map(k => { const t = TERMS[k]; return (
            <div key={k} id={k} tabIndex={-1} className="scroll-mt-4 border-t border-line py-3 outline-none first:border-0">
              <dt className="text-[14px] font-medium text-fg">{t.term}</dt>
              <dd className="mt-0.5 text-[13px] leading-[1.5] text-fg2"><span className="text-fg">{t.says}</span> {t.from}</dd>
            </div>) })}
        </dl>
        <p className="mx-5 mt-3 text-[12.5px] text-fg2">How the numbers have done, and the model's checks, are on the <Lnk to={{ v: 'record' }} go={go} className="lnk">Record</Lnk>.</p>
      </section>

      <section id="sources" tabIndex={-1} aria-labelledby="src-h" className="mx-5 mt-6 scroll-mt-4 outline-none">
        <h2 id="src-h" className="mb-2 text-[16px] font-semibold">Sources and credits</h2>
        <p className="mb-3 text-[13px] leading-[1.5] text-fg2">WarWatch only reads public data. Each signal's own page links to where it comes from. The main sources:</p>
        <ul className="rounded-r3 border border-line bg-s1 px-4">
          {SOURCES.map(([name, what, terms, url]) => (
            <li key={name} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 border-t border-line py-2.5 first:border-0">
              <span className="min-w-0"><a href={url} target="_blank" rel="noreferrer" className="lnk text-[13.5px] text-fg">{name}</a><span className="block text-[12px] leading-[1.4] text-fg2">{what}</span></span>
              <span className="text-right text-[11.5px] text-fg3">{terms}</span>
            </li>))}
        </ul>
        <p className="mt-3 text-[12px] leading-[1.5] text-fg3">Contains modified Copernicus Sentinel data. News reports are linked, never copied, and are graded by who published them, not checked. WarWatch is not affiliated with any source above.</p>
      </section>
    </div>
  )
}

/* source, what WarWatch takes from it, its terms as WarWatch uses them, and where to read more */
const SOURCES: [string, string, string, string][] = [
  ['Copernicus Sentinel-1 and Sentinel-2', 'Radar and optical pictures of watched bases and heat', 'Copernicus open licence', 'https://dataspace.copernicus.eu'],
  ['NASA FIRMS (VIIRS)', 'Fires and heat seen from orbit', 'NASA open data', 'https://firms.modaps.eosdis.nasa.gov'],
  ['NASA GIBS', 'Wide satellite tiles under heat', 'NASA open data', 'https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api'],
  ['adsb.lol', 'Military aircraft positions and diverted flights', 'ODbL', 'https://adsb.lol'],
  ['Global Fishing Watch', 'Ships with no AIS on radar, and loitering carrier vessels', 'GFW terms of use', 'https://globalfishingwatch.org'],
  ['IMF PortWatch', 'Daily ship transits through chokepoints', 'IMF terms of use', 'https://portwatch.imf.org'],
  ['UKMTO', 'Maritime security incidents', 'Public notices', 'https://www.ukmto.org'],
  ['NGA maritime safety', 'Navigational warnings at sea', 'US government work', 'https://msi.nga.mil'],
  ['US State Department', 'Travel advisories and ordered departures', 'US government work', 'https://travel.state.gov'],
  ['Tzeva Adom and alerts.in.ua', 'Siren and air-raid alerts', 'Public alerts', 'https://www.oref.org.il'],
  ['GDELT and Google News', 'News counts and links to reports', 'Linked, not copied', 'https://www.gdeltproject.org'],
  ['Natural Earth', 'Borders and coastlines', 'Public domain', 'https://www.naturalearthdata.com'],
  ['OpenStreetMap and Protomaps', 'The detailed basemap', 'ODbL', 'https://www.openstreetmap.org/copyright'],
]

/* a board row, drawn with the board's own parts, with each part named below it */
function Anatomy() {
  const parts: [string, string][] = [
    ['Theatre and build-up', 'The place, and its build-up level in words: Steady, Watch, Elevated or Critical. Amber and orange are used for build-up only.'],
    ['Now', 'What is already happening: a filled square for war, half filled for strikes, an outline for tension. Set by hand, and never changes the build-up.'],
    ['Groups', 'Five bars, one per group of signals (logistics, markets, people, news, physical). Taller and warmer means further from usual. A dashed one has no data.'],
    ['Reading', 'The build-up as a number from 0 to 100, with the Watch line marked on its bar.'],
    ['7 d', 'How much the reading moved over the last 7 days.'],
  ]
  return (
    <div className="rounded-r3 border border-line bg-s1">
      <div className="grid grid-cols-[minmax(0,1fr)_58px_44px_22px_30px] items-center gap-x-2.5 border-b border-line px-4 py-3" aria-hidden>
        <span className="min-w-0"><span className="flex items-center gap-1.5 text-[13.5px] font-medium text-fg">Example theatre<Num n={1} /></span><span className="mt-[3px] flex items-center gap-2 text-[11.5px]"><span className="text-z2t">Watch</span><NowMark now="strikes" /><Num n={2} /></span></span>
        <span className="flex items-center gap-1"><GroupBars g={{ Logistics: 0.4, Markets: 1.4, People: 2.4, News: 3.1, Physical: null }} /><Num n={3} /></span>
        <span className="relative h-[5px] rounded-full bg-z0"><i className="absolute inset-y-0 left-0 w-[56%] rounded-full bg-fg2" /><i className="absolute -top-[3px] left-1/2 h-[11px] w-px bg-fg3" /></span>
        <span className="num text-right text-[12.5px] text-fg">56<Num n={4} /></span>
        <span className="num text-right text-[12px] text-fg2">+9<Num n={5} /></span>
      </div>
      <ol className="px-4 py-2">
        {parts.map(([h, says], i) => (
          <li key={h} className="grid grid-cols-[22px_minmax(0,1fr)] gap-x-2 py-1.5 text-[13px] leading-[1.45]">
            <span className="mt-[2px] grid h-[17px] w-[17px] place-items-center rounded-full border border-fg3 text-[10.5px] font-medium leading-none text-fg">{i + 1}</span>
            <span><span className="font-medium text-fg">{h}.</span> <span className="text-fg2">{says}</span></span>
          </li>))}
      </ol>
    </div>
  )
}
const Num = ({ n }: { n: number }) => <sup className="ml-0.5 text-[9.5px] font-medium text-fg3">{n}</sup>
