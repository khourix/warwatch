import { useMemo, useState } from 'react'
import { Satellite, Flame, MapPin } from 'lucide-react'
import { focusOnMap } from './sat'
import { asset, shortDate, short, heatColour, routeHref, useLiveMap, type Brief, type LiveMap, type Route, type MapBase, type MapFire, type LonLat } from './data'
import { Lnk, Skeleton, Failed } from './ui'
import { baseWord, baseMark, rankBase, plainDates, fireWord, KIND, Compare } from './ground'

/* Ground: every watched base as a gallery, the unusual fires the imagery review checked on Sentinel-2, and what the map data
   holds near each sea chokepoint. Everything here reads map/live.json. */

type Go = (r: Route, replace?: boolean) => void
const CHANGED = ['out', 'in', 'changed']
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/* the opening sentence, in basewatch's words for each state (STATE_WHY: radar counts bright objects); the first half is the share
   description's too (pages.py) */
function lede(bases: MapBase[]): string {
  const n = (k: string) => bases.filter(b => b.state === k).length
  const parts = [n('out') && `${n('out')} read far fewer bright objects than usual`, n('in') && `${n('in')} far more`, n('changed') && `${plural(n('changed'), 'base', 'bases')} had one pass that differed`].filter(Boolean) as string[]
  const list = parts.length < 2 ? parts.join('') : parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1]
  const rest = [n('normal') && `${n('normal')} usual`, n('nodata') && `${n('nodata')} with no recent pass`, n('optical') && `${n('optical')} with optical images only`].filter(Boolean) as string[]
  return `${plural(bases.length, 'base is', 'bases are')} watched on satellite images; most are passed by Sentinel-1 radar every two to three days. ` +
    (parts.length ? `On the latest passes, ${list}.` : 'None differed from usual on the latest passes.') + (rest.length ? ` The rest: ${rest.join(', ')}.` : '')
}

export function GroundView({ brief, live, go }: { brief: Brief; live?: LiveMap; go: Go }) {
  const lq = useLiveMap()                                    // the same query the shell holds: here for its error
  const [f, setF] = useState('all')
  const bases = live?.bases || []
  const ths = useMemo(() => brief.theatres.map(t => [t.id, short(t.name), bases.filter(b => b.theatres.includes(t.id)).length] as const).filter(x => x[2] > 0), [brief, bases])
  const shown = useMemo(() => bases.filter(b => f === 'all' ? true : f === 'changed' ? CHANGED.includes(b.state) : f === 'image' ? !!b.thumb : b.theatres.includes(f))
    .sort((a, b) => rankBase(b) - rankBase(a) || a.name.localeCompare(b.name)), [bases, f])
  const chip = (on: boolean) => `shrink-0 whitespace-nowrap rounded-full border px-2.5 py-[3px] text-[12px] transition-colors duration-[120ms] ${on ? 'border-sel bg-sel font-medium text-selink' : 'border-line2 text-fg2 hover:text-fg'}`
  const nImg = bases.filter(b => b.thumb).length
  /* "With image" only when it leaves some out */
  const chips: [string, string, number][] = [['all', 'All', bases.length], ['changed', 'Changed', bases.filter(b => CHANGED.includes(b.state)).length], ...(nImg < bases.length ? [['image', 'With image', nImg] as [string, string, number]] : []), ...ths.map(([id, n, c]) => [id, n, c] as [string, string, number])]
  return (
    <div className="pb-8">
      <div className="px-5 pt-5">
        <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em]">Ground</h1>
        <p className="mt-2 max-w-[62ch] font-serif text-[16.5px] leading-[1.42] text-fg [text-wrap:pretty]">{live ? (bases.length ? lede(bases) : 'No base is watched in this data run.') : lq.isError ? <span className="text-fg3">The bases could not be loaded.</span> : <span className="text-fg3">Loading the bases…</span>}</p>
      </div>
      {!live ? (lq.isError ? <Failed what="the map data" error={lq.error} /> : <Skeleton lines={6} />) : <>
        <section aria-labelledby="g-bases" className="pt-4">
          <h2 id="g-bases" className="sr-only">Watched bases</h2>
          <div role="group" aria-label="Show bases" className="scroll-thin flex gap-1.5 overflow-x-auto px-5 pb-1 max-[699px]:flex-nowrap min-[700px]:flex-wrap">
            {chips.map(([k, l, n]) => <button key={k} aria-pressed={f === k} onClick={() => setF(k)} className={chip(f === k)}>{l} <span className="num">{n}</span></button>)}
          </div>
          {shown.length === 0 ? <p className="px-5 py-5 text-[12.5px] text-fg3">{f === 'changed' ? 'No base differed from usual on its latest passes.' : 'No base here.'}</p>
            : <ul className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(176px,1fr))] gap-3 px-5 max-[699px]:grid-cols-1 max-[699px]:gap-2">
              {shown.map(b => <li key={b.id}><BaseCard b={b} go={go} /></li>)}
            </ul>}
          <p className="mt-2.5 px-5 text-[11.5px] leading-[1.45] text-fg3">Changed bases first. A change on radar is a reason to look, not proof: one pass far outside the usual range marks a base as differing; two in a row within a week mark it as fewer or more than usual.</p>
        </section>
        <Heat live={live} brief={brief} go={go} />
        <Chokepoints live={live} brief={brief} go={go} />
      </>}
    </div>
  )
}

/* the tag on a narrow card: the two long states in fewer words, so they are not cut off; the full words are on the base's page */
const CARD_WORD: Record<string, string> = { out: 'Far fewer objects', in: 'Far more objects' }

/* a base: its latest radar picture (or a quiet stand-in), its state as a tag (ink, with a mark), name, kind and side */
function BaseCard({ b, go }: { b: MapBase; go: Go }) {
  const [bad, setBad] = useState(false)
  const mark = baseMark(b.state)
  const tag = (cls: string) => <span className={`${cls} items-center gap-1.5 rounded-full border border-line2 px-2 py-[2px] text-[11px] text-fg`}>
    {mark && <i aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: mark }} />}<span className="truncate" title={baseWord(b.state, b.part)}>{CARD_WORD[b.state] || baseWord(b.state, b.part)}</span></span>
  /* a card on wider screens; on a phone, one row per base (picture left), so the gallery stays a single column */
  return (
    <Lnk to={{ v: 'base', id: b.id }} go={go} className="group block overflow-hidden rounded-r3 border border-line bg-s1 transition-colors duration-[120ms] hover:border-line2 max-[699px]:flex">
      <span className="relative block aspect-[3/2] bg-s3 max-[699px]:w-[116px] max-[699px]:shrink-0">
        {b.thumb && !bad ? <img src={asset(b.thumb)} alt="" loading="lazy" decoding="async" onError={() => setBad(true)} className="h-full w-full object-cover" />
          : <span className="grid h-full place-items-center text-fg3" aria-hidden><Satellite size={18} /></span>}
        {tag('absolute left-2 top-2 inline-flex max-w-[calc(100%-16px)] bg-[color-mix(in_oklab,var(--s1)_88%,transparent)] backdrop-blur-[3px] max-[699px]:hidden')}
      </span>
      <span className="block min-w-0 px-2.5 pb-2.5 pt-2 max-[699px]:flex-1 max-[699px]:py-2">
        <span className="block truncate text-[12.5px] font-medium text-fg group-hover:underline group-hover:decoration-line2 group-hover:underline-offset-[3px]" title={b.name}>{b.name}</span>
        <span className="mt-0.5 block truncate text-[11px] text-fg3">{[KIND[b.kind] || b.kind || 'Site', b.side].filter(Boolean).join(' · ')}{b.last && b.state !== 'nodata' ? ` · ${shortDate(b.last)}` : ''}</span>
        {tag('mt-1.5 hidden max-w-full max-[699px]:inline-flex')}
      </span>
    </Lnk>
  )
}

/* ---------------------------------------------------------------- heat checked on Sentinel-2 */
/* firereview.py measures the burnt ground (dNBR 0.27 or more) over the central kilometre between a clear picture before and after */
const VERDICT: Record<string, [string, string]> = {
  scar: ['Burn scar', 'at least 1 hectare of ground burnt'],
  unclear: ['Unclear', 'between 0.2 and 1 hectare burnt, or no clear picture from before'],
  none: ['No burn scar', 'under 0.2 hectares burnt'],
}
const openFire = (f: MapFire, go: Go) => { go({ v: 'map' }); setTimeout(() => focusOnMap({ kind: 'fire', x: f }), 80) }

/* one card per check: VIIRS sees a fire as several hot spots over days, and the review checks a cluster once, so the hot spots that
   share a picture are one check. A place can be checked more than once (on different days, or a neighbouring cluster): checks are
   counted apart from places, a place being the named site, else the cluster (its id in the picture's name, without the date) */
type Checked = { f: MapFire; spots: number; first: string; last: string; mw: number; day: string; place: string }
const checkDay = (src: string) => src.match(/_(\d{4}-\d{2}-\d{2})_a\.\w+$/)?.[1]
const clusterOf = (src: string) => src.replace(/^.*\//, '').replace(/_\d{4}-\d{2}-\d{2}_a\.\w+$/, '')
function Heat({ live, brief, go }: { live: LiveMap; brief: Brief; go: Go }) {
  const [all, setAll] = useState(false)
  const checks = useMemo(() => {
    const by = new Map<string, MapFire[]>()
    for (const f of live.fires || []) if (f.images && f.images.a && VERDICT[f.images.v]) by.set(f.images.a, [...(by.get(f.images.a) || []), f])
    return [...by.entries()].map(([a, fs]): Checked => {
      const f = [...fs].sort((x, y) => y.score - x.score || y.mw - x.mw)[0], ds = fs.map(x => x.date).sort()
      return { f, spots: fs.length, first: ds[0], last: ds[ds.length - 1], mw: Math.max(...fs.map(x => x.mw)), day: checkDay(a) || ds[ds.length - 1], place: f.site || clusterOf(a) }
    }).sort((a, b) => b.last.localeCompare(a.last) || b.f.score - a.f.score)
  }, [live])
  const n = (v: string) => checks.filter(p => p.f.images!.v === v).length
  const places = new Set(checks.map(c => c.place)).size
  const spots = checks.reduce((a, p) => a + p.spots, 0)
  const shown = all ? checks : checks.slice(0, 12)
  return (
    <section aria-labelledby="g-heat" className="mt-8 border-t border-line px-5 pt-5">
      <h2 id="g-heat" className="text-[19px] font-semibold tracking-[-0.02em] text-fg">Heat with a satellite picture</h2>
      {checks.length === 0 ? <p className="mt-2 text-[12.5px] text-fg3">No unusual fire has a Sentinel-2 check in this data run.</p> : <>
        <p className="mt-1.5 max-w-[72ch] text-[12.5px] leading-[1.5] text-fg2">
          {plural(checks.length, 'check', 'checks')} at {plural(places, 'place', 'places')} with unusual heat ({plural(spots, 'hot spot', 'hot spots')} seen by NASA VIIRS) compare a clear Sentinel-2 picture from after the fire with one from before, where there was one: {n('scar')} {n('scar') === 1 ? 'shows' : 'show'} a burn scar, {n('unclear')} {n('unclear') === 1 ? 'is' : 'are'} unclear and {n('none')} {n('none') === 1 ? 'shows' : 'show'} no burn scar.
          {' '}The verdict is an automatic reading, not a person's: it measures how much ground turned dark in short-wave infrared over the central kilometre. A burn scar shows that something burned, not what caused it.</p>
        <ul className="mt-3.5 grid grid-cols-[repeat(auto-fill,minmax(272px,1fr))] gap-4">
          {shown.map(({ f, spots, first, last, mw, day }) => { const im = f.images!, [v, means] = VERDICT[im.v], place = f.site ? `Near ${f.site}` : fireWord(f.class), th = brief.theatres.find(t => t.id === f.theatre)
            return (
              <li key={im.a} className="min-w-0 rounded-r3 border border-line bg-s1 p-2.5">
                <Compare before={im.b && im.bd ? { src: im.b, date: im.bd } : null} after={{ src: im.a, date: im.ad || f.date }} what="Sentinel-2 picture" name={`${place}, ${shortDate(day)}`} className="" lazy words={['Before', 'After']} />
                <div className="px-0.5 pt-2.5">
                  <h3 className="flex items-start gap-1.5 text-[13px] font-medium leading-[1.3] text-fg"><Flame size={13} aria-hidden className="mt-[2px] shrink-0" style={{ color: heatColour(f.score) }} /><span className="min-w-0">{place}<span className="num font-normal text-fg2">, {shortDate(day)}</span></span></h3>
                  <p className="num mt-0.5 text-[11.5px] text-fg3">{[th ? short(th.name) : '', first === last ? (first === day ? '' : `seen ${shortDate(first)}`) : `seen ${shortDate(first)} to ${shortDate(last)}`, `${spots > 1 ? 'strongest ' : ''}${Math.round(mw)} MW`, spots > 1 ? plural(spots, 'hot spot', 'hot spots') : f.night ? 'night' : ''].filter(Boolean).join(' · ')}</p>
                  <p className="mt-1.5 text-[12px] leading-[1.4] text-fg"><b className="font-medium">{v}</b><span className="text-fg2">: {means}.</span></p>
                  {f.why && <p className="mt-1 line-clamp-3 text-[11.5px] leading-[1.45] text-fg3">{plainDates(f.why)}</p>}
                  <a href={routeHref({ v: 'map' })} onClick={e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); openFire(f, go) }} className="lnk mt-1.5 inline-block text-[12px]">Show it on the map</a>
                </div>
              </li>) })}
        </ul>
        {checks.length > 12 && <button onClick={() => setAll(!all)} aria-expanded={all} className="lnk mt-3 text-[12px]">{all ? 'Show the latest 12' : `Show all ${checks.length}`}</button>}
        <p className="mt-2 text-[11px] text-fg3">Pictures 2.5 km across. Contains modified Copernicus Sentinel data.</p>
      </>}
    </section>
  )
}

/* ---------------------------------------------------------------- chokepoints */
/* counts of what the map data holds near each strait, within NM nautical miles: the hubs' sampling circles are 120 to 250 nm
   (config.HUBS), and 150 nm reaches the approaches without taking in the next strait */
const NM = 150
const nmBetween = (a: LonLat, b: LonLat) => {
  const R = 3440.065, r = Math.PI / 180, dLat = (b[1] - a[1]) * r, dLon = (b[0] - a[0]) * r
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)))
}
const openPlace = (ll: LonLat, go: Go) => { go({ v: 'map' }); setTimeout(() => focusOnMap({ kind: 'place', ll, zoom: 5.6 }), 80) }

function Chokepoints({ live, brief, go }: { live: LiveMap; brief: Brief; go: Go }) {
  const rows = useMemo(() => (live.chokepoints || []).map(c => {
    const near = <T extends { ll: LonLat | null }>(xs: T[] | undefined) => (xs || []).filter(x => x.ll && nmBetween(c.ll, x.ll) <= NM)
    const dark = near(live.darkShips)
    /* dark ships and loitering come only from Global Fishing Watch's waters boxes: outside them a 0 would read as calm, so those
       rows are left out and a line says they are not covered (data without the flag: not covered) */
    const gfw = c.gfw === true
    return { c, gfw, counts: [
      [near(live.ships).length, 'military and coast-guard ships', ''],
      ...(gfw ? [[dark.reduce((s, x) => s + (x.count || 0), 0), 'ships dark on radar', dark.length ? `in ${plural(dark.length, 'radar area', 'radar areas')}` : ''],
        [near(live.loitering).length, 'loitering ships', '']] : []),
      [near(live.warnings).length, 'sea warnings', ''],
      [near(live.incidents).length, 'news reports', '(unverified)'],
    ] as [number, string, string][] }
  }), [live])
  if (!rows.length) return null
  return (
    <section aria-labelledby="g-choke" className="mt-8 border-t border-line px-5 pt-5">
      <h2 id="g-choke" className="text-[19px] font-semibold tracking-[-0.02em] text-fg">Chokepoints</h2>
      <p className="mt-1.5 max-w-[72ch] text-[12.5px] leading-[1.5] text-fg2">What the map data holds within {NM} nautical miles of each strait or canal. These are counts now, with no usual level to compare them with yet, so none of them is marked as unusual.
        <span className="mt-1 block text-[11.5px] text-fg3">Military and coast-guard ships: US Navy positions from USNI News (approximate, weekly) and military or law-enforcement ships heard on AIS. Dark and loitering ships are from Global Fishing Watch, about five days behind, and only in the waters it is asked about. Sea warnings are NGA navigational warnings. News reports are unverified.</span></p>
      <ul className="mt-3.5 grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-3">
        {rows.map(({ c, gfw, counts }) => { const th = brief.theatres.find(t => t.id === c.theatre), empty = counts.every(x => !x[0]); return (
          <li key={c.name} className="flex flex-col rounded-r3 border border-line bg-s1 px-3.5 pb-3 pt-3">
            <h3 className="text-[13.5px] font-medium text-fg">{c.name}</h3>
            <p className="text-[11.5px] text-fg3">{th ? short(th.name) : ''}{th ? ' · ' : ''}within {NM} nm</p>
            {empty ? <p className="mt-2.5 text-[12px] text-fg3">Nothing in the map data within {NM} nm now.</p>
              : <dl className="mt-2">{counts.map(([n, what, src]) => (
                <div key={what} className="flex items-baseline justify-between gap-3 border-t border-line py-[5px] first:border-0">
                  <dt className="min-w-0 text-[12px] leading-[1.3] text-fg2">{what}{src && <span className="text-fg3"> {src}</span>}</dt>
                  <dd className="num shrink-0 text-[15px] font-medium text-fg">{n}</dd>
                </div>))}</dl>}
            {!gfw && <p className="mt-1.5 text-[11.5px] leading-[1.4] text-fg3">Dark ships and loitering are not covered here.</p>}
            <span className="flex-1" />
            <a href={routeHref({ v: 'map' })} onClick={e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); openPlace(c.ll, go) }} className="lnk mt-2 inline-flex items-center gap-1 self-start text-[12px]"><MapPin size={12} aria-hidden />Show on the map</a>
          </li>) })}
      </ul>
    </section>
  )
}
