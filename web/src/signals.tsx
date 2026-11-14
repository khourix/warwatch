import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Search, ExternalLink, X } from 'lucide-react'
import { GROUPS, useSignals, useSeries, useBuildup, fmtZ, shortDate, short, groupTone, stepFixed, routeHref,
  type Brief, type Route, type Signal, type Group, type Buildup, type SeriesFile } from './data'
import { Spark, Lnk, Facts, Skeleton, Failed, useWidth } from './ui'
import { Crumbs, zMark } from './views'

/* Signals: the build-up wall (every theatre against the last 60 days), where the unusual readings sit (theatre by group), and
   every series in one virtual list (921 rows, about 25 in the DOM) with a detail panel. A signal also has a page of its own,
   /signal/<id>/, which phones open instead of the panel. */

type Go = (r: Route, replace?: boolean) => void
/* the pipeline's words (contract.py, share.py): a signal is scoring when its status is ok and it has a reading; strong at 3 SD or
   more from its usual (brief counts.strong), unusual at 2 */
const scoring = (s: Signal) => s.status === 'ok' && s.z != null
const isStrong = (s: Signal) => scoring(s) && Math.abs(s.z!) >= 3
const isUnusual = (s: Signal) => scoring(s) && Math.abs(s.z!) >= 2
const STATUS: Record<string, string> = { ok: 'scoring', collecting: 'collecting history', awaiting_key: 'needs a free key', error: 'failed this run' }
type Only = 'all' | 'unusual' | 'strong' | 'off'
const ONLY: [Only, string][] = [['all', 'All'], ['unusual', 'Unusual'], ['strong', 'Strong'], ['off', 'Not scoring']]
const where = (brief: Brief, id: string) => id === 'global' ? 'Worldwide' : short(brief.theatres.find(t => t.id === id)?.name || id)
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
/* dates with the year when it is not this one: "13 Nov", "4 Mar 2024", a month "Oct 2026" */
const thisYear = new Date().getUTCFullYear()
const longDate = (d: string, monthly = false) => {
  if (monthly || d.length === 7) d = d.slice(0, 7)
  if (d.length === 7) return new Date(d + '-01T00:00Z').toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).replace('Sept', 'Sep')
  return shortDate(d.slice(0, 10)) + (+d.slice(0, 4) === thisYear ? '' : ' ' + d.slice(0, 4))
}

export function SignalsView({ th, brief, go }: { th?: string; brief: Brief; go: Go }) {
  const sq = useSignals()
  const all = sq.data?.signals || []
  const [q, setQ] = useState(''), [only, setOnly] = useState<Only>('all'), [g, setG] = useState<Group | null>(null), [t, setT] = useState<string | null>(th || null)
  const [sel, setSel] = useState<string | null>(null)
  const [box, cw] = useWidth<HTMLDivElement>()
  const three = cw >= 1180, panel = cw >= 860, phone = cw > 0 && cw < 700
  const list = useMemo(() => {
    const needle = q.toLowerCase().trim()
    return all.filter(s => (!g || s.group === g) && (!t || s.theatre === t)
      && (only === 'all' || (only === 'unusual' && isUnusual(s)) || (only === 'strong' && isStrong(s)) || (only === 'off' && !scoring(s)))
      && (!needle || `${s.label} ${s.sub} ${s.id} ${s.group} ${where(brief, s.theatre)}`.toLowerCase().includes(needle)))
      .sort((a, b) => (b.z == null ? -1 : Math.abs(b.z)) - (a.z == null ? -1 : Math.abs(a.z)))
  }, [all, q, g, t, only, brief])
  const open = panel ? all.find(s => s.id === sel) : undefined
  const pick = (th: string, gr: Group) => { if (t === th && g === gr) { setT(null); setG(null) } else { setT(th); setG(gr) } }

  const nSc = all.filter(scoring).length, nSt = all.filter(s => isStrong(s) && s.theatre !== 'global').length, nStG = all.filter(s => isStrong(s) && s.theatre === 'global').length
  /* strong as brief counts.strong counts it: in the theatres; the worldwide series (markets, US procurement) are named apart */
  const lede = !all.length ? null : `${all.length} public series, each scored against its own history. ${nSc} ${nSc === 1 ? 'is' : 'are'} scoring today; ${nSt} ${nSt === 1 ? 'reads' : 'read'} strong in the theatres${nStG ? ` and ${nStG} worldwide` : ''}, 3 SD or more from usual.`
  const matrix = <Matrix all={all} brief={brief} t={t} g={g} pick={pick} />
  return (
    <div ref={box} className="pb-6">
      <div className="px-5 pt-5">
        <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em]">Signals</h1>
        <p className="mt-2 max-w-[62ch] font-serif text-[16.5px] leading-[1.42] text-fg [text-wrap:pretty]">{lede ?? <span className="text-fg3">{brief.counts.signals} public series, each scored against its own history.</span>}</p>
      </div>
      <Wall go={go} />
      {sq.isError ? <Failed what="the signals" error={sq.error} /> : (
        <div className="mt-1 grid items-start gap-x-6 gap-y-4 px-5" style={{ gridTemplateColumns: three ? `272px minmax(0,1fr)${open ? ' 360px' : ''}` : panel ? (open ? 'minmax(0,1fr) 340px' : '272px minmax(0,1fr)') : 'minmax(0,1fr)' }}>
          {/* the matrix beside the list when there is room; folded above it on a phone, or while a signal is open on a mid-width screen */}
          {three || (panel && !open) ? <div className="sticky top-3">{matrix}</div>
            : <details className={`group rounded-r3 border border-line bg-s1 [&_summary::-webkit-details-marker]:hidden ${panel ? 'col-span-2' : ''}`}><summary className="flex cursor-pointer items-center justify-between px-3.5 py-2.5 text-[12.5px] font-semibold text-fg">Where it is unusual<span className="text-[11.5px] font-normal text-fg3 group-open:hidden">theatre by group, {t || g ? 'filtering the list' : 'pick a square to filter'}</span></summary><div className="max-w-[360px] px-0.5 pb-1">{matrix}</div></details>}
          <SignalList list={list} total={all.length} pending={sq.isPending} brief={brief} go={go} q={q} setQ={setQ} only={only} setOnly={setOnly} g={g} setG={setG} t={t} clearT={() => setT(null)}
            sel={open?.id} select={panel ? setSel : null} phone={phone} />
          {open && <aside aria-label="The selected signal" className="sticky top-3 max-h-[calc(100vh-88px)] overflow-y-auto rounded-r3 border border-line bg-s1 scroll-thin">
            <SignalDetail key={open.id} s={open} brief={brief} go={go} onClose={() => setSel(null)} />
          </aside>}
        </div>)}
    </div>
  )
}

/* ---------------------------------------------------------------- the build-up wall */
/* Breadth counts the groups that read high that day; a group reads high at 2 or more, the step the theatre dossier's build-up strips
   start their amber at (groupTone), which is also the pipeline's line for a group that is firing (config.THRESH_WATCH). */
const HIGH = 2
type WallView = 'Breadth' | Group
const WALL_VIEWS: WallView[] = ['Breadth', 'Physical', 'Logistics', 'People', 'Markets', 'News']
const BREADTH_TONE = ['var(--z0)', 'var(--z1)', 'var(--z2)', 'var(--z3)']
const groupWord = (z: number) => z >= 3 ? 'very high' : z >= 2 ? 'high' : z >= 1 ? 'raised' : 'usual'
const LEGEND: Record<'Breadth' | 'one', [string, string][]> = {
  Breadth: [['var(--z0)', 'no group high'], ['var(--z1)', 'one'], ['var(--z2)', 'two'], ['var(--z3)', 'three or more']],
  one: [['var(--z0)', 'usual, under 1'], ['var(--z1)', 'raised, 1 to 2'], ['var(--z2)', 'high, 2 to 3'], ['var(--z3)', 'very high, 3 or more']],
}
type Cell = { v: number | null; text: string }
type Row = { id: string; name: string; cells: Cell[]; today: number | null; recent: number; high: Group[] }

function wallRows(b: Buildup, view: WallView, n: number): Row[] {
  const fit = (h?: (number | null)[]) => { const x = (h || []).slice(-n); return [...Array(n - x.length).fill(null), ...x] as (number | null)[] }
  return b.theatres.map(r => {
    const hs = Object.fromEntries(GROUPS.map(gr => [gr, fit(r.groups[gr])])) as Record<Group, (number | null)[]>
    const cells: Cell[] = Array.from({ length: n }, (_, i) => {
      if (view !== 'Breadth') { const z = hs[view][i]; return { v: z, text: z == null ? 'No reading' : `${view} reads ${stepFixed(z)}, ${groupWord(z)}` } }
      const read = GROUPS.filter(gr => hs[gr][i] != null), high = read.filter(gr => hs[gr][i]! >= HIGH)
      return { v: read.length ? high.length : null, text: !read.length ? 'No reading' : high.length ? `${high.length} of 5 groups high: ${high.join(', ')}` : 'No group high' }
    })
    return { id: r.id, name: short(r.name), cells, today: cells[n - 1]?.v ?? null, recent: cells.slice(-14).reduce((a, c) => a + (c.v || 0), 0), high: GROUPS.filter(gr => (hs[gr][n - 1] ?? 0) >= HIGH) }
  }).sort((a, b) => (b.today ?? -1) - (a.today ?? -1) || b.recent - a.recent || a.name.localeCompare(b.name))
}

function Wall({ go }: { go: Go }) {
  const bq = useBuildup()
  const [view, setView] = useState<WallView>('Breadth')
  const [hover, setHover] = useState<[number, number] | null>(null)
  const [focus, setFocus] = useState<[number, number] | null>(null)
  const [cur, setCur] = useState<[number, number] | null>(null)     // the cell in the tab order (roving)
  const gridRef = useRef<HTMLDivElement>(null), tipBox = useRef<HTMLDivElement>(null)
  const b = bq.data
  const n = b ? Math.min(60, b.dates.length) : 0
  const dates = b ? b.dates.slice(-n) : []
  const rows = useMemo(() => b && n ? wallRows(b, view, n) : [], [b, view, n])
  const head = (
    <div className="mb-2.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <h2 id="wall-h" className="text-[12.5px] font-semibold text-fg">Build-up, last {n > 1 ? `${n} days` : '60 days'}</h2>
      {rows.length > 0 && <div role="group" aria-label="Colour the wall by" className="flex flex-wrap gap-1">
        {WALL_VIEWS.map(v => <button key={v} aria-pressed={view === v} onClick={() => setView(v)}
          className={`rounded-full border px-2.5 py-[3px] text-[12px] transition-colors duration-[120ms] ${view === v ? 'border-sel bg-sel font-medium text-selink' : 'border-line2 text-fg2 hover:text-fg'}`}>{v}</button>)}
      </div>}
    </div>)
  const frame = (body: ReactNode) => <section aria-labelledby="wall-h" className="mx-5 mb-5 mt-5 rounded-r3 border border-line bg-s1 px-4 pb-3.5 pt-3.5">{head}{body}</section>
  if (bq.isPending) return frame(<Skeleton lines={4} />)
  if (!b || n < 2 || !rows.length) return frame(<p className="text-[12.5px] text-fg3">{!b ? 'The build-up wall is not in this data run.' : 'Too few days to draw the wall yet.'} Each theatre's page shows its own build-up.</p>)

  const active = hover || focus
  const move = (e: KeyboardEvent, r: number, c: number) => {
    const to: [number, number] | null = e.key === 'ArrowRight' ? [r, Math.min(n - 1, c + 1)] : e.key === 'ArrowLeft' ? [r, Math.max(0, c - 1)]
      : e.key === 'ArrowDown' ? [Math.min(rows.length - 1, r + 1), c] : e.key === 'ArrowUp' ? [Math.max(0, r - 1), c]
      : e.key === 'Home' ? [r, 0] : e.key === 'End' ? [r, n - 1] : null
    if (!to) return
    e.preventDefault(); setCur(to)
    ;(gridRef.current?.querySelector(`[data-rc="${to[0]}-${to[1]}"]`) as HTMLElement | null)?.focus()
  }
  const [cr, cc] = cur || [0, n - 1]
  const legend = LEGEND[view === 'Breadth' ? 'Breadth' : 'one']
  /* the key numbers as text: today's picture in one line */
  const lit = rows.filter(r => (r.today ?? 0) >= (view === 'Breadth' ? 1 : HIGH)), top = rows[0]
  const summary = view === 'Breadth'
    ? (lit.length ? `Today ${lit.length} of ${rows.length} theatres have at least one group high. The most: ${top.name}, with ${top.high.length} (${top.high.join(', ')}).` : `Today no theatre has a group reading high.`)
    : (lit.length ? `Today ${lit.length} of ${rows.length} theatres read high in ${view}. The highest: ${top.name} at ${stepFixed(top.today!)}.` : `Today no theatre reads high in ${view}.`)
  const tip = (() => {
    if (!active || !gridRef.current || !tipBox.current) return null
    const el = gridRef.current.querySelector(`[data-rc="${active[0]}-${active[1]}"]`) as HTMLElement | null
    if (!el) return null
    const o = tipBox.current.getBoundingClientRect(), r = el.getBoundingClientRect(), row = rows[active[0]]
    const x = Math.max(4, Math.min(o.width - 224, r.left - o.left + r.width / 2 - 110))
    return <div role="presentation" className="pointer-events-none absolute z-10 w-[220px] rounded-r1 border border-line2 bg-s2 px-2 py-1.5 text-[11.5px] leading-[1.35] text-fg2 shadow-[var(--shadow)]"
      style={r.top - o.top < 48 ? { left: x, top: r.bottom - o.top + 8 } : { left: x, top: r.top - o.top - 8, transform: 'translateY(-100%)' }}><b className="font-medium text-fg">{row.name}</b> · {longDate(dates[active[1]])}<br />{row.cells[active[1]].text}</div>
  })()
  return frame(<>
    <div ref={tipBox} className="relative">
      <div className="scroll-thin -mx-1 overflow-x-auto px-1 pb-1">
        <div ref={gridRef} role="grid" aria-label={`Build-up wall, ${view === 'Breadth' ? 'how many of the five signal groups read high' : `how unusual ${view} reads`}, each theatre over ${n} days from ${longDate(dates[0])} to ${longDate(dates[n - 1])}`}
          aria-rowcount={rows.length} className="min-w-[620px]" onPointerLeave={e => { if (e.pointerType === 'mouse') setHover(null) }}>
          {rows.map((row, r) => (
            <div key={row.id} role="row" className="grid h-[19px] grid-cols-[118px_minmax(0,1fr)_34px] items-center gap-2.5">
              <span role="rowheader" className="min-w-0 truncate text-[12px] leading-none"><Lnk to={{ v: 'theatre', id: row.id }} go={go} className="text-fg2 hover:text-fg hover:underline hover:decoration-line2 hover:underline-offset-[3px]">{row.name}</Lnk></span>
              <span role="none" className="grid h-[15px] gap-px" style={{ gridTemplateColumns: `repeat(${n}, minmax(0,1fr))` }}>
                {row.cells.map((c, i) => (
                  <span key={i} role="gridcell" data-rc={`${r}-${i}`} tabIndex={r === cr && i === cc ? 0 : -1} aria-label={`${row.name}, ${longDate(dates[i])}: ${c.text}`}
                    onPointerEnter={() => setHover([r, i])} onPointerDown={e => { if (e.pointerType !== 'mouse') setHover([r, i]) }}
                    onFocus={() => { setFocus([r, i]); setCur([r, i]) }} onBlur={() => setFocus(null)} onKeyDown={e => move(e, r, i)}
                    className="rounded-[1.5px] focus-visible:outline-offset-1"
                    style={{ background: c.v == null ? 'transparent' : view === 'Breadth' ? BREADTH_TONE[Math.min(3, c.v)] : groupTone(c.v), boxShadow: c.v == null ? 'inset 0 0 0 1px var(--line)' : undefined }} />))}
              </span>
              <span role="gridcell" className="num text-right text-[12px] font-medium text-fg">{row.today == null ? '–' : view === 'Breadth' ? row.today : stepFixed(row.today)}</span>
            </div>))}
          <div className="mt-1.5 grid grid-cols-[118px_minmax(0,1fr)_34px] gap-2.5 font-mono text-[10px] leading-none text-fg3" aria-hidden>
            <span /><span className="flex justify-between"><span>{longDate(dates[0])}</span><span>{longDate(dates[Math.floor((n - 1) / 2)])}</span><span>{longDate(dates[n - 1])}</span></span><span className="text-right">today</span>
          </div>
        </div>
      </div>
      {tip}
    </div>
    <div className="mt-2.5 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-[11.5px] text-fg3" aria-label="Legend" role="group">
      {legend.map(([c, l]) => <span key={l} className="inline-flex items-center gap-1.5"><i aria-hidden className="h-2.5 w-2.5 rounded-[2px]" style={{ background: c }} />{l}</span>)}
      <span className="inline-flex items-center gap-1.5"><i aria-hidden className="h-2.5 w-2.5 rounded-[2px] shadow-[inset_0_0_0_1px_var(--line2)]" />no reading</span>
    </div>
    <p className="mt-1.5 text-[11.5px] leading-[1.45] text-fg2">{summary} <span className="text-fg3">{view === 'Breadth' ? 'A group reads high at 2 or more, the step where a theatre\'s build-up strips turn amber.' : 'The same readings as the build-up strips on each theatre\'s page.'} Hover, tap or use the arrow keys for a day.</span></p>
  </>)
}

/* ---------------------------------------------------------------- where it is unusual */
type MCell = { n: number; unusual: number; strong: number }
const mTone = (c?: MCell) => !c || !c.n ? 'var(--z0)' : c.strong >= 2 ? 'var(--z3)' : c.strong === 1 ? 'var(--z2)' : c.unusual ? 'var(--z1)' : 'var(--z0)'
function Matrix({ all, brief, t, g, pick }: { all: Signal[]; brief: Brief; t: string | null; g: Group | null; pick: (t: string, g: Group) => void }) {
  const m = useMemo(() => {
    const out: Record<string, MCell> = {}
    for (const s of all) {
      if (!scoring(s)) continue
      const c = out[s.theatre + '|' + s.group] ||= { n: 0, unusual: 0, strong: 0 }
      c.n++; if (Math.abs(s.z!) >= 3) c.strong++; else if (Math.abs(s.z!) >= 2) c.unusual++
    }
    return out
  }, [all])
  const rows = [...(all.some(s => s.theatre === 'global') ? ['global'] : []), ...[...brief.theatres].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)).map(x => x.id)]
  if (!all.length) return <section className="rounded-r3 border border-line bg-s1 px-3.5 py-3"><Skeleton lines={5} /></section>
  return (
    <section aria-labelledby="mx-h" className="rounded-r3 border border-line bg-s1 px-3.5 pb-3 pt-3">
      <h2 id="mx-h" className="eyebrow mb-2.5">Where it is unusual</h2>
      <div className="scroll-thin overflow-x-auto">
        <div className="min-w-[236px]">
          <div className="grid h-[18px] grid-cols-[minmax(0,1fr)_repeat(5,28px)] items-center gap-[3px] text-center font-mono text-[10px] text-fg3" aria-hidden>
            <span />{GROUPS.map(x => <span key={x} title={x}>{x.slice(0, 3)}</span>)}
          </div>
          {rows.map(id => { const name = where(brief, id); return (
            <div key={id} className="grid h-6 grid-cols-[minmax(0,1fr)_repeat(5,28px)] items-center gap-[3px]">
              <span className="truncate text-[12px] text-fg2">{name}</span>
              {GROUPS.map(gr => { const c = m[id + '|' + gr], on = t === id && g === gr
                const label = `${name}, ${gr}: ${c?.n ? `${plural(c.n, 'signal', 'signals')} scoring, ${c.strong} strong, ${c.unusual} more unusual` : 'no signal scoring'}`
                return <button key={gr} aria-pressed={on} aria-label={label} title={label} onClick={() => pick(id, gr)}
                  className={`h-5 rounded-[3px] transition-transform duration-100 hover:scale-110 ${on ? 'outline outline-[1.5px] outline-offset-1 outline-sel' : ''}`} style={{ background: mTone(c) }} /> })}
            </div>) })}
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-fg3" role="group" aria-label="Legend">
        {([['var(--z0)', 'usual'], ['var(--z1)', 'unusual'], ['var(--z2)', '1 strong'], ['var(--z3)', '2 or more strong']] as const).map(([c, l]) => <span key={l} className="inline-flex items-center gap-1.5"><i aria-hidden className="h-2.5 w-2.5 rounded-[2px]" style={{ background: c }} />{l}</span>)}
      </div>
      <p className="mt-1.5 text-[11.5px] leading-[1.45] text-fg3">Unusual is 2 SD or more from usual, strong 3. Pick a square to list its signals; pick it again to clear.</p>
    </section>
  )
}

/* ---------------------------------------------------------------- the list */
function SignalList({ list, total, pending, brief, go, q, setQ, only, setOnly, g, setG, t, clearT, sel, select, phone }: {
  list: Signal[]; total: number; pending: boolean; brief: Brief; go: Go; q: string; setQ: (s: string) => void; only: Only; setOnly: (o: Only) => void
  g: Group | null; setG: (g: Group | null) => void; t: string | null; clearT: () => void; sel?: string; select: ((id: string) => void) | null; phone: boolean
}) {
  const listRef = useRef<HTMLDivElement>(null)
  const [scrollEl, setScrollEl] = useState<HTMLElement | null>(null)
  const [margin, setMargin] = useState(0)
  /* the list's offset in its scroll box moves as the wall loads and the filters wrap: measured after every render, set when it changed */
  useLayoutEffect(() => {
    const el = listRef.current?.closest('[data-scroll]') as HTMLElement | null
    if (el !== scrollEl) setScrollEl(el)
    if (el && listRef.current) { const m = Math.round(listRef.current.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop); if (Math.abs(m - margin) > 1) setMargin(m) }
  })
  const rowH = phone ? 76 : 54
  const v = useVirtualizer({ count: list.length, getScrollElement: () => scrollEl, estimateSize: () => rowH, overscan: 10, scrollMargin: margin })
  const chip = (on: boolean) => `shrink-0 rounded-full border px-2.5 py-[3px] text-[12px] transition-colors duration-[120ms] ${on ? 'border-sel bg-sel font-medium text-selink' : 'border-line2 text-fg2 hover:text-fg'}`
  const cols = phone ? 'grid-cols-[minmax(0,1fr)_118px]' : 'grid-cols-[minmax(0,1fr)_78px_142px]'
  return (
    <section aria-label="All signals" className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-r2 border border-line bg-s1 px-2.5 py-[7px] focus-within:border-line2"><Search size={14} className="shrink-0 text-fg3" aria-hidden />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder={`Filter ${total || ''} signals`} aria-label="Filter signals by name, source or theatre" className="w-full bg-transparent text-[13.5px] outline-none placeholder:text-fg3" /></label>
        <span role="group" aria-label="Show" className="inline-flex rounded-r2 border border-line p-0.5 text-[12.5px]">
          {ONLY.map(([k, l]) => <button key={k} aria-pressed={only === k} onClick={() => setOnly(k)} className={`rounded-[6px] px-2.5 py-1 transition-colors duration-[120ms] ${only === k ? 'bg-s3 text-fg' : 'text-fg2 hover:text-fg'}`}>{l}</button>)}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span role="group" aria-label="Signal group" className="flex flex-wrap gap-1.5">{GROUPS.map(x => <button key={x} aria-pressed={g === x} onClick={() => setG(g === x ? null : x)} className={chip(g === x)}>{x}</button>)}</span>
        {t && <button onClick={clearT} className={`${chip(true)} inline-flex items-center gap-1`} aria-label={`Showing ${where(brief, t)} only. Show every theatre`}>{where(brief, t)}<X size={12} aria-hidden /></button>}
        <span className="num ml-auto text-[12px] text-fg3" aria-live="polite">{pending ? 'Loading…' : `${list.length} shown, most unusual first`}</span>
      </div>
      <div className={`mt-2.5 grid ${cols} items-end gap-3 border-b border-line2 px-2 pb-1.5 text-[11px] text-fg3`} aria-hidden>
        <span>Signal</span>{!phone && <span>Recent</span>}<span>Unusualness</span>
      </div>
      {pending ? <Skeleton lines={10} /> : list.length === 0 ? <p className="px-2 py-6 text-[12.5px] text-fg3">No signal matches. Clear a filter to see more.</p> : (
        <div ref={listRef} className="relative" style={{ height: v.getTotalSize() }} role="list" aria-label={`Signals, ${list.length} shown`}>
          {v.getVirtualItems().map(it => { const s = list[it.index], z = s.z, on = sel === s.id; return (
            <div key={s.id} role="listitem" className="absolute inset-x-0" style={{ top: 0, height: it.size, transform: `translateY(${it.start - margin}px)` }}>
              <Lnk to={{ v: 'signal', id: s.id }} go={select ? () => select(s.id) : go} className={`grid h-full ${cols} items-center gap-3 border-b border-line px-2 transition-colors duration-[120ms] ${on ? 'bg-s2 shadow-[inset_2px_0_0_var(--sel)]' : 'hover:bg-s2'}`}>
                <span className="min-w-0">
                  <span className={`block text-[13px] leading-[1.3] text-fg ${phone ? 'line-clamp-2' : 'truncate'}`} title={s.label}>{s.label}</span>
                  <span className="mt-0.5 block truncate text-[11.5px] text-fg3">{where(brief, s.theatre)} · {s.group}{s.sub ? ` · ${s.sub}` : ''}{s.untested ? ' · not tested' : ''}{!scoring(s) ? ` · ${STATUS[s.status] || s.status}` : s.stale ? ' · last good copy' : ''}</span>
                </span>
                {!phone && <Spark v={s.spark} w={74} h={22} stroke="var(--fg3)" dot={zMark(z)} fill={false} />}
                <ZBar z={z} />
                {on && <span className="sr-only">, open</span>}
              </Lnk>
            </div>) })}
        </div>)}
    </section>
  )
}

/* how far from usual, as a bar from the centre (left below usual, right above, full at 5 SD); the bar is the mark, the number ink */
function ZBar({ z }: { z: number | null }) {
  const w = z == null ? 0 : Math.min(Math.abs(z), 5) / 5 * 50
  return (
    <span className="grid grid-cols-[minmax(0,1fr)_38px] items-center gap-2">
      <span className="relative h-1.5 rounded-[3px] bg-z0" aria-hidden>
        <i className="absolute -bottom-[3px] -top-[3px] left-1/2 w-px bg-fg3" />
        {z != null && w > 0 && <i className="absolute inset-y-0 rounded-[3px]" style={{ [z >= 0 ? 'left' : 'right']: '50%', width: `${w}%`, background: zMark(z) === 'var(--fg2)' ? 'var(--fg3)' : zMark(z) }} />}
      </span>
      <span className="num text-right text-[12.5px] font-medium text-fg">{fmtZ(z)}</span>
    </span>
  )
}

/* ---------------------------------------------------------------- one signal: the panel, or its own page */
export function SignalView({ id, brief, go }: { id: string; brief: Brief; go: Go }) {
  const sq = useSignals()
  const s = sq.data?.signals.find(x => x.id === id)
  const inTheatre = s && brief.theatres.some(t => t.id === s.theatre)
  const back: Route = s && inTheatre ? { v: 'theatre', id: s.theatre, tab: 'signals' } : { v: 'signals' }
  const crumbs = <Crumbs back={back} items={[['Signals', { v: 'signals' }], ...(s && inTheatre ? [[where(brief, s.theatre), { v: 'theatre', id: s.theatre, tab: 'signals' }] as [string, Route]] : []), ['Signal']]} go={go} />
  if (sq.isPending) return <>{crumbs}<Skeleton lines={6} /></>
  if (sq.isError) return <>{crumbs}<h1 className="px-5 pt-2 text-[23px] font-semibold">Signal</h1><Failed what="the signals" error={sq.error} /></>
  if (!s) return <>{crumbs}<h1 className="px-5 pt-2 text-[23px] font-semibold">Signal</h1><p className="px-5 py-4 text-[13px] text-fg3">No signal called “{id}” in this run.</p></>
  return <>{crumbs}<SignalDetail s={s} brief={brief} go={go} page /></>
}

function SignalDetail({ s, brief, go, page, onClose }: { s: Signal; brief: Brief; go: Go; page?: boolean; onClose?: () => void }) {
  const hq = useSeries(s.id)
  const theatre = brief.theatres.find(t => t.id === s.theatre)
  const z = s.z
  const word = !scoring(s) ? (STATUS[s.status] || s.status) : Math.abs(z!) >= 3 ? 'strong' : Math.abs(z!) >= 2 ? 'unusual' : 'in its usual range'
  const H = page ? 'h1' : 'h2'
  const host = (() => { try { return new URL(s.url).hostname.replace(/^www\./, '') } catch { return '' } })()
  return (
    <div className={page ? 'pb-6' : 'pb-4'}>
      <div className={`px-5 ${page ? 'pt-2' : 'pt-4'}`}>
        <div className="flex items-start justify-between gap-3">
          <p className="eyebrow pt-1">{s.group}{s.sub ? ` · ${s.sub}` : ''}</p>
          {onClose && <button onClick={onClose} aria-label="Close the signal" className="-mr-1.5 -mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-r1 text-fg3 hover:bg-s2 hover:text-fg"><X size={15} /></button>}
        </div>
        <H className={`mt-1.5 font-semibold leading-[1.2] tracking-[-0.02em] text-fg ${page ? 'text-[23px]' : 'text-[17px]'}`}>{s.label}</H>
        {s.why && <p className="mt-2.5 font-serif text-[15.5px] leading-[1.45] text-fg [text-wrap:pretty]">{s.why}</p>}
        {s.untested && <p className="mt-2 text-[11.5px] text-fg3">New, not yet tested on past events, so it is kept out of the score.</p>}
        <Facts className="mt-3.5" items={[
          [fmtZ(z), word],
          [s.last ? longDate(s.last, s.kind === 'monthly') : '–', `latest reading, ${s.kind === 'monthly' ? 'monthly' : 'daily'}${s.stale ? `; a copy kept from ${longDate(s.stale)}` : ''}`],
          [s.lagging ? 'Confirms' : 'Leads', s.lagging ? 'published late, so it confirms' : 'published in time to warn'],
        ]} />
      </div>
      <div className="px-5 pt-4">
        {hq.isPending ? <Skeleton lines={3} /> : hq.data && hq.data.points.length > 1 ? <SeriesChart s={s} f={hq.data} />
          : s.spark.filter(x => x != null).length > 1 ? <RecentOnly s={s} />
          : <p className="text-[12.5px] text-fg3">No stored history for this signal yet.</p>}
      </div>
      <dl className="mx-5 mt-3.5 border-t border-line text-[12.5px]">
        {([['Where', theatre ? <Lnk to={{ v: 'theatre', id: s.theatre }} go={go} className="lnk">{theatre.name}</Lnk> : where(brief, s.theatre)],
          ['Series id', <span className="font-mono text-[12px] text-fg">{s.id}</span>],
          ...(s.url ? [['Source', <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-fg hover:underline hover:decoration-line2 hover:underline-offset-[3px]"><span className="max-w-[220px] truncate font-mono text-[12px]">{host || s.url}</span><ExternalLink size={11} aria-hidden /><span className="sr-only"> (opens the source)</span></a>]] : [])] as [string, ReactNode][]).map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-4 border-b border-line py-2"><dt className="text-fg3">{k}</dt><dd className="min-w-0 text-right text-fg">{v}</dd></div>))}
      </dl>
      <div className="flex flex-wrap gap-2 px-5 pt-3.5">
        {theatre && <Lnk to={{ v: 'theatre', id: s.theatre }} go={go} className="inline-flex items-center rounded-r2 bg-sel px-3 py-1.5 text-[12.5px] font-medium text-selink">Open {short(theatre.name)}</Lnk>}
        {!page && <a href={routeHref({ v: 'signal', id: s.id })} onClick={e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); go({ v: 'signal', id: s.id }) }} className="inline-flex items-center rounded-r2 border border-line2 px-3 py-1.5 text-[12.5px] text-fg2 hover:text-fg">Its own page</a>}
      </div>
    </div>
  )
}

/* Past events a series carries in its own points: an action series ("step", travel-advisory level sums) changes on the day of each
   step; a rating series ("event", CrisisWatch) reads above zero in each month it rated (dashboard.CW_WORDS) */
const CW = ['no alert', 'deteriorated', 'conflict-risk alert', 'conflict-risk alert, deteriorated']
const num = (n: number) => String(Math.round(n * 100) / 100)
function pastEvents(s: Signal, pts: [string, number | null][]): { date: string; text: string }[] {
  if (s.event !== 'step' && s.event !== 'event') return []
  const out: { date: string; text: string }[] = []
  let prev: number | null = null
  for (const [d, v] of pts) {
    if (v == null) continue
    if (s.event === 'step' ? prev != null && v !== prev : v > 0)
      out.push({ date: d, text: s.event === 'step' ? `${num(prev!)} to ${num(v)}` : s.id.startsWith('crisiswatch_') ? CW[Math.max(0, Math.min(3, Math.round(v)))] : `reads ${num(v)}` })
    prev = v
  }
  return out
}
const tms = (d: string) => Date.parse((d.length === 7 ? d + '-01' : d.slice(0, 10)) + 'T00:00Z')

/* the series' values on a time axis (at most 500 points drawn), past events as quiet ivory ticks, and under it the distance from
   usual over time as a strip of the same width */
function SeriesChart({ s, f }: { s: Signal; f: SeriesFile }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const H = 116, B = 16
  const all = f.points.filter((p): p is [string, number] => p[1] != null && Number.isFinite(tms(p[0])))
  const ev = useMemo(() => pastEvents(s, f.points), [s, f])
  if (all.length < 2) return <p className="text-[12.5px] text-fg3">Not enough history to draw yet.</p>
  const step = Math.max(1, Math.ceil(all.length / 500))
  const p = all.filter((_, i) => i % step === 0 || i === all.length - 1)
  const t0 = tms(p[0][0]), t1 = tms(p[p.length - 1][0]), lo = Math.min(...p.map(x => x[1])), hi = Math.max(...p.map(x => x[1])), r = hi - lo || 1
  const X = (d: string) => 2 + ((tms(d) - t0) / (t1 - t0 || 1)) * (w - 4), Y = (y: number) => 6 + (1 - (y - lo) / r) * (H - B - 12)
  const d = p.map((x, i) => `${i ? 'L' : 'M'}${X(x[0]).toFixed(1)},${Y(x[1]).toFixed(1)}`).join('')
  const fmt = (n: number) => Math.abs(n) >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : Math.abs(n) >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : num(n)
  const last = p[p.length - 1]
  const zz = f.zHistory.filter((x): x is [string, number] => x[1] != null)
  const shownEv = ev.filter(e => tms(e.date) >= t0), m = s.kind === 'monthly', ld = (d: string) => longDate(d, m)
  return (
    <div ref={ref}>
      {w > 0 && <svg width={w} height={H} className="block" role="img" aria-label={`${s.label}: values from ${ld(p[0][0])} to ${ld(last[0])}, between ${fmt(lo)} and ${fmt(hi)}; latest ${fmt(last[1])}.${shownEv.length ? ` ${plural(shownEv.length, 'past event is', 'past events are')} marked.` : ''}`}>
        {shownEv.map((e, i) => <line key={i} x1={X(e.date)} x2={X(e.date)} y1={2} y2={H - B} stroke="var(--happened)" strokeOpacity={.5} strokeWidth={1} />)}
        <path d={`${d}L${X(last[0])},${H - B}L${X(p[0][0])},${H - B}Z`} fill="var(--fg2)" opacity={.07} />
        <path d={d} fill="none" stroke="var(--fg)" strokeWidth={1.3} strokeLinejoin="round" />
        <circle cx={X(last[0])} cy={Y(last[1])} r={3} fill={zMark(s.z) === 'var(--fg2)' ? 'var(--fg)' : zMark(s.z)} />
        <text x={2} y={11} fontSize={10} fill="var(--fg3)" fontFamily="var(--font-mono)">{fmt(hi)}</text>
        <text x={2} y={H - B - 3} fontSize={10} fill="var(--fg3)" fontFamily="var(--font-mono)">{fmt(lo)}</text>
        <text x={2} y={H - 3} fontSize={10} fill="var(--fg3)" fontFamily="var(--font-mono)">{ld(p[0][0])}</text>
        <text x={w - 2} y={H - 3} fontSize={10} fill="var(--fg3)" fontFamily="var(--font-mono)" textAnchor="end">{ld(last[0])}</text>
      </svg>}
      {shownEv.length > 0 && <p className="mt-1.5 text-[11.5px] leading-[1.45] text-fg3"><span className="mr-1 inline-block h-2.5 w-px translate-y-[1px] bg-happened opacity-70" aria-hidden />{s.event === 'step' ? 'Steps' : 'Ratings above zero'}: {shownEv.slice(-6).reverse().map(e => `${ld(e.date)}, ${e.text}`).join('; ')}{shownEv.length > 6 ? `; and ${shownEv.length - 6} earlier` : ''}.</p>}
      {zz.length > 1 && <>
        <div className="mt-2.5 grid h-2.5 gap-px" style={{ gridTemplateColumns: `repeat(${zz.length}, minmax(0,1fr))` }} role="img" aria-label={`Distance from its own usual, ${ld(zz[0][0])} to ${ld(zz[zz.length - 1][0])}: highest ${fmtZ(Math.max(...zz.map(x => x[1])))}, lowest ${fmtZ(Math.min(...zz.map(x => x[1])))}`}>
          {zz.map(([dt, v], i) => <i key={i} title={`${ld(dt)}: ${fmtZ(v)} SD`} className="rounded-[1px]" style={{ background: Math.abs(v) >= 3 ? 'var(--z3)' : Math.abs(v) >= 2 ? 'var(--z2)' : Math.abs(v) >= 1 ? 'var(--z1)' : 'var(--z0)' }} />)}
        </div>
        <p className="mt-1.5 text-[11.5px] text-fg3">Distance from its own usual, {ld(zz[0][0])} to {ld(zz[zz.length - 1][0])}: darker from 1 SD, amber from 2, orange from 3.</p>
      </>}
    </div>
  )
}

/* when the series file is missing: the recent readings the list carries */
function RecentOnly({ s }: { s: Signal }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const k = s.spark.length
  return <div>
    <div ref={ref} role="img" aria-label={`The last ${k} readings of ${s.label}`} style={{ height: 60 }}>{w > 0 && <Spark v={s.spark} w={w} h={60} stroke="var(--fg)" dot={zMark(s.z) === 'var(--fg2)' ? 'var(--fg)' : zMark(s.z)} fill={false} />}</div>
    <p className="mt-1.5 text-[11.5px] text-fg3">The last {k} readings. The full history is not in this data run.</p>
  </div>
}
