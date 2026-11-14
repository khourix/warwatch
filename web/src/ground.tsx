import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { Satellite, Flame, Plane, Ship, TriangleAlert, ExternalLink, ImageIcon } from 'lucide-react'
import { focusOnMap } from './sat'
import { useBase, asset, baseState, shortDate, short, ago, parseGen, emergency, heatColour,
  type Brief, type LiveMap, type Route, type BasePart, type BaseFile, type Pic, type MapBase, type Theatre, type AirKey, type MapAirport } from './data'
import { Spark, Lnk, Tag, Facts, Block, Note, Skeleton, Failed, listAnim, useWidth } from './ui'
import { Crumbs } from './views'

/* What is physically happening in a theatre (its Ground tab), and the base dossier. Everything here reads map/live.json,
   theatres/<id>.json (aircraft48h) and bases/<id>.json. */

type Go = (r: Route, replace?: boolean) => void
const THINGS: Record<string, string> = { apron: 'aircraft', harbour: 'ships', ground: 'vehicles' }
const PART_TITLE: Record<string, string> = { apron: 'Aircraft', harbour: 'Ships', ground: 'Vehicles and equipment' }
export const baseWord = (state: string, part?: string) =>
  state === 'out' || state === 'in' ? `${state === 'out' ? 'Fewer' : 'More'} ${THINGS[part || ''] || 'objects'} than usual` : baseState(state)[0]
/* a base's state as a data mark (a dot or the end of its sparkline); the words stay ink */
export const baseMark = (state: string) => state === 'out' || state === 'in' ? 'var(--z3)' : state === 'changed' ? 'var(--z2)' : undefined
const FIRE_WORD: Record<string, string> = { anom: 'Unusual heat', hot: 'Much more heat than usual', unex: 'Heat with no known source', ind: 'Industry or gas flare', seas: 'Farm or grass burning', volc: 'Volcano', off: 'Offshore platform' }
export const fireWord = (c: string) => FIRE_WORD[c] || 'Heat'
export const KIND: Record<string, string> = { air: 'Air base', naval: 'Naval base', 'air+naval': 'Air and naval base', launch: 'Launch site', port: 'Port', missile: 'Missile base', depot: 'Depot', airdef: 'Air defence' }
export const rankBase = (b: MapBase) => (({ out: 5, in: 5, changed: 4, normal: 2, optical: 1, nodata: 0 } as Record<string, number>)[b.state] || 0) * 10 + Math.abs(b.z || 0)

/* ---------------------------------------------------------------- the theatre's Ground tab */
export function GroundTab({ id, t, live, brief, go }: { id: string; t: Theatre; live?: LiveMap; brief: Brief; go: Go }) {
  const now = parseGen(brief.generated)
  const [all, setAll] = useState(false)
  if (!live) return <Skeleton lines={6} />
  const bases = live.bases.filter(b => b.theatres.includes(id)).sort((a, b) => rankBase(b) - rankBase(a) || a.name.localeCompare(b.name))
  const news = live.incidents.filter(x => x.th === id && x.t).sort((a, b) => (b.d || '').localeCompare(a.d || ''))
  const fires = live.fires.filter(f => f.theatre === id).sort((a, b) => b.score - a.score || b.mw - a.mw)
  const ships = live.ships.filter(s => s.th === id)
  const warn = live.warnings.filter(w => w.theatre === id)
  const shown = all ? bases : bases.slice(0, 8)
  return <>
    <Block title="Watched bases" aside="Sentinel-1 radar, about every two days">
      {bases.length === 0 ? <p className="text-[12.5px] text-fg3">No base in this theatre is watched yet.</p>
        : <ul>{shown.map((b, i) => <li key={b.id} className="border-t border-line first:border-0"><BaseRow b={b} i={i} go={go} /></li>)}</ul>}
      {bases.length > 8 && <button onClick={() => setAll(!all)} aria-expanded={all} className="lnk mt-2 text-[12px]">{all ? 'Show the first 8' : `Show all ${bases.length} bases`}</button>}
    </Block>
    {news.length > 0 && <Block title="Reported on the ground" aside="news reports, unverified">
      <ol className="relative ml-[5px] border-l border-line2 pl-4">
        {news.slice(0, 8).map((x, i) => (
          <li key={i} className="relative pb-3 last:pb-0">
            <i aria-hidden className="absolute -left-[20.5px] top-[4px] h-[7px] w-[7px] rounded-full border-[1.5px] border-fg3 bg-s1" />
            <p className="font-mono text-[10.5px] leading-none text-fg3">{[x.d && shortDate(x.d.slice(0, 10)), x.loc, x.src].filter(Boolean).join(' · ')}</p>
            <p className="mt-0.5 text-[12.5px] leading-[1.35] text-fg">{x.u ? <a href={x.u} target="_blank" rel="noreferrer" className="hover:underline hover:decoration-line2 hover:underline-offset-[3px]">{(x.t || '').replace(/ - [^-]*$/, '')}<span className="sr-only"> (opens the report)</span></a> : (x.t || '').replace(/ - [^-]*$/, '')}</p>
          </li>))}
      </ol>
    </Block>}
    <AirPicture id={id} t={t} live={live} />
    {fires.length > 0 && <Block title="Heat, last 48 hours" aside="NASA VIIRS">
      {fires.slice(0, 8).map((f, i) => (
        <motion.button key={i} {...listAnim(i)} onClick={() => focusOnMap({ kind: 'fire', x: f })} className="-mx-2 flex w-[calc(100%+16px)] gap-3 rounded-r2 px-2 py-1.5 text-left text-[12.5px] hover:bg-s2">
          <Flame size={14} aria-hidden className="mt-0.5 shrink-0" style={{ color: heatColour(f.score) }} />
          <span className="min-w-0 flex-1"><span className="flex items-center gap-1.5 text-fg">{f.site ? `Near ${f.site}` : fireWord(f.class)}{f.images && <ImageIcon size={12} className="text-fg3" aria-label="with Sentinel-2 close-ups" />}</span><span className="line-clamp-2 text-[11.5px] text-fg3">{f.why || fireWord(f.class)}</span></span>
          <span className="num shrink-0 text-right text-[11.5px] text-fg3">{Math.round(f.mw)} MW<span className="block">{ago(now, f.date)}{f.night ? ', night' : ''}</span></span>
          <span className="sr-only">Show it on the map</span>
        </motion.button>))}
      <p className="mt-1 text-[11px] text-fg3">Pick one to see it on the map with that day's satellite pass.</p>
    </Block>}
    {(ships.length > 0 || warn.length > 0) && <Block title="At sea" aside={`${ships.length} ${ships.length === 1 ? 'ship' : 'ships'} · ${warn.length} ${warn.length === 1 ? 'warning' : 'warnings'}`}>
      {ships.slice(0, 8).map((s, i) => (
        <div key={'s' + i} className="flex gap-3 py-1.5 text-[12.5px]">
          <Ship size={14} aria-hidden className="mt-0.5 shrink-0 text-cool" />
          <span className="min-w-0 flex-1"><span className="block text-fg">{s.name}</span><span className="block text-[11.5px] text-fg3">{[s.loc, s.note || s.tx].filter(Boolean).join(' · ')}</span></span>
          {s.d && <span className="num shrink-0 text-[11.5px] text-fg3">{shortDate(s.d.slice(0, 10))}</span>}
        </div>))}
      {warn.slice(0, 6).map((w, i) => (
        <div key={'w' + i} className="flex gap-3 py-1.5 text-[12.5px]">
          <TriangleAlert size={14} aria-hidden className="mt-0.5 shrink-0" style={{ color: 'var(--z2)' }} />
          <span className="min-w-0 flex-1 text-fg2"><span className="line-clamp-3">{w.text}</span></span>
          <span className="num shrink-0 text-[11.5px] text-fg3">{w.id}</span>
        </div>))}
    </Block>}
  </>
}

function BaseRow({ b, i, go }: { b: MapBase; i: number; go: Go }) {
  const mark = baseMark(b.state)
  return (
    <motion.div {...listAnim(i)}>
      <Lnk to={{ v: 'base', id: b.id }} go={go} className="group grid grid-cols-[52px_minmax(0,1fr)_74px] items-center gap-3 py-[7px]">
        <span className="grid h-[52px] w-[52px] place-items-center overflow-hidden rounded-r1 bg-s3">{b.thumb ? <img src={asset(b.thumb)} alt="" loading="lazy" className="h-full w-full object-cover" onError={e => { e.currentTarget.style.visibility = 'hidden' }} /> : <Satellite size={16} className="text-fg3" aria-hidden />}</span>
        <span className="min-w-0">
          <span className="block text-[12.5px] font-medium leading-[1.3] text-fg group-hover:underline group-hover:decoration-line2 group-hover:underline-offset-[3px]">{b.name}</span>
          <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-fg3">{mark && <i aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: mark }} />}<span className={mark ? 'text-fg2' : ''}>{baseWord(b.state, b.part)}</span>{b.last && b.state !== 'nodata' ? <span className="num">· last pass {shortDate(b.last)}</span> : null}</span>
        </span>
        <span className="justify-self-end" aria-hidden><Spark v={b.radar} w={70} h={24} stroke="var(--fg3)" dot={mark || 'var(--fg)'} fill={false} /></span>
      </Lnk>
    </motion.div>
  )
}

/* ---------------------------------------------------------------- the air picture */
const AIR: [AirKey, string][] = [['mil', 'All military'], ['fighter', 'Fighters'], ['isr', 'Surveillance'], ['lift', 'Transport'], ['tanker', 'Tankers']]
const LOW = .7
const ratio = (a: MapAirport) => a.usual > 0 ? a.departures / a.usual : Infinity
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

function AirPicture({ id, t, live }: { id: string; t: Theatre; live: LiveMap }) {
  const [allPorts, setAllPorts] = useState(false)
  const ports = (live.airports || []).filter(a => a.theatre === id).sort((a, b) => ratio(a) - ratio(b) || b.usual - a.usual)
  const divs = (live.diversions || []).filter(d => d.theatre === id).sort((a, b) => b.time - a.time)
  const series = AIR.map(([k, label]) => [k, label, (t.aircraft48h?.[k] || []).filter(p => p && p[0])] as const).filter(s => s[2].filter(p => p[1] != null).length > 1)
  const nowAir = [...live.aircraft, ...live.squawks].filter(a => a.th === id)
  const holds = ports.reduce((n, a) => n + (a.holds || 0), 0), biz = ports.reduce((n, a) => n + (a.bizjets || 0), 0), bizOut = ports.reduce((n, a) => n + (a.bizjetsOut || 0), 0)
  const turn = divs.filter(d => d.kind === 'turnback').length
  const nothing = !ports.length && !divs.length && !series.length && !nowAir.length
  const shownPorts = allPorts ? ports : ports.slice(0, 6)
  return (
    <Block title="Air picture" aside={nothing ? undefined : 'adsb.lol and OpenSky; airline flights a day behind'}>
      {nothing && <p className="text-[12.5px] text-fg3">No air data for this theatre.</p>}
      {ports.length > 0 && <>
        <h3 className="mb-1 text-[11.5px] font-medium text-fg2">Airports, departures against usual</h3>
        <ul>{shownPorts.map(a => { const r = ratio(a), low = r < LOW; const week = [a.divertedAway && `${a.divertedAway} diverted away`, a.divertedIn && `${a.divertedIn} diverted in`, a.turnbacks && `${a.turnbacks} turned back`, a.holds && `${a.holds} held`, a.bizjets && `${a.bizjets} business ${a.bizjets === 1 ? 'jet' : 'jets'} out${a.bizjetsOut ? `, ${a.bizjetsOut} abroad` : ''}`].filter(Boolean)
          return (
            <li key={a.icao} className="border-t border-line py-1.5 first:border-0">
              <div className="flex items-baseline justify-between gap-3 text-[12.5px]">
                <span className="flex min-w-0 items-center gap-1.5 text-fg">{low && <i aria-hidden className="h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full bg-z2" />}<span className="truncate">{a.name}</span></span>
                <span className="num shrink-0 text-right text-fg">{a.departures} <span className="text-fg3">{a.usual >= 1 ? `of ${Math.round(a.usual)}` : 'with no usual count'}</span></span>
              </div>
              <p className="text-[11px] leading-[1.35] text-fg3">{a.icao} · {shortDate(a.date)}{low ? <span className="text-fg2"> · below 70% of usual</span> : ''}{week.length ? ` · last 7 days: ${week.join(', ')}` : ''}</p>
            </li>) })}
        </ul>
        {ports.length > 6 && <button onClick={() => setAllPorts(!allPorts)} aria-expanded={allPorts} className="lnk mt-1 text-[12px]">{allPorts ? 'Show the first 6' : `Show all ${ports.length} airports`}</button>}
      </>}
      {(divs.length > 0 || holds > 0 || biz > 0) && <div className={ports.length ? 'mt-3' : ''}>
        <h3 className="mb-1 text-[11.5px] font-medium text-fg2">Diversions, holds and business jets</h3>
        {divs.length > 0 && <p className="text-[12px] leading-[1.45] text-fg2">Since {shortDate(divs.reduce((m, d) => d.date < m ? d.date : m, divs[0].date))}: {[divs.length - turn > 0 && plural(divs.length - turn, 'flight diverted', 'flights diverted'), turn > 0 && `${turn} turned back`].filter(Boolean).join(' · ')}.</p>}
        {(holds > 0 || biz > 0) && <p className="text-[12px] leading-[1.45] text-fg2">Last 7 days at these airports: {[holds > 0 && `${holds} held before landing`, biz > 0 && `${plural(biz, 'business-jet departure', 'business-jet departures')}${bizOut ? `, ${bizOut} abroad` : ''}`].filter(Boolean).join(' · ')}.</p>}
        {divs.length > 0 && <ul className="mt-1">{divs.slice(0, 4).map((d, i) => (
          <li key={i} className="flex justify-between gap-3 py-[3px] text-[11.5px]"><span className="min-w-0 truncate text-fg2"><span className="text-fg">{d.call}</span>{d.type ? ` · ${d.type}` : ''} · {d.kind === 'turnback' ? `turned back to ${d.landed}` : `${d.from} to ${d.planned}, landed ${d.landed}`}</span><span className="num shrink-0 text-fg3">{shortDate(d.date)}</span></li>))}</ul>}
      </div>}
      {series.length > 0 && <div className={ports.length || divs.length ? 'mt-3.5' : ''}><AirCharts series={series} /></div>}
      {nowAir.length > 0 && <div className="mt-3">
        <h3 className="mb-1 text-[11.5px] font-medium text-fg2">Broadcasting now</h3>
        {nowAir.slice(0, 6).map((a, i) => (
          <div key={i} className="flex items-center gap-2.5 py-1 text-[12px]">
            <Plane size={13} aria-hidden className="shrink-0" style={{ color: emergency(a) ? 'var(--crit)' : 'var(--cool)', transform: `rotate(${(a.trk ?? 45) - 45}deg)` }} />
            <span className="min-w-0 flex-1 truncate"><span className="text-fg">{a.call || a.hex || 'Unknown'}</span><span className="text-fg3"> · {[a.t, a.o || a.ct].filter(Boolean).join(' · ')}</span></span>
            <span className="num shrink-0 text-[11.5px] text-fg3">{a.sq ? `squawk ${a.sq}` : a.alt != null ? `${Math.round(a.alt / 100) * 100} ft` : ''}</span>
          </div>))}
      </div>}
      {!nothing && <p className="mt-2.5 text-[11px] leading-[1.45] text-fg3">Most military aircraft fly with their transponder off, so none seen is not none there.</p>}
    </Block>
  )
}

/* Five small lines on one time axis: military aircraft broadcasting over the theatre, about every half hour for 48 hours */
const tms = (s: string) => Date.parse(s.length <= 16 ? s + 'Z' : s)
function AirCharts({ series }: { series: (readonly [AirKey, string, [string, number | null][]])[] }) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const t0 = Math.min(...series.map(s => tms(s[2][0][0]))), t1 = Math.max(...series.map(s => tms(s[2][s[2].length - 1][0])))
  const span = t1 - t0 || 1, H = 26, labelW = 84, valW = 26, w = Math.max(40, W - labelW - valW - 16)
  const X = (s: string) => ((tms(s) - t0) / span) * (w - 4) + 2
  const hh = (ms: number) => new Date(ms).toISOString().slice(11, 16)
  return (
    <div ref={ref}>
      <h3 className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3 text-[11.5px] font-medium text-fg2">Military aircraft broadcasting, last 48 hours<span className="font-normal text-fg3">count per run</span></h3>
      {W > 0 && series.map(([k, label, pts]) => {
        const vals = pts.map(p => p[1]).filter((v): v is number => v != null), max = Math.max(1, ...vals), last = [...pts].reverse().find(p => p[1] != null)?.[1] ?? null
        const Y = (v: number) => H - 2 - (v / max) * (H - 5)
        const d = pts.filter(p => p[1] != null).map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]!).toFixed(1)}`).join('')
        const lp = [...pts].reverse().find(p => p[1] != null)
        return (
          <div key={k} className="grid items-center gap-2" style={{ gridTemplateColumns: `${labelW}px ${w}px ${valW}px` }}>
            <span className="text-[11.5px] text-fg2">{label}</span>
            <svg width={w} height={H} role="img" aria-label={`${label}: ${last ?? 'no count'} at the latest run; highest ${Math.max(0, ...vals)}, lowest ${vals.length ? Math.min(...vals) : 0} in 48 hours`} className="block overflow-visible">
              <line x1={0} x2={w} y1={H - 2} y2={H - 2} stroke="var(--line)" />
              <path d={d} fill="none" stroke="var(--fg2)" strokeWidth={1.3} strokeLinejoin="round" />
              {lp && <circle cx={X(lp[0])} cy={Y(lp[1]!)} r={2.2} fill="var(--fg)" />}
            </svg>
            <span className="num text-right text-[12px] font-medium text-fg">{last ?? '–'}</span>
          </div>)
      })}
      {W > 0 && <div className="mt-0.5 grid gap-2 font-mono text-[9.5px] leading-none text-fg3" style={{ gridTemplateColumns: `${labelW}px ${w}px ${valW}px` }} aria-hidden>
        <span /><span className="flex justify-between"><span>{shortDate(new Date(t0).toISOString().slice(0, 10))} {hh(t0)}</span><span>{hh(t1)} UTC</span></span><span className="text-right">now</span>
      </div>}
    </div>
  )
}

/* ---------------------------------------------------------------- Base dossier */
export function BaseView({ id, brief, live, go }: { id: string; brief: Brief; live?: LiveMap; go: Go }) {
  const q = useBase(id)
  const mb = live?.bases.find(b => b.id === id)
  const th = (q.data?.theatres || mb?.theatres || [])[0]
  const thName = th ? short(brief.theatres.find(t => t.id === th)?.name || th) : null
  const back: Route = th ? { v: 'theatre', id: th, tab: 'ground' } : { v: 'brief' }
  const crumbs = <Crumbs back={back} items={[['Watch', { v: 'brief' }], ...(th && thName ? [[thName, { v: 'theatre', id: th, tab: 'ground' }] as [string, Route]] : []), ['Base']]} go={go} />
  if (q.isPending) return <>{crumbs}<h1 className="px-5 pt-2 text-[23px] font-semibold tracking-[-0.028em]">{mb?.name || 'Base'}</h1><Skeleton lines={8} /></>
  if (q.isError && !mb) return <>{crumbs}<h1 className="px-5 pt-2 text-[23px] font-semibold tracking-[-0.028em]">Base</h1><Failed what="this base" error={q.error} /></>
  return q.data ? <BaseFull b={q.data} mb={mb} crumbs={crumbs} th={th} thName={thName} go={go} /> : <BaseLite b={mb!} crumbs={crumbs} />
}

function BaseHead({ name, state, part, kind, side, why }: { name: string; state: string; part?: string; kind: string; side: string; why: string }) {
  return (
    <div className="px-5 pb-3.5 pt-2">
      <h1 className="text-[23px] font-semibold leading-[1.15] tracking-[-0.028em]">{name}</h1>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Tag mark={baseMark(state)}>{baseWord(state, part)}</Tag>
        <Tag>{KIND[kind] || kind || 'Site'}</Tag>
        {side && <Tag>{side}</Tag>}
      </div>
      <p className="mt-3 font-serif text-[16.5px] leading-[1.42] text-fg [text-wrap:pretty]">{why ? whyText(why) : 'No radar reading for this base yet.'}</p>
    </div>
  )
}
/* ISO dates in the pipeline's sentences read as "10 Nov"; the "not yet checked" clause moves to the closing note */
export const plainDates = (s: string) => s.replace(/\b(\d{4}-\d{2}-\d{2})\b/g, (_, d) => shortDate(d))
const whyText = (s: string) => plainDates(s.split(/ Not yet checked/)[0])
const coords = (ll: [number, number]) => <span className="font-mono">{ll[1].toFixed(3)}, {ll[0].toFixed(3)}</span>

/* a base whose own file is missing: what the map knows */
function BaseLite({ b, crumbs }: { b: MapBase; crumbs: ReactNode }) {
  return <>
    {crumbs}
    <BaseHead name={b.name} state={b.state} part={b.part} kind={b.kind} side={b.side} why={b.why} />
    {b.thumb && <><div className="mx-5 overflow-hidden rounded-r2 bg-black"><img src={asset(b.thumb)} alt={`Latest radar image of ${b.name}`} className="block w-full" /></div>
      <p className="mx-5 mt-1.5 text-[11px] leading-[1.45] text-fg3">Latest Sentinel-1 radar image. Bright points are metal objects.</p></>}
    <div className="mt-3 border-t border-line" />
    {b.radar.length > 1 && <Block title="Radar on each pass" aside={`last ${b.radar.length} passes, band is the usual range`}><RadarSpark v={b.radar} mark={baseMark(b.state)} /></Block>}
    <Note><b>What this does not say.</b> A change on radar is a reason to look, not proof. Coordinates {coords(b.ll)}.</Note>
  </>
}
function RadarSpark({ v, mark }: { v: number[]; mark?: string }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  return <div ref={ref} role="img" aria-label={`Radar reading against this base's usual on the last ${v.length} passes; latest ${v[v.length - 1]?.toFixed(1)} standard deviations`} style={{ height: 60 }}>{w > 0 && <Spark v={v} w={w} h={60} stroke="var(--fg2)" band={[-1, 1]} dot={mark || 'var(--fg)'} fill={false} />}</div>
}

function BaseFull({ b, mb, crumbs, th, thName, go }: { b: BaseFile; mb?: MapBase; crumbs: ReactNode; th?: string; thName: string | null; go: Go }) {
  const main = Math.max(0, b.parts.findIndex(p => p.part === b.mainPart))
  const [sel, setSel] = useState(main)
  const [optical, setOptical] = useState(false)
  const p: BasePart | undefined = b.parts[sel]
  const radarPair: [Pic, Pic] | null = p?.images.marked ? [p.images.before, p.images.marked] : b.images.radar ? [b.images.radarBefore, b.images.radar] : null
  const optPair: [Pic, Pic] | null = b.images.optical ? [b.images.opticalBefore, b.images.optical] : null
  const showOpt = optical && !!optPair || (!radarPair && !!optPair)
  const pair = showOpt ? optPair : radarPair
  const hot = baseMark(p?.state || b.state)
  return (
    <div>
      {crumbs}
      <BaseHead name={b.name} state={b.state} part={b.mainPart} kind={b.type} side={b.side} why={b.why} />
      {pair ? <>
        {radarPair && optPair && <div className="mx-5 mb-2 flex items-center justify-between gap-2">
          <span className="inline-flex rounded-r2 border border-line p-0.5 text-[11.5px]" role="group" aria-label="Kind of image">
            {([[false, 'Radar'], [true, 'Optical']] as const).map(([k, l]) => <button key={l} aria-pressed={showOpt === k} onClick={() => setOptical(k)} className={`rounded-[6px] px-2 py-0.5 transition-colors duration-[120ms] ${showOpt === k ? 'bg-s3 text-fg' : 'text-fg3 hover:text-fg2'}`}>{l}</button>)}
          </span>
          {b.parts.length > 1 && !showOpt && p && <span className="truncate text-[11.5px] text-fg3">{PART_TITLE[p.part] || p.what} {p.where}</span>}
        </div>}
        <Compare before={pair[0]} after={pair[1]} what={showOpt ? 'Sentinel-2 optical image' : 'Sentinel-1 radar image'} name={b.name.split(',')[0]} />
        <p className="mx-5 mt-1.5 text-[11px] leading-[1.45] text-fg3">
          {pair[0] ? 'Drag the divider, or focus it and use the arrow keys, to compare. ' : ''}
          {showOpt ? 'Sentinel-2 optical, 10 m. Clouds and night hide it; radar sees through both.'
            : `Sentinel-1 radar: bright points are metal objects such as vehicles and aircraft.${p?.marks && p.images.marked ? ` ${p.marks.objects} ${p.marks.objects === 1 ? 'object' : 'objects'} on the latest pass${p.marks.gone != null && p.marks.new != null ? `, ${p.marks.gone} gone and ${p.marks.new} new since ${shortDate(p.marks.before)}` : ''}.` : ''}`}
          {' '}Contains modified Copernicus Sentinel data.</p>
      </> : mb?.thumb ? <>
        <div className="mx-5 overflow-hidden rounded-r2 bg-black"><img src={asset(mb.thumb)} alt={`Latest radar image of ${b.name}`} className="block w-full" /></div>
        <p className="mx-5 mt-1.5 text-[11px] leading-[1.45] text-fg3">Latest Sentinel-1 radar image. Bright points are metal objects.</p>
      </> : <p className="px-5 text-[12.5px] text-fg3">No image of this base yet. Images arrive with the next imagery run.</p>}
      <div className="mt-2 border-t border-line" />
      {p ? <PassBlock p={p} hot={hot} /> : b.radar.length > 1 && <Block title="Radar on each pass" aside={`last ${b.radar.length} passes, band is the usual range`}><RadarSpark v={b.radar} mark={baseMark(b.state)} /></Block>}
      {b.parts.length > 1 && <Block title="Parts of the base">
        <ul role="group" aria-label="Parts of the base">{b.parts.map((q, i) => { const m = baseMark(q.state); return (
          <li key={q.part} className="border-t border-line first:border-0">
            <button aria-pressed={i === sel} onClick={() => { setSel(i); setOptical(false) }} className={`-mx-2 flex w-[calc(100%+16px)] items-baseline justify-between gap-3 rounded-r1 px-2 py-1.5 text-left text-[12.5px] ${i === sel ? 'bg-s2 shadow-[inset_2px_0_0_var(--sel)]' : 'hover:bg-s2'}`}>
              <span className={i === sel ? 'font-medium text-fg' : 'text-fg2'}>{PART_TITLE[q.part] || q.what} <span className="font-normal text-fg3">{q.where}</span></span>
              <span className="flex shrink-0 items-center gap-1.5 text-right text-fg2">{m && <i aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ background: m }} />}{baseWord(q.state, q.part)}{q.now != null && q.usual != null ? <span className="num text-fg3"> · {Math.round(q.now)} of {Math.round(q.usual)}</span> : null}</span>
            </button>
          </li>) })}
        </ul>
      </Block>}
      {(b.about || b.note) && <Block title="Why this base is watched">
        {b.about && <p className="text-[12.5px] leading-[1.5] text-fg2">{b.about}</p>}
        {b.note && <p className="mt-1.5 text-[12px] leading-[1.5] text-fg3">{plainDates(b.note)}</p>}
      </Block>}
      <Note><b>What this does not say.</b> A change on radar is a reason to look, not proof. One pass far outside the usual range marks a base as changed; two passes in a row within a week, both far below or both far above it, mark it as fewer or more than usual.
        {p && !p.tested ? ' This count is not yet tested against past events, so it carries no weight in the unusual readings.' : ''} Coordinates {coords(b.ll)}.</Note>
      <div className="flex flex-wrap gap-2 px-5 pb-6">
        <a href={`https://browser.dataspace.copernicus.eu/?zoom=14&lat=${b.ll[1]}&lng=${b.ll[0]}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-r2 border border-line px-3 py-1.5 text-[12.5px] text-fg2 hover:bg-s2">Copernicus Browser <ExternalLink size={12} aria-hidden /></a>
        {th && thName && <Lnk to={{ v: 'theatre', id: th, tab: 'ground' }} go={go} className="inline-flex items-center gap-1.5 rounded-r2 bg-sel px-3 py-1.5 text-[12.5px] font-medium text-selink">Open {thName}</Lnk>}
      </div>
    </div>
  )
}

function PassBlock({ p, hot }: { p: BasePart; hot?: string }) {
  const r = (v: number | null) => v == null ? '–' : Math.round(v)
  return (
    <Block title={`${PART_TITLE[p.part] || p.what} counted per pass`} aside={p.tested ? 'band is the usual range' : 'band is the usual range · not yet tested'}>
      <PassChart p={p} hot={hot} marked={p.state === 'out' || p.state === 'in' ? 2 : p.state === 'changed' ? 1 : 0} />
      <Facts className="mt-2" items={[[r(p.now), 'on the latest pass'], [r(p.usual), 'usual'], [p.low != null && p.high != null ? `${r(p.low)}–${r(p.high)}` : '–', 'usual range']]} />
    </Block>
  )
}

/* Count on each pass, the usual range as a band and the usual as a dashed line; the last two passes carry the base's mark */
/* marked: how many of the last passes made the state (basewatch.state: two for fewer or more than usual, one for changed) */
function PassChart({ p, hot, marked }: { p: BasePart; hot?: string; marked: number }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const h = useMemo(() => p.history.filter(x => x[1] != null), [p])
  const hh = 132, L = 30, R = 6, T = 10, B = 20
  const geo = useMemo(() => {
    if (h.length < 2 || w < 60) return null
    const vals = h.flatMap(x => [x[1], x[2], x[3], x[4]].filter((v): v is number => v != null))
    const mn = Math.min(...vals) * .92, mx = Math.max(...vals) * 1.04 || 1
    const X = (i: number) => L + (i / (h.length - 1)) * (w - L - R), Y = (v: number) => T + (1 - (v - mn) / (mx - mn || 1)) * (hh - T - B)
    const bd = h.map((x, i) => [i, x[3], x[4]] as const).filter(x => x[1] != null && x[2] != null)
    const band = bd.length > 1 ? bd.map(x => `${X(x[0]).toFixed(1)},${Y(x[2]!).toFixed(1)}`).join(' ') + ' ' + [...bd].reverse().map(x => `${X(x[0]).toFixed(1)},${Y(x[1]!).toFixed(1)}`).join(' ') : ''
    const usual = h.map((x, i) => [i, x[2]] as const).filter(x => x[1] != null).map(x => `${X(x[0]).toFixed(1)},${Y(x[1]!).toFixed(1)}`).join(' ')
    const line = h.map((x, i) => `${X(i).toFixed(1)},${Y(x[1]).toFixed(1)}`).join(' ')
    return { X, Y, mn, mx, band, usual, line }
  }, [h, w])
  const out = h.filter(x => x[3] != null && x[4] != null && (x[1] < x[3] || x[1] > x[4])).length
  const lastV = h.length ? h[h.length - 1][1] : null
  const label = h.length < 2 ? 'Too few passes to draw.' : `${PART_TITLE[p.part] || p.what} counted on each of the last ${h.length} passes, ${shortDate(h[0][0])} to ${shortDate(h[h.length - 1][0])}: ${lastV} on the latest pass${p.usual != null ? `, against a usual ${Math.round(p.usual)}` : ''}${p.low != null && p.high != null ? ` (range ${Math.round(p.low)} to ${Math.round(p.high)})` : ''}. Outside the usual range on ${out} of ${h.length} passes.`
  return (
    <div ref={ref} style={{ minHeight: h.length > 1 ? hh : undefined }}>
      {h.length < 2 ? <p className="text-[12px] text-fg3">Too few passes to draw yet.</p> : geo && <svg width={w} height={hh} role="img" aria-label={label} className="block">
        {geo.band && <polygon points={geo.band} fill="color-mix(in srgb, var(--fg3) 16%, transparent)" />}
        {geo.usual && <polyline points={geo.usual} fill="none" stroke="var(--fg3)" strokeWidth={1} strokeDasharray="3 3" />}
        <polyline points={geo.line} fill="none" stroke="var(--fg)" strokeWidth={1.4} strokeLinejoin="round" />
        {h.map((x, i) => { const m = marked > 0 && !!hot && i >= h.length - marked, last = i === h.length - 1; return <circle key={i} cx={geo.X(i)} cy={geo.Y(x[1])} r={m ? 3.4 : last ? 2.8 : 1.7} fill={m ? hot : 'var(--fg)'} /> })}
        <text x={L - 6} y={geo.Y(geo.mx) + 8} textAnchor="end" fontSize={9.5} fill="var(--fg3)" fontFamily="var(--font-mono)">{Math.round(geo.mx)}</text>
        <text x={L - 6} y={geo.Y(geo.mn)} textAnchor="end" fontSize={9.5} fill="var(--fg3)" fontFamily="var(--font-mono)">{Math.round(geo.mn)}</text>
        <text x={L} y={hh - 5} fontSize={9.5} fill="var(--fg3)" fontFamily="var(--font-mono)">{shortDate(h[0][0])}</text>
        <text x={w - R} y={hh - 5} textAnchor="end" fontSize={9.5} fill="var(--fg3)" fontFamily="var(--font-mono)">{shortDate(h[h.length - 1][0])}</text>
        <text x={geo.X(h.length - 1) - 9} y={Math.max(16, Math.min(hh - B - 4, geo.Y(h[h.length - 1][1]) + 4))} textAnchor="end" fontSize={10.5} fontWeight={500} fill="var(--fg)" stroke="var(--s1)" strokeWidth={3} paintOrder="stroke">{Math.round(h[h.length - 1][1])} now</text>
      </svg>}
    </div>
  )
}

/* Before on the left of the divider, the latest pass under it on the right. Drag anywhere on the picture (mouse or touch; a
   vertical swipe still scrolls), or focus the handle and use the arrow keys (Shift for larger steps), Home and End. */
/* className places it (a dossier's 20 px margins by default); lazy defers the pictures until they near the screen (a long list).
   A picture that fails to load is dropped: without the before, the latest shows alone; without the latest, a quiet line says so. */
export function Compare({ before: b0, after, what, name, className = 'mx-5', lazy = false, words = ['Before', 'Now'] }: { before: Pic; after: Pic; what: string; name: string; className?: string; lazy?: boolean; words?: [string, string] }) {
  const [pos, setPos] = useState(50)
  const [bad, setBad] = useState<{ a?: boolean; b?: boolean }>({})
  const before = bad.b ? null : b0
  const load = lazy ? 'lazy' as const : undefined, fit = lazy ? 'aspect-square object-cover' : ''   // lazy: square chips (the fire close-ups), sized before they load
  const box = useRef<HTMLDivElement>(null), drag = useRef(false)
  /* a touch waits to see which way it goes: sideways moves the divider, up or down is left to scroll the page; a tap moves it there */
  const touch = useRef<{ x: number; y: number; id: number; moved: boolean } | null>(null)   // moved: it became a drag
  if (!after) return null
  if (bad.a) return <div className={`${className} grid aspect-square place-items-center rounded-r2 bg-s3 px-4 text-center text-[11.5px] text-fg2`}>The picture of {shortDate(after.date)} is not available.</div>
  const at = (e: PointerEvent) => { const r = box.current!.getBoundingClientRect(); setPos(Math.round(Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100)))) }
  const key = (e: KeyboardEvent) => {
    const step = e.shiftKey ? 10 : 2
    const to = e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? pos - step : e.key === 'ArrowRight' || e.key === 'ArrowUp' ? pos + step : e.key === 'PageDown' ? pos - 10 : e.key === 'PageUp' ? pos + 10 : e.key === 'Home' ? 0 : e.key === 'End' ? 100 : null
    if (to == null) return
    e.preventDefault(); setPos(Math.max(0, Math.min(100, to)))
  }
  const label = 'font-mono absolute top-2 rounded-[3px] bg-black/75 px-1.5 py-1 text-[10.5px] font-medium leading-none text-white'
  if (!before) return (
    <div className={`relative ${className} overflow-hidden rounded-r2 bg-black`}>
      <img src={asset(after.src)} alt={`${what} of ${name}, ${shortDate(after.date)}`} loading={load} onError={() => setBad(x => ({ ...x, a: true }))} className={`block w-full ${fit}`} />
      <span className={`${label} right-2`}>{words[1]} · {shortDate(after.date)}</span>
    </div>)
  return (
    <div ref={box} className={`relative ${className} cursor-ew-resize select-none overflow-hidden rounded-r2 bg-black`} style={{ touchAction: 'pan-y' }}
      onPointerDown={e => {
        if (e.button) return
        if (e.pointerType !== 'mouse') { touch.current = { x: e.clientX, y: e.clientY, id: e.pointerId, moved: false }; return }
        drag.current = true; box.current?.setPointerCapture(e.pointerId); at(e)
      }}
      onPointerMove={e => {
        const t = touch.current
        if (t && !drag.current) {
          const dx = Math.abs(e.clientX - t.x), dy = Math.abs(e.clientY - t.y)
          if (dy > 8 && dy >= dx) { touch.current = null; return }          // a scroll: leave the divider alone
          if (dx > 8 && dx > dy) { drag.current = true; t.moved = true; try { box.current?.setPointerCapture(t.id) } catch { /* pointer gone */ } }
          else return
        }
        if (drag.current) at(e)
      }}
      onPointerUp={e => { const t = touch.current; if (t && !t.moved && !drag.current) at(e); drag.current = false; touch.current = null }}
      onPointerCancel={() => { drag.current = false; touch.current = null }}>
      <img src={asset(after.src)} alt={`${what} of ${name}, latest pass, ${shortDate(after.date)}`} draggable={false} loading={load} onError={() => setBad(x => ({ ...x, a: true }))} className={`pointer-events-none block w-full ${fit}`} />
      <img src={asset(before.src)} alt={`${what} of ${name}, earlier pass, ${shortDate(before.date)}`} draggable={false} loading={load} onError={() => setBad(x => ({ ...x, b: true }))} className="pointer-events-none absolute inset-0 h-full w-full object-cover" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} />
      <span className={`${label} left-2`}>{words[0]} · {shortDate(before.date)}</span>
      <span className={`${label} right-2`}>{words[1]} · {shortDate(after.date)}</span>
      <div className="pointer-events-none absolute inset-y-0 w-[2px] -translate-x-1/2 bg-white shadow-[0_0_0_1px_rgba(0,0,0,.4)]" style={{ left: `${pos}%` }}>
        <span role="slider" tabIndex={0} aria-label="Compare the earlier and the latest pass" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pos}
          aria-valuetext={`${pos}% of the picture shows the earlier pass of ${shortDate(before.date)}, the rest the latest of ${shortDate(after.date)}`} onKeyDown={key}
          className="pointer-events-auto absolute left-1/2 top-1/2 h-[26px] w-[26px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-[0_2px_10px_rgba(0,0,0,.5)] focus-visible:shadow-[0_0_0_3px_#000,0_0_0_5px_#fff] focus-visible:outline-none" />
      </div>
    </div>
  )
}
