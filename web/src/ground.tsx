import { useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { Satellite, Flame, Plane, Ship, TriangleAlert, ExternalLink, Radar, ArrowLeft, ChevronRight, ImageIcon } from 'lucide-react'
import { focusOnMap } from './sat'
import { useBase, asset, baseState, shortDate, ago, parseGen, type Brief, type LiveMap, type Route, type BasePart, type Pic, type MapBase } from './data'
import { Spark, Section, Skeleton, Failed, listAnim } from './ui'

/* PR 4: what is physically happening in a theatre (bases on satellite radar, aircraft, ships, fires, navigational warnings),
   and the Base view with the radar passes under a compare slider. Everything here reads map/live.json and bases/<id>.json. */

type Go = (r: Route) => void
const THINGS: Record<string, string> = { apron: 'aircraft', harbour: 'ships', ground: 'vehicles' }
const PART_TITLE: Record<string, string> = { apron: 'Aircraft on the aprons', harbour: 'Ships in the harbour', ground: 'Vehicles and equipment on the base' }
const SHORT: Record<string, string> = { apron: 'Aircraft', harbour: 'Ships', ground: 'Vehicles' }
export const baseWord = (state: string, part?: string) =>
  state === 'out' || state === 'in' ? `${state === 'out' ? 'Fewer' : 'More'} ${THINGS[part || ''] || 'objects'} than usual` : baseState(state)[0]
const FIRE_WORD: Record<string, string> = { anom: 'Unusual heat', hot: 'Much more heat than usual', unex: 'Heat with no known source', ind: 'Industry or gas flare', seas: 'Farm or grass burning', volc: 'Volcano', off: 'Offshore platform' }
export const fireWord = (c: string) => FIRE_WORD[c] || 'Heat'
export const fireColour = (c: string) => c === 'anom' || c === 'hot' ? 'var(--elev)' : c === 'unex' ? 'var(--watch)' : 'var(--fg-3)'

/* ---------------------------------------------------------------- the theatre's "On the ground" tab */
export function GroundTab({ id, live, brief, go }: { id: string; live?: LiveMap; brief: Brief; go: Go }) {
  const now = parseGen(brief.generated)
  const [all, setAll] = useState(false)
  if (!live) return <Skeleton lines={6} />
  const bases = live.bases.filter(b => b.theatres.includes(id)).sort((a, b) => rankBase(b) - rankBase(a) || a.name.localeCompare(b.name))
  const fires = live.fires.filter(f => f.theatre === id).sort((a, b) => b.score - a.score || b.mw - a.mw)
  const air = [...live.aircraft, ...live.squawks].filter(a => a.th === id)
  const ships = live.ships.filter(s => s.th === id)
  const warn = live.warnings.filter(w => w.theatre === id)
  const changed = bases.filter(b => ['out', 'in', 'changed'].includes(b.state)).length
  const shown = all ? bases : bases.slice(0, 6)
  return <>
    <Section title="Bases watched by satellite" aside={`${bases.length} sites${changed ? ` · ${changed} changed` : ''}`}>
      {bases.length === 0 && <p className="text-[13px] text-fg3">No base in this theatre is watched yet.</p>}
      <div className="grid gap-2">
        {shown.map((b, i) => <BaseRow key={b.id} b={b} i={i} go={go} />)}
      </div>
      {bases.length > 6 && <button onClick={() => setAll(!all)} className="mt-2 text-[12.5px] text-accent hover:underline">{all ? 'Show fewer' : `Show all ${bases.length}`}</button>}
    </Section>
    <Section title="Fires and heat, last 48 hours" aside="NASA VIIRS">
      {fires.length === 0 && <p className="text-[13px] text-fg3">No fire detected in this theatre in the last 48 hours.</p>}
      {fires.slice(0, 12).map((f, i) => (
        <motion.button key={i} {...listAnim(i)} onClick={() => focusOnMap({ kind: 'fire', x: f })} title="Show it on the map, with the satellite pictures" className="-mx-2 flex w-[calc(100%+16px)] gap-3 rounded-lg px-2 py-1.5 text-left text-[12.5px] hover:bg-hover">
          <Flame size={14} className="mt-0.5 shrink-0" style={{ color: fireColour(f.class) }} />
          <span className="min-w-0 flex-1"><span className="flex items-center gap-1.5 text-fg">{f.site ? `Near ${f.site}` : fireWord(f.class)}{f.images && <ImageIcon size={12} className="text-fg3" aria-label="Sentinel-2 close-up" />}</span><span className="block text-fg3">{f.why || fireWord(f.class)}</span></span>
          <span className="num shrink-0 text-right text-fg3">{Math.round(f.mw)} MW<span className="block text-[11px]">{ago(now, f.date)}{f.night ? ', night' : ''}</span></span>
        </motion.button>
      ))}
      {fires.length > 0 && <p className="mt-1 text-[11.5px] text-fg3">Pick a fire to see it on the map with that day's satellite pass and, where checked, the Sentinel-2 close-ups.</p>}
    </Section>
    <Section title="Military aircraft seen now" aside="adsb.lol, OpenSky">
      {air.length === 0 ? <p className="text-[13px] text-fg3">None broadcasting over this theatre at the last run. Most military aircraft fly with their transponder off, so none seen is not none there.</p>
        : air.slice(0, 12).map((a, i) => (
          <div key={i} className="flex items-center gap-3 py-1.5 text-[12.5px]">
            <Plane size={14} className="shrink-0" style={{ color: a.emergency || a.sq ? 'var(--elev)' : 'var(--fg-2)', transform: `rotate(${(a.trk ?? 45) - 45}deg)` }} />
            <span className="min-w-0 flex-1 truncate"><span className="text-fg">{a.call || a.hex || 'Unknown'}</span><span className="text-fg3"> · {[a.t, a.o || a.ct].filter(Boolean).join(' · ')}</span></span>
            <span className="num shrink-0 text-fg3">{a.sq ? `squawk ${a.sq}` : a.alt != null ? `${Math.round(a.alt / 100) * 100} ft` : ''}</span>
          </div>))}
    </Section>
    {(ships.length > 0 || warn.length > 0) && <Section title="At sea" aside={`${ships.length} ships · ${warn.length} warnings`}>
      {ships.slice(0, 10).map((s, i) => (
        <div key={'s' + i} className="flex gap-3 py-1.5 text-[12.5px]">
          <Ship size={14} className="mt-0.5 shrink-0 text-fg2" />
          <span className="min-w-0 flex-1"><span className="block text-fg">{s.name}</span><span className="block text-fg3">{[s.loc, s.note || s.tx].filter(Boolean).join(' · ')}</span></span>
          {s.d && <span className="num shrink-0 text-fg3">{shortDate(s.d.slice(0, 10))}</span>}
        </div>))}
      {warn.slice(0, 10).map((w, i) => (
        <div key={'w' + i} className="flex gap-3 py-1.5 text-[12.5px]">
          <TriangleAlert size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--watch)' }} />
          <span className="min-w-0 flex-1 text-fg2"><span className="line-clamp-3">{w.text}</span></span>
          <span className="num shrink-0 text-fg3">{w.id}</span>
        </div>))}
    </Section>}
  </>
}
const rankBase = (b: MapBase) => ({ out: 4, in: 4, changed: 3, normal: 1 } as Record<string, number>)[b.state] || 0

function BaseRow({ b, i, go }: { b: MapBase; i: number; go: Go }) {
  const [txt, col] = [baseWord(b.state, b.part), baseState(b.state)[1]]
  return (
    <motion.button {...listAnim(i)} onClick={() => go({ v: 'base', id: b.id })} className="flex min-w-0 items-center gap-3 rounded-xl border border-line p-2 text-left hover:border-line2 hover:bg-hover">
      <span className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-raised">{b.thumb ? <img src={asset(b.thumb)} alt="" loading="lazy" className="h-full w-full object-cover" /> : <Satellite size={18} className="text-fg3" />}</span>
      <span className="min-w-0 flex-1"><span className="block truncate text-[13.5px] font-medium">{b.name}</span><span className="block text-[12px]" style={{ color: col }}>{txt}</span><span className="block text-[11.5px] text-fg3">{b.last ? `Last pass ${shortDate(b.last)}` : 'No pass yet'}</span></span>
      <Spark v={b.radar} w={70} h={26} stroke={col} band={[-1, 1]} fill={false} />
    </motion.button>
  )
}

/* ---------------------------------------------------------------- Base view */
export function BaseView({ id, brief, go }: { id: string; brief: Brief; go: Go }) {
  const q = useBase(id)
  const name = (x: string) => brief.theatres.find(t => t.id === x)?.name || x
  const [mode, setMode] = useState<string>('')
  const head = (title: string, th?: string) => (
    <div className="flex items-center gap-2 px-5 pt-4 text-[12.5px] text-fg3">
      <button onClick={() => go(th ? { v: 'theatre', id: th, tab: 'ground' } : { v: 'brief' })} aria-label="Back" className="-ml-1.5 grid h-7 w-7 place-items-center rounded-md hover:bg-hover hover:text-fg"><ArrowLeft size={15} /></button>
      {th && <><button onClick={() => go({ v: 'theatre', id: th, tab: 'ground' })} className="hover:text-fg">{name(th)}</button><ChevronRight size={12} className="opacity-50" /><span>Bases</span><ChevronRight size={12} className="opacity-50" /></>}
      <span className="truncate text-fg2">{title}</span>
    </div>)
  if (q.isPending) return <>{head('Base')}<Skeleton lines={8} /></>
  if (q.isError) return <>{head('Base')}<Failed what="this base" error={q.error} /></>
  const b = q.data
  const th = b.theatres[0]
  const parts = b.parts.filter(p => p.images.marked)
  const modes: [string, string][] = [...parts.map(p => [p.part, SHORT[p.part] || p.what] as [string, string]), ...(b.images.optical ? [['optical', 'Optical'] as [string, string]] : [])]
  const cur = modes.find(m => m[0] === mode)?.[0] || modes.find(m => m[0] === b.mainPart)?.[0] || modes[0]?.[0] || ''
  const part = parts.find(p => p.part === cur)
  const col = baseState(b.state)[1]
  return (
    <div>
      {head(b.name.split(',')[0], th)}
      <div className="px-5 pb-3 pt-3">
        <h1 className="text-[24px] font-semibold leading-tight tracking-[-0.02em]">{b.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[12.5px] text-fg3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line2 px-2 py-[2px] font-medium" style={{ color: col }}><Radar size={12} />{baseWord(b.state, b.mainPart)}</span>
          <span>{b.side} · {b.type === 'air' ? 'Air base' : b.type === 'naval' ? 'Naval base' : b.type === 'port' ? 'Port' : b.type === 'missile' ? 'Missile base' : 'Site'}</span>
        </div>
        <p className="mt-3 font-[family-name:var(--font-serif)] text-[16.5px] leading-[1.45] [text-wrap:pretty]">{b.why || 'No radar reading for this base yet.'}</p>
        {b.about && <p className="mt-2 text-[12.5px] leading-relaxed text-fg3">{b.about}</p>}
      </div>
      {modes.length > 0 ? <div className="px-5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex flex-wrap rounded-lg border border-line p-0.5 text-[12px]" role="tablist">
            {modes.map(([k, label]) => <button key={k} role="tab" aria-selected={cur === k} onClick={() => setMode(k)} className={`relative rounded-md px-2.5 py-1 ${cur === k ? 'text-fg' : 'text-fg3 hover:text-fg2'}`}>
              {cur === k && <motion.i layoutId="seg-img" className="absolute inset-0 rounded-md bg-hover" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}<span className="relative">{label}</span></button>)}
          </div>
          <span className="text-[11.5px] text-fg3">{cur === 'optical' ? 'Optical' : 'Radar'}, drag to compare</span>
        </div>
        {cur === 'optical' ? <Compare before={b.images.opticalBefore} after={b.images.optical} what="Optical image, Sentinel-2" />
          : part && <Compare before={part.images.before} after={part.images.marked} what="Radar, Sentinel-1" />}
        <p className="mt-2 text-[11.5px] leading-relaxed text-fg3">{cur === 'optical'
          ? 'Sentinel-2 optical, 10 m. Clouds and night hide it; radar sees through both. Contains modified Copernicus Sentinel data 2026.'
          : 'Sentinel-1 radar, 10 m. On the latest pass each circle marks a bright object and the outlines are the areas counted. Contains modified Copernicus Sentinel data 2026.'}</p>
      </div> : <p className="px-5 text-[13px] text-fg3">No image of this base yet. Images arrive with the next imagery run.</p>}
      {(part ? [part, ...b.parts.filter(p => p !== part)] : b.parts).map(p => <PartChart key={p.part} p={p} />)}
      {b.parts.length === 0 && b.radar.length > 1 && <Section title="Radar on each pass, against this base's normal" aside={`last ${b.radar.length} passes`}>
        <Spark v={b.radar} w={380} h={70} stroke={col} band={[-1, 1]} />
      </Section>}
      <p className="mx-5 mb-4 text-[12px] leading-relaxed text-fg3">One pass outside the normal range happens about one time in five by chance; two in a row far outside is what marks a base as changed. A change is a reason to look, not proof.</p>
      <div className="flex flex-wrap gap-2 px-5 pb-6">
        <a href={`https://browser.dataspace.copernicus.eu/?zoom=14&lat=${b.ll[1]}&lng=${b.ll[0]}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-fg2 hover:bg-hover">Copernicus Browser <ExternalLink size={12} /></a>
        {th && <button onClick={() => go({ v: 'theatre', id: th, tab: 'ground' })} className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-[12.5px] font-medium text-accentink">Open {name(th)}</button>}
      </div>
    </div>
  )
}

/* Before on the left, after on the right of a draggable divider. The range input carries keyboard and screen-reader use. */
function Compare({ before, after, what }: { before: Pic; after: Pic; what: string }) {
  const [pos, setPos] = useState(50)
  if (!after) return null
  if (!before) return <div className="overflow-hidden rounded-xl border border-line bg-black"><img src={asset(after.src)} alt={`${what}, ${after.date}`} className="block w-full" /></div>
  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-black">
      <img src={asset(before.src)} alt={`${what}, ${before.date}`} className="block w-full" />
      <img src={asset(after.src)} alt={`${what}, ${after.date}`} className="absolute inset-0 h-full w-full object-cover" style={{ clipPath: `inset(0 0 0 ${pos}%)` }} />
      <div className="pointer-events-none absolute inset-y-0 w-[2px] bg-white/90 shadow-[0_0_0_1px_rgba(0,0,0,.4)]" style={{ left: `${pos}%` }}>
        <span className="absolute top-1/2 -ml-[13px] -mt-[13px] grid h-[28px] w-[28px] place-items-center rounded-full bg-white text-[11px] font-semibold text-black shadow">⇆</span>
      </div>
      <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[11px] text-white">{before.date}</span>
      <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[11px] text-white">{after.date}</span>
      <input aria-label={`Compare the passes of ${before.date} and ${after.date}`} type="range" min={0} max={100} value={pos} onChange={e => setPos(+e.target.value)} className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0" />
    </div>
  )
}

/* Count on each pass against the base's usual band (low to high): the reader sees the band, not a z-score. */
function PartChart({ p }: { p: BasePart }) {
  const h = p.history.filter(x => x[1] != null)
  const w = 380, H = 92
  const geo = useMemo(() => {
    if (h.length < 2) return null
    const vals = h.flatMap(x => [x[1], x[3], x[4]].filter((v): v is number => v != null))
    const lo = Math.min(...vals), hi = Math.max(...vals), r = hi - lo || 1
    const X = (i: number) => 4 + (i / (h.length - 1)) * (w - 8), Y = (v: number) => H - 14 - ((v - lo) / r) * (H - 24)
    const band = h.map((x, i) => x[3] != null && x[4] != null ? [X(i), Y(x[4]), Y(x[3])] : null).filter(Boolean) as number[][]
    const bandD = band.length > 1 ? `M${band.map(b => `${b[0].toFixed(1)},${b[1].toFixed(1)}`).join('L')}L${[...band].reverse().map(b => `${b[0].toFixed(1)},${b[2].toFixed(1)}`).join('L')}Z` : ''
    const line = h.map((x, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(x[1]).toFixed(1)}`).join('')
    return { X, Y, bandD, line }
  }, [p])
  const col = baseState(p.state)[1]
  return (
    <Section title={PART_TITLE[p.part] || `${p.what} ${p.where}`} aside={p.tested ? `last ${h.length} passes` : 'not yet tested'}>
      <div className="flex items-baseline gap-3 text-[13px]">
        {p.now != null && <span className="num text-[20px] font-medium" style={{ color: col }}>{Math.round(p.now)}</span>}
        <span className="text-fg2">{p.note === 'usual' ? 'in the usual range' : p.note}{p.usual != null && <span className="text-fg3"> · usual {Math.round(p.usual)}{p.low != null && p.high != null ? ` (${Math.round(p.low)} to ${Math.round(p.high)})` : ''}</span>}</span>
      </div>
      {geo && <svg viewBox={`0 0 ${w} ${H}`} className="mt-2 w-full" role="img" aria-label={`Count on each of the last ${h.length} passes against the usual range`}>
        {geo.bandD && <path d={geo.bandD} fill="var(--line)" />}
        <path d={geo.line} fill="none" stroke={col} strokeWidth={1.5} strokeLinejoin="round" />
        {h.map((x, i) => { const out = x[3] != null && x[4] != null && (x[1] < x[3] || x[1] > x[4]); return <circle key={i} cx={geo.X(i)} cy={geo.Y(x[1])} r={out ? 2.6 : 1.6} fill={out ? 'var(--elev)' : col}><title>{`${x[0]}: ${x[1]}`}</title></circle> })}
        <text x={4} y={H - 1} fontSize={10} fill="var(--fg-3)">{shortDate(h[0][0])}</text>
        <text x={w - 4} y={H - 1} fontSize={10} fill="var(--fg-3)" textAnchor="end">{shortDate(h[h.length - 1][0])}</text>
      </svg>}
      {p.marks && <p className="mt-1 text-[12px] text-fg3">{p.marks.objects} objects on {shortDate(p.marks.date)}{p.marks.new != null && p.marks.gone != null ? `: ${p.marks.new} new and ${p.marks.gone} gone since ${shortDate(p.marks.before)}` : ''}.</p>}
      {!p.tested && <p className="mt-1 text-[12px] text-fg3">Not yet checked against past events, so it carries no weight in the risk numbers.</p>}
    </Section>
  )
}
