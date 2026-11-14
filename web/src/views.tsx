import { useMemo, useState, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ArrowLeft, ChevronDown } from 'lucide-react'
import { GROUPS, GROUP_HINT, useTheatre, useSignals, summary, gatesSentence, wireName, levelWord, wholeScore, groupTone, fmtZ, shortDate, parseGen,
  type Brief, type LiveMap, type Route, type Signal, type FeedItem, type Theatre, type Tell, type Group } from './data'
import { GroundTab } from './ground'
import { Spark, Tabs, tabPanel, Lnk, Tag, Facts, Block, Note, Skeleton, Failed, useWidth } from './ui'

type Go = (r: Route, replace?: boolean) => void
export const toRoute = (to: FeedItem['to']): Route => to.view === 'theatre' && to.id ? { v: 'theatre', id: to.id, tab: to.tab } : to.view === 'base' && to.id ? { v: 'base', id: to.id } : { v: 'brief' }

/* the level as a data mark (the dot before a tag); Quiet has none */
export const levelMark = (l: string) => l === 'Critical' ? 'var(--crit)' : l === 'Elevated' ? 'var(--z3)' : l === 'Watch' ? 'var(--z2)' : undefined
/* how unusual a signal reads, as a mark (the end of a sparkline); its number stays ink */
export const zMark = (z: number | null | undefined) => z == null ? 'var(--fg3)' : Math.abs(z) >= 3 ? 'var(--z3)' : Math.abs(z) >= 2 ? 'var(--z2)' : 'var(--fg2)'

/* Back, then where this sits: Watch / region, or Watch / theatre / Base */
export function Crumbs({ back, items, go }: { back: Route; items: [string, Route?][]; go: Go }) {
  return (
    <div className="flex min-w-0 items-center gap-1.5 px-5 pt-3.5 text-[12px] text-fg3">
      <button onClick={() => go(back)} aria-label="Back" className="-ml-1.5 grid h-7 w-7 shrink-0 place-items-center rounded-r1 hover:bg-s2 hover:text-fg"><ArrowLeft size={15} /></button>
      <nav aria-label="Breadcrumb" className="min-w-0"><ol className="flex min-w-0 items-center gap-1.5">
        {items.map(([t, r], i) => <li key={i} className="flex min-w-0 items-center gap-1.5">
          {i > 0 && <span aria-hidden className="text-fg3">/</span>}
          {r ? <Lnk to={r} go={go} className="truncate hover:text-fg">{t}</Lnk> : <span className="truncate text-fg2" aria-current={i === items.length - 1 ? 'page' : undefined}>{t}</span>}
        </li>)}
      </ol></nav>
    </div>
  )
}

/* ---------------------------------------------------------------- Theatre */
const TABS = ['now', 'ground', 'signals', 'history']
const GLOSS: Record<Group, string> = { Logistics: 'supply', Markets: 'money', People: 'advice', News: 'language', Physical: 'movement' }

export function TheatreView({ id, tab, brief, live, go }: { id: string; tab?: string; brief: Brief; live?: LiveMap; go: Go }) {
  const q = useTheatre(id)
  const sub = tab && TABS.includes(tab) ? tab : 'now'
  const bt = brief.theatres.find(t => t.id === id)
  const crumbs = (region?: string): [string, Route?][] => [['Watch', { v: 'brief' }], [region || bt?.region || '']]
  if (q.isPending) return <><Crumbs back={{ v: 'brief' }} items={crumbs()} go={go} /><h1 className="px-5 pt-2 text-[27px] font-semibold tracking-[-0.028em]">{bt?.name || id}</h1><Skeleton lines={6} /></>
  if (q.isError) return <><Crumbs back={{ v: 'brief' }} items={crumbs()} go={go} /><h1 className="px-5 pt-2 text-[27px] font-semibold tracking-[-0.028em]">{bt?.name || id}</h1><Failed what={bt?.name || id} error={q.error} /></>
  const t = q.data
  const regionName = brief.regions.find(r => r.theatres.includes(id))?.name || t.region
  const lit = t.tells.filter(x => x.on).length
  const nBases = live ? live.bases.filter(b => b.theatres.includes(id)).length : undefined
  const setTab = (s: string) => go({ v: 'theatre', id, tab: s }, true)
  return (
    <div>
      <Crumbs back={{ v: 'brief' }} items={[['Watch', { v: 'brief' }], [regionName]]} go={go} />
      <div className="px-5 pb-3.5 pt-2">
        <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em] max-[899px]:text-[25px]">{t.name}</h1>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Tag mark={levelMark(t.level)}><span className="sr-only">Level: </span>{levelWord(t.level)}</Tag>
          {t.context && <Tag><span title={`Set by hand${t.contextChecked ? `, checked ${shortDate(t.contextChecked)}` : ''}. Context only: it does not change the level.`}>{t.context}</span></Tag>}
          {lit > 0 && <Tag mark="var(--z2)">{lit} {lit === 1 ? 'tripwire' : 'tripwires'} lit</Tag>}
          {t.spillover && t.parents.length > 0 && <Tag>Spillover from {t.parents.map(p => brief.theatres.find(x => x.id === p)?.name || p).join(', ')}</Tag>}
        </div>
        <p className="mt-3 font-serif text-[16.5px] leading-[1.42] text-fg [text-wrap:pretty]">{summary(t, brief.model.active)}</p>
      </div>
      <Gauge t={t} active={brief.model.active} />
      <Tabs id="th" label={`${t.name} dossier`} value={sub} onChange={setTab} panel sticky
        tabs={[['now', 'Overview'], ['ground', 'Ground', nBases], ['signals', 'Signals', t.signals.total], ['history', 'History', t.events.length]]} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={sub} {...tabPanel('th', sub)} className="outline-none" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: [.22, 1, .36, 1] }}>
          {sub === 'now' && <Overview t={t} brief={brief} go={go} />}
          {sub === 'ground' && <GroundTab id={id} t={t} live={live} brief={brief} go={go} />}
          {sub === 'signals' && <SignalsTab t={t} go={go} />}
          {sub === 'history' && <HistoryTab t={t} brief={brief} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/* The reading on its track. Grey at every value: it has shown no skill as a forecast. The Watch and Critical ticks are drawn
   only while the model is off, because only then does the reading set the level. */
function Gauge({ t, active }: { t: Theatre; active: boolean }) {
  const s = t.score == null ? null : Math.max(0, Math.min(100, t.score))
  const w = s == null ? null : wholeScore(s)
  const line = !active
  const say: ReactNode = s == null || w == null ? 'No reading today'
    : !line ? null
    : s < 50 ? <><b className="font-medium text-fg">{50 - w} {50 - w === 1 ? 'point' : 'points'}</b> below Watch</>
    : s >= 90 ? <><b className="font-medium text-fg">Over</b> the Critical line</>
    : <><b className="font-medium text-fg">{w === 50 ? 'On' : 'Over'}</b> the Watch line</>
  return (
    <section aria-label="Unusual readings" className="mx-5 mb-3.5 rounded-r3 border border-line bg-s2 px-4 pb-3 pt-3.5">
      <h2 className="eyebrow mb-2.5">Unusual readings</h2>
      <div className="flex items-end justify-between gap-3">
        <p className="num whitespace-nowrap text-[46px] font-medium leading-[.9] tracking-[-0.045em] text-fg2">{w ?? '–'}<span className="ml-1.5 text-[13px] font-normal tracking-normal text-fg3">of 100</span></p>
        <p className="text-right text-[12.5px] leading-[1.35] text-fg2">{say}{say && <br />}Level today: {levelWord(t.level)}</p>
      </div>
      <div className={`relative ${line ? "mb-5" : "mb-3.5"} mt-3.5 h-2.5 rounded-[5px]`} aria-hidden
        style={{ background: line ? 'linear-gradient(90deg, var(--z0) 0 50%, color-mix(in srgb, var(--fg3) 26%, transparent) 50% 90%, color-mix(in srgb, var(--fg3) 46%, transparent) 90%)' : 'var(--z0)' }}>
        {s != null && <motion.i className="absolute inset-y-0 left-0 rounded-[5px] bg-fg2" initial={{ width: 0 }} animate={{ width: `${Math.max(s, 1.2)}%` }} transition={{ duration: .9, ease: [.2, .8, .2, 1] }} />}
        {line && ([[50, 'Watch 50'], [90, 'Critical 90']] as const).map(([x, l]) => (
          <i key={x} className="absolute -bottom-[3px] -top-[3px] w-px bg-fg3" style={{ left: `${x}%` }}><em className="absolute left-0 top-[17px] -translate-x-1/2 whitespace-nowrap text-[10px] not-italic leading-none text-fg3">{l}</em></i>))}
      </div>
      <Facts items={[
        [<>{t.tells.filter(x => x.on).length}<span className="text-[12px] font-normal text-fg3"> / {t.tells.length}</span></>, 'tripwires lit'],
        [t.signals.strong, `strong signals of ${t.signals.scored} scoring`],
        [t.confidence || 'n/a', 'confidence in the reading'],
      ]} />
    </section>
  )
}

/* ---------------------------------------------------------------- Overview */
function Overview({ t, brief, go }: { t: Theatre; brief: Brief; go: Go }) {
  return <>
    <Ladder t={t} brief={brief} go={go} />
    <Tripwires t={t} />
    {t.official.length > 0 && <Block title="Official word">
      <dl>{t.official.map((o, i) => (
        <div key={i} className="flex justify-between gap-4 border-t border-line py-1.5 text-[12.5px] first:border-0">
          <dt className="min-w-0 text-fg2">{o.name}</dt>
          <dd className="text-right text-fg">{o.value.split(';')[0]}<span className="num block text-[11px] text-fg3">{shortDate(o.date)}</span></dd>
        </div>))}
      </dl>
    </Block>}
    <Note>
      <b>How sure is this?</b> Confidence is {(t.confidence || 'not rated').toLowerCase()}: {t.signals.scored} of {t.signals.total} signals for {t.name} are scoring today.{' '}
      {brief.model.active
        ? 'The level comes from the 30-day model, which has passed its checks. The unusual readings measure how unusual today is and are not a chance of war.'
        : 'The level comes from the unusual readings alone, which measure how unusual today is and are not a chance of war. A 30-day chance model runs in shadow and stays off this screen until it passes its tests.'}{' '}
      <Lnk to={{ v: 'record' }} go={go} className="lnk">See the record</Lnk>
    </Note>
  </>
}

/* Build-up, slow to fast: each group's last 60 days as cells shaded by how unusual the day was (the board's own steps) */
function Ladder({ t, brief, go }: { t: Theatre; brief: Brief; go: Go }) {
  const [open, setOpen] = useState<Group | null>(null)
  const end = parseGen(brief.generated).getTime()
  const day = (k: number) => shortDate(new Date(end - k * 864e5).toISOString().slice(0, 10))
  const cols = 'grid grid-cols-[70px_minmax(0,1fr)_36px] gap-2.5'
  return (
    <Block title="Build-up, slow to fast" aside="60 days, darker is more unusual">
      {GROUPS.map(g => {
        const d = t.groups[g], h = (d?.history || []).slice(-60), on = open === g
        const peak = h.length ? Math.max(...h) : null
        return (
          <div key={g}>
            <button onClick={() => setOpen(on ? null : g)} aria-expanded={on} aria-controls={`lad-${g}`}
              className={`${cols} -mx-2 w-[calc(100%+16px)] items-center rounded-r1 px-2 py-1 text-left hover:bg-s2`}>
              <span className="text-[12.5px] leading-[1.15] text-fg">{g}<small className="block text-[10.5px] text-fg3">{GLOSS[g]}</small></span>
              <span className="grid h-[18px] gap-px" aria-hidden style={{ gridTemplateColumns: `repeat(${Math.max(h.length, 1)}, minmax(0,1fr))` }}>
                {h.map((z, i) => <i key={i} className="rounded-[1px]" style={{ background: groupTone(z) }} />)}
              </span>
              <span className="num flex items-center justify-end gap-0.5 text-[12px] font-medium text-fg2">{d?.z == null ? '–' : d.z.toFixed(1)}<ChevronDown size={11} aria-hidden className={`shrink-0 text-fg3 transition-transform ${on ? 'rotate-180' : ''}`} /></span>
              <span className="sr-only">{`: ${d?.z == null ? 'no reading today' : `${d.z.toFixed(1)} standard deviations from usual today`}${peak != null ? `, highest ${peak.toFixed(1)} in 60 days` : ''}. Show its top signals.`}</span>
            </button>
            <AnimatePresence initial={false}>{on && (
              <motion.div id={`lad-${g}`} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: .22, ease: [.22, 1, .36, 1] }} className="overflow-hidden">
                <div className="mb-1.5 ml-[80px] text-[11.5px] max-[420px]:ml-0">
                  <p className="py-0.5 text-fg3">{GROUP_HINT[g]}</p>
                  {(d?.top || []).length ? <ul>{d.top.map(s => (
                    <li key={s.id}><Lnk to={{ v: 'signal', id: s.id }} go={go} className="flex justify-between gap-2.5 py-[3px] text-fg2 hover:text-fg">
                      <span className="min-w-0 truncate">{s.label}</span><span className="num shrink-0 text-fg">{fmtZ(s.z)}</span></Lnk></li>))}</ul>
                    : <p className="py-0.5 text-fg3">No scored signals in this group.</p>}
                </div>
              </motion.div>)}
            </AnimatePresence>
          </div>)
      })}
      <div className={`${cols} mt-0.5 font-mono text-[9.5px] leading-none text-fg3`} aria-hidden>
        <span /><span className="flex justify-between"><span>{day(59)}</span><span>{day(29)}</span><span>today</span></span><span />
      </div>
    </Block>
  )
}

/* Tripwires: fixed rules over the last 7 days. Lit ones first, with the day they fired; every one with its record, plainly:
   most firings were not followed by anything. Each opens to the rule it checks. */
const year = (d?: string) => d ? d.slice(0, 4) : ''
const monthYear = (d: string) => new Date(d.slice(0, 10) + 'T00:00Z').toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).replace('Sept', 'Sep')
export function recordLine(x: Tell): string {
  const r = x.record
  if (!r || r.episodes == null) return 'New, no record yet'
  if (!r.episodes) return `Has not fired since ${year(r.first)}`
  return `Fired ${r.episodes} ${r.episodes === 1 ? 'time' : 'times'} since ${year(r.first)}, ${r.hits ?? 0} followed by an event`
}
function Tripwires({ t }: { t: Theatre }) {
  const [open, setOpen] = useState<string | null>(null)
  const list = useMemo(() => [...t.tells.filter(x => x.on).sort((a, b) => (b.date || '').localeCompare(a.date || '')), ...t.tells.filter(x => !x.on)], [t])
  const lit = list.filter(x => x.on).length
  const eps = t.tells.reduce((n, x) => n + (x.record?.episodes || 0), 0), hits = t.tells.reduce((n, x) => n + (x.record?.hits || 0), 0)
  return (
    <Block title="Tripwires" aside={`${lit} of ${t.tells.length} lit, fixed rules over 7 days`}>
      <ul className="grid gap-1.5">
        {list.map(x => { const on = open === x.id, r = x.record; return (
          <li key={x.id} className="rounded-r2 border" style={{ borderColor: x.on ? 'color-mix(in srgb, var(--z2) 55%, transparent)' : 'var(--line)', background: x.on ? 'color-mix(in srgb, var(--z2) 7%, var(--s2))' : 'var(--s2)' }}>
            <button onClick={() => setOpen(on ? null : x.id)} aria-expanded={on} aria-controls={`tw-${x.id}`} className="grid w-full grid-cols-[10px_minmax(0,1fr)_14px] items-start gap-2.5 rounded-r2 px-2.5 py-2 text-left">
              <i aria-hidden className={`mt-[5px] h-2 w-2 rounded-full border ${x.on ? 'tw-lit' : ''}`} style={{ background: x.on ? 'var(--z2)' : 'var(--z0)', borderColor: x.on ? 'var(--z2)' : 'var(--line2)' }} />
              <span className="min-w-0">
                <span className="flex flex-wrap items-baseline gap-x-2 text-[12.5px] font-medium leading-[1.3] text-fg">{wireName(x)}
                  {x.on && <span className="num text-[11.5px] font-normal text-fg2">{x.date ? `Fired ${shortDate(x.date)}` : 'Fired this week'}</span>}
                  <span className="sr-only">{x.on ? ', lit' : ', not lit'}.</span></span>
                <span className={`mt-0.5 block text-[11px] leading-[1.35] ${x.on ? 'text-fg2' : 'text-fg3'}`}>{recordLine(x)}<span className="sr-only">.</span></span>
                {r?.events ? <span className={`block text-[11px] leading-[1.35] ${x.on ? 'text-fg2' : 'text-fg3'}`}>Fired before {r.caught ?? 0} of {r.events} past events</span> : null}
              </span>
              <ChevronDown size={13} aria-hidden className={`mt-[3px] text-fg3 transition-transform ${on ? 'rotate-180' : ''}`} />
              <span className="sr-only">Show the rule</span>
            </button>
            <AnimatePresence initial={false}>{on && (
              <motion.div id={`tw-${x.id}`} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: .2 }} className="overflow-hidden">
                <div className="space-y-1 px-2.5 pb-2.5 pl-[30px] text-[11.5px] leading-[1.45] text-fg2">
                  {x.name !== wireName(x) && <p className="text-fg">{x.name}</p>}
                  <p><span className="text-fg3">The rule: </span>{x.says}</p>
                  {x.cases && <p><span className="text-fg3">Seen before: </span>{x.cases}</p>}
                  {r?.first && r.last ? <p className="text-fg3">The record runs from {monthYear(r.first)} to {monthYear(r.last)}{r.theatres ? `, across ${r.theatres} ${r.theatres === 1 ? 'theatre' : 'theatres'}` : ''}.</p> : null}
                </div>
              </motion.div>)}
            </AnimatePresence>
          </li>) })}
      </ul>
      {eps > 0 && <p className="mt-2.5 text-[11.5px] leading-[1.45] text-fg3">Across these rules, {hits} of {eps} past firings were followed by an event. A lit tripwire is a reason to look closer, not a forecast.</p>}
    </Block>
  )
}

/* ---------------------------------------------------------------- Signals */
function SignalsTab({ t, go }: { t: Theatre; go: Go }) {
  const q = useSignals()
  const all = useMemo(() => (q.data?.signals || []).filter(s => s.theatre === t.id), [q.data, t.id])
  const top = useMemo(() => all.filter(s => s.z != null).sort((a, b) => Math.abs(b.z!) - Math.abs(a.z!)).slice(0, 14), [all])
  return (
    <Block title="Most unusual now" aside="against each signal's own history">
      {q.isPending ? <Skeleton lines={8} /> : q.isError ? <Failed what="the signals" error={q.error} />
        : top.length === 0 ? <p className="text-[12.5px] text-fg3">No signal for this theatre is scoring today.</p>
        : <ul>{top.map(s => <li key={s.id} className="border-t border-line first:border-0"><SignalRow s={s} go={go} /></li>)}</ul>}
      <p className="mt-2.5 text-[12px]"><Lnk to={{ v: 'signals', th: t.id }} go={go} className="lnk">Open {all.length ? `all ${all.length}` : 'them'} in Signals</Lnk></p>
    </Block>
  )
}
function SignalRow({ s, go }: { s: Signal; go: Go }) {
  return (
    <Lnk to={{ v: 'signal', id: s.id }} go={go} className="group grid grid-cols-[minmax(0,1fr)_70px_44px] items-center gap-2.5 py-[7px]">
      <span className="min-w-0"><span className="line-clamp-2 text-[12.5px] leading-[1.3] text-fg group-hover:underline group-hover:decoration-line2 group-hover:underline-offset-[3px]">{s.label}</span>
        <span className="block truncate text-[11px] text-fg3">{s.group} · {s.sub}{s.lagging ? ' · confirms' : ''}{s.stale ? ' · last good copy' : ''}</span></span>
      <Spark v={s.spark} w={70} h={22} stroke="var(--fg3)" dot={zMark(s.z)} fill={false} />
      <span className="num text-right text-[12px] font-medium text-fg">{fmtZ(s.z)}</span>
    </Lnk>
  )
}

/* ---------------------------------------------------------------- History */
function HistoryTab({ t, brief }: { t: Theatre; brief: Brief }) {
  const hs = t.history.map(x => x[1])
  const last = t.history[t.history.length - 1]
  const events = useMemo(() => [...t.events].sort((a, b) => b.date.localeCompare(a.date)), [t.events])
  const [all, setAll] = useState(false)
  const c = t.chance, pct = (p: number) => `${Math.round(p * 100)}%`
  const big = (k: string) => ['strike', 'war', 'onset', 'invasion'].includes(k)
  return <>
    {hs.length > 1 && <Block title="Standing risk" aside={`last ${hs.length} days`}>
      <div className="flex items-center gap-3.5">
        <span role="img" aria-label={`Standing risk over the last ${hs.length} days, from ${hs[0]} to ${last[1]} times the theatre's usual. Lowest ${Math.min(...hs)}, highest ${Math.max(...hs)}.`} className="min-w-0 flex-1">
          <SizedSpark v={hs} h={44} />
        </span>
        <span className="num shrink-0 text-right text-[12.5px] leading-[1.3] text-fg2">{last[1].toFixed(2)}×<small className="block text-[11px] text-fg3">usual, today</small></span>
      </div>
      <p className="mt-1.5 text-[11px] leading-[1.45] text-fg3">The theatre's rate of qualifying events against its long-run usual, from the {brief.model.active ? 'model' : 'shadow model. It does not set the level'}.</p>
    </Block>}
    <Block title="What has happened here" aside={`the events the model is tested on, to ${shortDate(brief.eventsThrough)}`}>
      {events.length === 0 ? <p className="text-[12.5px] text-fg3">No labelled event in this theatre since 2018.</p>
        : <ol className="relative ml-[5px] border-l border-line2 pl-4">
          {(all ? events : events.slice(0, 14)).map((e, i) => (
            <li key={i} className="relative pb-3 last:pb-0">
              <i aria-hidden className="absolute -left-[20.5px] top-[4px] h-[7px] w-[7px] rounded-full border-[1.5px] border-happened" style={{ background: big(e.kind) ? 'var(--happened)' : 'var(--s1)' }} />
              <p className="num font-mono text-[10.5px] leading-none text-fg3">{new Date(e.date + 'T00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })} · {e.kind}</p>
              <p className="mt-0.5 text-[12.5px] leading-[1.35] text-fg">{e.text}</p>
            </li>))}
        </ol>}
      {events.length > 14 && <button onClick={() => setAll(!all)} className="lnk mt-2 text-[12px]">{all ? 'Show the latest 14' : `Show all ${events.length}`}</button>}
    </Block>
    <Note>
      <b>{brief.model.active ? 'The 30-day model.' : 'Shadow model.'}</b>{' '}
      {c.p != null ? <>It puts the 30-day chance of a qualifying event in {t.name} at {pct(c.p)}{c.lo != null && c.hi != null ? ` (${pct(c.lo)} to ${pct(c.hi)})` : ''}{c.usual != null ? `, against a usual ${pct(c.usual)}` : ''}. </> : 'It gives no chance for this theatre today. '}
      {gatesSentence(brief.model.gates, brief.model.active)}
    </Note>
  </>
}

/* a sparkline that fills its box: measured once, then drawn at that width */
function SizedSpark({ v, h }: { v: number[]; h: number }) {
  const [ref, w] = useWidth<HTMLSpanElement>()
  return <span ref={ref} className="block w-full" style={{ height: h }}>{w > 0 && <Spark v={v} w={w} h={h} stroke="var(--fg2)" fill={false} />}</span>
}
