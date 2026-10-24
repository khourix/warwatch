import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ArrowLeft, ChevronRight, Search, ExternalLink } from 'lucide-react'
import { GROUPS, useSignals, useSeries, fmtZ, shortDate, type Brief, type Route, type Signal } from './data'
import { Spark, Section, Skeleton, Failed } from './ui'

/* Signals: every series in one virtual list (765 rows, about 25 in the DOM), with search, group and theatre filters and three
   sorts. A row opens the Signal view: the full history, its distance from normal over time, why it is watched, and the source. */

type Go = (r: Route) => void
const STATUS: Record<string, [string, string]> = {
  ok: ['Scored', 'var(--fg-3)'], collecting: ['Collecting history', 'var(--fg-3)'], awaiting_key: ['Needs a free key', 'var(--watch)'], error: ['Failed this run', 'var(--crit)'],
}
const zTone = (z: number | null) => z == null ? 'var(--fg-3)' : Math.abs(z) >= 3 ? 'var(--elev)' : Math.abs(z) >= 2 ? 'var(--watch)' : 'var(--fg-2)'
type Sort = 'unusual' | 'name' | 'fresh'

export function SignalsView({ th, brief, go }: { th?: string; brief: Brief; go: Go }) {
  const sq = useSignals()
  const [q, setQ] = useState(''), [g, setG] = useState<string>('All'), [t, setT] = useState(th || 'all'), [only, setOnly] = useState(false), [sort, setSort] = useState<Sort>('unusual')
  const all = sq.data?.signals || []
  const thName = (id: string) => brief.theatres.find(x => x.id === id)?.name || (id === 'global' ? 'Global' : id)
  const list = useMemo(() => {
    const needle = q.toLowerCase().trim()
    const f = all.filter(s => (g === 'All' || s.group === g) && (t === 'all' || s.theatre === t) && (!only || Math.abs(s.z ?? 0) >= 2)
      && (!needle || `${s.label} ${s.sub} ${s.id} ${thName(s.theatre)}`.toLowerCase().includes(needle)))
    const by: Record<Sort, (a: Signal, b: Signal) => number> = {
      unusual: (a, b) => Math.abs(b.z ?? -1) - Math.abs(a.z ?? -1),
      name: (a, b) => a.label.localeCompare(b.label),
      fresh: (a, b) => (b.last || '').localeCompare(a.last || ''),
    }
    return f.sort(by[sort])
  }, [all, q, g, t, only, sort])

  const listRef = useRef<HTMLDivElement>(null)
  const [scrollEl, setScrollEl] = useState<HTMLElement | null>(null)
  const [margin, setMargin] = useState(0)
  useLayoutEffect(() => {
    const el = listRef.current?.closest('[data-scroll]') as HTMLElement | null
    setScrollEl(el)
    if (el && listRef.current) setMargin(listRef.current.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop)
  }, [sq.data])
  const v = useVirtualizer({ count: list.length, getScrollElement: () => scrollEl, estimateSize: () => 52, overscan: 10, scrollMargin: margin })

  return (
    <div>
      <div className="flex items-center gap-2 px-5 pt-4 text-[12.5px] text-fg3">
        <button onClick={() => go({ v: 'brief' })} aria-label="Back" className="-ml-1.5 grid h-7 w-7 place-items-center rounded-md hover:bg-hover hover:text-fg"><ArrowLeft size={15} /></button>
        <button onClick={() => go({ v: 'brief' })} className="hover:text-fg">Brief</button><ChevronRight size={12} className="opacity-50" /><span className="text-fg2">Signals</span>
      </div>
      <div className="px-5 pt-3">
        <h1 className="text-[24px] font-semibold tracking-[-0.02em]">Signals</h1>
        <p className="mt-1 text-[13px] text-fg3"><span className="num">{sq.data?.signals.length ?? brief.counts.signals}</span> public series, each scored against its own history.</p>
        <label className="mt-3 flex items-center gap-2 rounded-lg border border-line bg-raised px-2.5 py-2 focus-within:border-accent"><Search size={14} className="text-fg3" /><input value={q} onChange={e => setQ(e.target.value)} placeholder="Search name, source or theatre" aria-label="Search signals" className="w-full bg-transparent text-[13.5px] outline-none placeholder:text-fg3" /></label>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {['All', ...GROUPS].map(x => <button key={x} onClick={() => setG(x)} aria-pressed={g === x} className={`rounded-full border px-2.5 py-1 text-[12px] ${g === x ? 'border-accent bg-accentsoft text-fg' : 'border-line text-fg2 hover:border-line2'}`}>{x}</button>)}
          <button onClick={() => setOnly(!only)} aria-pressed={only} className={`rounded-full border px-2.5 py-1 text-[12px] ${only ? 'border-watch text-watch' : 'border-line text-fg2'}`}>Unusual only</button>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select value={t} onChange={e => setT(e.target.value)} aria-label="Theatre" className="rounded-full border border-line bg-panel px-2 py-1 text-[12px] text-fg2"><option value="all">All theatres</option>{brief.theatres.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}<option value="global">Global markets</option></select>
          <span className="flex-1" />
          <span className="text-[12px] text-fg3">Sort</span>
          <span className="inline-flex rounded-lg border border-line p-0.5 text-[12px]" role="radiogroup" aria-label="Sort">
            {([['unusual', 'Most unusual'], ['fresh', 'Newest'], ['name', 'Name']] as [Sort, string][]).map(([k, n]) => <button key={k} role="radio" aria-checked={sort === k} onClick={() => setSort(k)} className={`rounded-md px-2 py-0.5 ${sort === k ? 'bg-hover text-fg' : 'text-fg3 hover:text-fg2'}`}>{n}</button>)}
          </span>
        </div>
        <div className="num mt-3 border-b border-line pb-2 text-[12px] text-fg3">{sq.isPending ? 'Loading…' : `${list.length} shown`}</div>
      </div>
      {sq.isError ? <Failed what="the signals" error={sq.error} /> : sq.isPending ? <Skeleton lines={10} /> : (
        <div ref={listRef} className="relative mx-5 mb-6" style={{ height: v.getTotalSize() }} role="list" aria-label="Signals">
          {v.getVirtualItems().map(it => { const s = list[it.index]; return (
            <button key={s.id} role="listitem" onClick={() => go({ v: 'signal', id: s.id })} className="absolute inset-x-0 grid grid-cols-[1fr_auto_48px] items-center gap-3 border-b border-line text-left hover:bg-hover"
              style={{ top: 0, height: it.size, transform: `translateY(${it.start - margin}px)` }}>
              <span className="min-w-0"><span className="block truncate text-[13px] text-fg" title={s.label}>{s.label}</span>
                <span className="block truncate text-[11.5px] text-fg3">{thName(s.theatre)} · {s.group} · {s.sub}{s.untested ? ' · not tested' : ''}{s.status !== 'ok' ? ` · ${STATUS[s.status]?.[0] || s.status}` : s.stale ? ' · last good copy' : ''}</span></span>
              <Spark v={s.spark} w={76} h={22} stroke={Math.abs(s.z ?? 0) >= 2 ? 'var(--watch)' : 'var(--fg-3)'} fill={false} />
              <span className="num text-right text-[12.5px]" style={{ color: zTone(s.z) }}>{fmtZ(s.z)}</span>
            </button>) })}
        </div>)}
    </div>
  )
}

/* ---------------------------------------------------------------- one signal */
export function SignalView({ id, brief, go }: { id: string; brief: Brief; go: Go }) {
  const sq = useSignals(), hq = useSeries(id)
  const s = sq.data?.signals.find(x => x.id === id)
  const thName = (x: string) => brief.theatres.find(t => t.id === x)?.name
  const back: Route = s && thName(s.theatre) ? { v: 'theatre', id: s.theatre, tab: 'signals' } : { v: 'signals' }
  const head = (
    <div className="flex items-center gap-2 px-5 pt-4 text-[12.5px] text-fg3">
      <button onClick={() => go(back)} aria-label="Back" className="-ml-1.5 grid h-7 w-7 place-items-center rounded-md hover:bg-hover hover:text-fg"><ArrowLeft size={15} /></button>
      <button onClick={() => go({ v: 'signals' })} className="hover:text-fg">Signals</button>
      {s && thName(s.theatre) && <><ChevronRight size={12} className="opacity-50" /><button onClick={() => go({ v: 'theatre', id: s.theatre, tab: 'signals' })} className="hover:text-fg">{thName(s.theatre)}</button></>}
    </div>)
  if (sq.isPending) return <>{head}<Skeleton lines={6} /></>
  if (sq.isError) return <>{head}<Failed what="the signals" error={sq.error} /></>
  if (!s) return <>{head}<p className="px-5 py-6 text-[13px] text-fg3">No signal called “{id}” in this run.</p></>
  const [st, stCol] = STATUS[s.status] || [s.status, 'var(--fg-3)']
  return (
    <div>
      {head}
      <div className="px-5 pb-2 pt-3">
        <h1 className="text-[21px] font-semibold leading-snug tracking-[-0.015em]">{s.label}</h1>
        <div className="mt-1.5 flex flex-wrap gap-x-3 text-[12.5px] text-fg3"><span>{s.group} · {s.sub}</span><span>{s.kind === 'monthly' ? 'Monthly' : 'Daily'}</span><span>{s.lagging ? 'Confirms (published late)' : 'Leads'}</span>{s.untested && <span style={{ color: 'var(--watch)' }} title="New in October 2026. Shown and used in the timing tells, but kept out of the score until a test on past events passes.">Not tested yet, not in the score</span>}</div>
        <dl className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-line bg-[var(--line)]">
          {([['From its normal', <span style={{ color: zTone(s.z) }}>{s.z == null ? 'n/a' : `${fmtZ(s.z)} SD`}</span>, Math.abs(s.z ?? 0) >= 3 ? 'strong' : Math.abs(s.z ?? 0) >= 2 ? 'unusual' : 'usual range'],
            ['Latest value', s.last ? shortDate(s.last.slice(0, 10)) : 'none', s.stale ? `stale, copy of ${s.stale}` : 'fresh'],
            ['Status', <span style={{ color: stCol }}>{st}</span>, s.event ? 'event flag' : s.status === 'collecting' ? 'scored later' : '']] as const).map(([a, b, c], i) => (
            <div key={i} className="bg-panel px-3 py-2.5"><dt className="text-[11.5px] text-fg3">{a}</dt><dd className="num mt-1 text-[16px] font-medium leading-tight">{b}</dd><dd className="mt-1 text-[11.5px] text-fg3">{c}</dd></div>
          ))}
        </dl>
        {s.why && <p className="mt-4 font-[family-name:var(--font-serif)] text-[16px] leading-[1.45] [text-wrap:pretty]">{s.why}</p>}
      </div>
      <Section title="History" aside={hq.data ? `${hq.data.points.length} ${s.kind === 'monthly' ? 'months' : 'days'}` : undefined}>
        {hq.isPending ? <Skeleton lines={3} /> : hq.isError ? <p className="text-[13px] text-fg3">No stored history for this signal yet.</p> : <HistoryChart pts={hq.data.points} zs={hq.data.zHistory} />}
      </Section>
      <div className="flex flex-wrap gap-2 px-5 pb-6">
        {s.url && <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-fg2 hover:bg-hover">Source <ExternalLink size={12} /></a>}
        {thName(s.theatre) && <button onClick={() => go({ v: 'theatre', id: s.theatre })} className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-[12.5px] font-medium text-accentink">Open {thName(s.theatre)}</button>}
      </div>
    </div>
  )
}

/* Values as a line (at most 400 points), and under it the distance from normal as a heat strip on the same time axis. */
function HistoryChart({ pts, zs }: { pts: [string, number | null][]; zs: [string, number | null][] }) {
  const w = 400, H = 110
  const step = Math.max(1, Math.ceil(pts.length / 400))
  const p = pts.filter((_, i) => i % step === 0 || i === pts.length - 1).filter(x => x[1] != null) as [string, number][]
  if (p.length < 2) return <p className="text-[13px] text-fg3">Not enough history to draw yet.</p>
  const lo = Math.min(...p.map(x => x[1])), hi = Math.max(...p.map(x => x[1])), r = hi - lo || 1
  const X = (i: number) => 2 + (i / (p.length - 1)) * (w - 4), Y = (y: number) => H - 16 - ((y - lo) / r) * (H - 26)
  const d = p.map((x, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(x[1]).toFixed(1)}`).join('')
  const fmt = (n: number) => Math.abs(n) >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : Math.abs(n) >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(Math.round(n * 100) / 100)
  const zz = zs.filter(x => x[1] != null) as [string, number][]
  return <>
    <svg viewBox={`0 0 ${w} ${H}`} className="w-full" role="img" aria-label={`Values from ${p[0][0]} to ${p[p.length - 1][0]}, between ${fmt(lo)} and ${fmt(hi)}`}>
      <path d={`${d}L${X(p.length - 1)},${H - 16}L${X(0)},${H - 16}Z`} fill="var(--accent)" opacity={.08} />
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth={1.3} strokeLinejoin="round" />
      <text x={2} y={9} fontSize={10} fill="var(--fg-3)">{fmt(hi)}</text>
      <text x={2} y={H - 18} fontSize={10} fill="var(--fg-3)">{fmt(lo)}</text>
      <text x={2} y={H - 2} fontSize={10} fill="var(--fg-3)">{p[0][0]}</text>
      <text x={w - 2} y={H - 2} fontSize={10} fill="var(--fg-3)" textAnchor="end">{p[p.length - 1][0]}</text>
    </svg>
    {zz.length > 1 && <>
      <div className="mt-2 grid h-3 gap-px" style={{ gridTemplateColumns: `repeat(${zz.length}, minmax(0,1fr))` }} role="img" aria-label="Distance from normal over the same period">
        {zz.map(([dt, z], i) => <i key={i} title={`${dt}: ${fmtZ(z)} SD`} className="rounded-[1px]" style={{ background: Math.abs(z) >= 3 ? 'var(--elev)' : Math.abs(z) >= 2 ? 'var(--watch)' : Math.abs(z) >= 1 ? 'color-mix(in oklab, var(--watch) 35%, transparent)' : 'var(--line)' }} />)}
      </div>
      <p className="mt-1.5 text-[11.5px] text-fg3">Distance from its own normal, {zz[0][0]} to {zz[zz.length - 1][0]}. Amber at 2 SD, orange at 3.</p>
    </>}
  </>
}
