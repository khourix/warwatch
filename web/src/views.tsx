import { useMemo, useState, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ArrowLeft, ChevronDown, Pin } from 'lucide-react'
import { useFollow } from './follow'
import { useReplay } from './replay'
import { GROUPS, GROUP_HINT, useTheatre, useSignals, summary, countWord, gatesSentence, wireName, levelWord, wholeAt, lineWhole, groupTone, stepFixed, fmtZ, fmtChange, NOW_WORD, shortDate, parseGen,
  type Brief, type LiveMap, type Route, type Signal, type FeedItem, type Theatre, type Tell, type Group } from './data'
import { GroundTab } from './ground'
import { Spark, Tabs, tabPanel, Lnk, Tag, Facts, Block, Note, Skeleton, Failed, useWidth, CopyLink, Explain, NowMark } from './ui'

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
      <button onClick={() => go(back)} aria-label="Back" className="tap -ml-1.5 grid h-7 w-7 max-[899px]:w-11 shrink-0 place-items-center rounded-r1 hover:bg-s2 hover:text-fg"><ArrowLeft size={15} /></button>
      <nav aria-label="Breadcrumb" className="min-w-0 flex-1"><ol className="flex min-w-0 items-center gap-1.5">
        {items.map(([t, r], i) => <li key={i} className="flex min-w-0 items-center gap-1.5">
          {i > 0 && <span aria-hidden className="text-fg3">/</span>}
          {r ? <Lnk to={r} go={go} className="block truncate hover:text-fg max-[899px]:-my-3.5 max-[899px]:py-3.5">{t}</Lnk> : <span className="truncate text-fg2">{t}</span>}
        </li>)}
      </ol></nav>
      <CopyLink />
    </div>
  )
}

/* ---------------------------------------------------------------- Theatre */
/* Does the 30-day model set this theatre's level? Only when it is active and gives this theatre a chance: a sub-theatre the
   model has not passed for (model.py, "held") keeps its signal-pressure level and carries no chance. */
export const modelOn = (b: Brief, t: Theatre) => b.model.active && t.chance.p != null
const held = (b: Brief, t: Theatre) => b.model.active && t.chance.p == null
const TABS = ['now', 'ground', 'signals', 'history']
const GLOSS: Record<Group, string> = { Logistics: 'supply', Markets: 'money', People: 'advice', News: 'language', Physical: 'movement' }

export function TheatreView({ id, tab, brief, live, go }: { id: string; tab?: string; brief: Brief; live?: LiveMap; go: Go }) {
  const q = useTheatre(id)
  const rp = useReplay(), day = rp?.theatres[id] ?? null
  const sub = tab && TABS.includes(tab) ? tab : 'now'
  const bt = brief.theatres.find(t => t.id === id)
  const crumbs = (region?: string): [string, Route?][] => [['Watch', { v: 'brief' }], [region || bt?.region || '']]
  if (q.isPending) return <><Crumbs back={{ v: 'brief' }} items={crumbs()} go={go} /><h1 className="px-5 pt-2 text-[27px] font-semibold tracking-[-0.028em]">{bt?.name || id}</h1><Skeleton lines={6} /></>
  if (q.isError && !q.data) return <><Crumbs back={{ v: 'brief' }} items={crumbs()} go={go} /><h1 className="px-5 pt-2 text-[27px] font-semibold tracking-[-0.028em]">{bt?.name || id}</h1><Failed what={bt?.name || id} error={q.error} /></>
  const t = q.data
  const regionName = brief.regions.find(r => r.theatres.includes(id))?.name || t.region
  const lit = t.tells.filter(x => x.on).length
  const nBases = live ? live.bases.filter(b => b.theatres.includes(id)).length : undefined
  const setTab = (s: string) => go({ v: 'theatre', id, tab: s }, true)
  const on = modelOn(brief, t)
  const dayLit = day ? wiresOn(t, day.wires) : null
  return (
    <div>
      <Crumbs back={{ v: 'brief' }} items={[['Watch', { v: 'brief' }], [regionName]]} go={go} />
      <div className="px-5 pb-3.5 pt-2">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em] max-[899px]:text-[25px]">{t.name}</h1>
          <FollowButton id={id} name={t.name} />
        </div>
        {t.question && !rp && <QuestionLine q={t.question} />}
        <StatusPair t={t} brief={brief} day={rp && day ? { level: day.level, label: shortDate(rp.day) } : null} />
        <div className="mt-2 flex flex-wrap gap-1.5 empty:hidden">
          {rp && day ? (dayLit ? dayLit.length > 0 && <Tag mark="var(--z2)">{dayLit.length} {dayLit.length === 1 ? 'tripwire' : 'tripwires'} lit at the run of {shortDate(rp.day)}</Tag> : <Tag>Tripwires not kept for {shortDate(rp.day)}</Tag>)
            : lit > 0 && <Tag mark="var(--z2)">{lit} {lit === 1 ? 'tripwire' : 'tripwires'} lit</Tag>}
          {t.spillover && t.parents.length > 0 && <Tag>Spillover from {t.parents.map(p => brief.theatres.find(x => x.id === p)?.name || p).join(', ')}</Tag>}
        </div>
        <p className="mt-3 font-serif text-[16.5px] leading-[1.42] text-fg [text-wrap:pretty]">{rp && day ? daySummary(t.name, rp.day, day.level, dayLit && dayLit.map(x => wireName(x))) : summary(t, on)}</p>
        {rp && <p className="mt-1.5 text-[11.5px] text-fg2">Replaying {shortDate(rp.day)}: the level and the tripwires (here and in the Overview's Tripwires block) are that day's, and the context tag is hidden. Live, as today: the reading below, the Ground, Signals and History tabs and the rest of the Overview.</p>}
      </div>
      <Gauge t={t} active={on} today={!!rp} />
      <Tabs id="th" label={`${t.name} dossier`} value={sub} onChange={setTab} panel sticky
        tabs={[['now', 'Overview'], ['ground', 'Ground', nBases], ['signals', 'Signals', t.signals.total], ['history', 'History', t.events.length]]} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={sub} {...tabPanel('th', sub)} className="outline-none" initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: [.22, 1, .36, 1] }}>
          {sub === 'now' && <Overview t={t} brief={brief} on={on} go={go} />}
          {sub === 'ground' && <GroundTab id={id} t={t} live={live} brief={brief} go={go} />}
          {sub === 'signals' && <SignalsTab t={t} go={go} />}
          {sub === 'history' && <HistoryTab t={t} brief={brief} on={on} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/* The reading on its track. Grey at every value: it has shown no skill as a forecast. The Watch, Elevated and Critical ticks are
   drawn only while the model is off, because only then does the reading set the level. Where the lines sit comes from the data
   (theatre.lines, added November 2026); older data has none, and then Watch is 50, Critical 90 and there is no Elevated tick. */
/* The score is rounded to 0.1 and the lines to 0.01, while the level is set from the unrounded reading against the unrounded
   thresholds (engine.theatre_composite): a score up to 0.1 under a line its level has reached is at that line, so neither the number
   nor the words ("held") can come from rounding alone. */
const LEVEL_RANK: Record<string, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }
function Gauge({ t, active, today = false }: { t: Theatre; active: boolean; today?: boolean }) {
  const L = t.lines, W = L?.watch ?? 50, C = L?.critical ?? 90, E = L && L.elevated > W && L.elevated < C ? L.elevated : null
  /* only while the reading sets the level (the model off) does the level say which lines the reading reached */
  const reached = active ? [] : ([[W, 1], [E, 2], [C, 3]] as [number | null, number][]).filter(([x, k]) => x != null && (LEVEL_RANK[t.level] ?? -1) >= k).map(([x]) => x!)
  const s = t.score == null ? null : reached.reduce((v, x) => v < x && v >= x - 0.1 ? x : v, Math.max(0, Math.min(100, t.score)))
  const marks = E == null ? [W, C] : [W, E, C]
  const w = s == null ? null : wholeAt(s, marks)
  const line = !active
  /* while the reading sets the level, the words follow the level the pipeline set (it can hold a level across a line) */
  const B = ({ children }: { children: ReactNode }) => <b className="font-medium text-fg">{children}</b>
  const below = (to: number, name: string) => { const n = lineWhole(to) - w!; return <><B>{n} {n === 1 ? 'point' : 'points'}</B> below {name}</> }
  const say: ReactNode = s == null || w == null ? 'No reading today'
    : !line ? null
    : t.level === 'Normal' ? (s < W ? below(W, 'Watch') : <><B>At</B> the Watch line, level not raised</>)
    : t.level === 'Critical' ? (s >= C ? <><B>Past</B> the Critical line</> : <>Level <B>held</B> at Critical</>)
    : t.level === 'Elevated' ? (E == null ? (s >= W ? <><B>Past</B> the Watch line</> : <>Level <B>held</B> at Elevated</>) : s >= E ? <><B>Past</B> the Elevated line</> : <>Level <B>held</B> at Elevated</>)
    : s >= W ? (E != null && s < E ? <><B>Past</B> the Watch line, {below(E, 'Elevated')}</> : <><B>Past</B> the Watch line</>) : <>Level <B>held</B> at {levelWord(t.level)}</>
  const grey = (a: number) => `color-mix(in srgb, var(--fg3) ${a}%, transparent)`
  const track = E == null ? `linear-gradient(90deg, var(--z0) 0 ${W}%, ${grey(26)} ${W}% ${C}%, ${grey(46)} ${C}%)`
    : `linear-gradient(90deg, var(--z0) 0 ${W}%, ${grey(20)} ${W}% ${E}%, ${grey(32)} ${E}% ${C}%, ${grey(46)} ${C}%)`
  const ticks: [number, string, boolean][] = [[W, `Watch ${lineWhole(W)}`, false], ...(E != null ? [[E, `Elevated ${lineWhole(E)}`, true] as [number, string, boolean]] : []), [C, `Critical ${lineWhole(C)}`, false]]
  return (
    <section aria-label="Reading" className="mx-5 mb-3.5 rounded-r3 border border-line bg-s2 px-4 pb-3 pt-3.5">
      <h2 className="eyebrow mb-2.5"><Explain k="unusual">Reading</Explain>, 0 to 100{today && <span>, today, live</span>}</h2>
      <div className="flex items-end justify-between gap-3">
        <p className="num whitespace-nowrap text-[46px] font-medium leading-[.9] tracking-[-0.045em] text-fg2">{w ?? '–'}<span className="ml-1.5 text-[13px] font-normal tracking-normal text-fg3">of 100</span></p>
        <p className="text-right text-[12.5px] leading-[1.35] text-fg2">{say}{say && <br />}Level today: {levelWord(t.level)}</p>
      </div>
      <div className={`relative ${line ? (E != null ? 'mb-8' : 'mb-5') : 'mb-3.5'} mt-3.5 h-2.5 rounded-[5px]`} aria-hidden
        style={{ background: line ? track : 'var(--z0)' }}>
        {s != null && <motion.i className="absolute inset-y-0 left-0 rounded-[5px] bg-fg2" initial={{ width: 0 }} animate={{ width: `${Math.max(s, 1.2)}%` }} transition={{ duration: .22, ease: [.2, .8, .2, 1] }} />}
        {line && ticks.map(([x, l, low]) => (
          <i key={l} className="absolute -bottom-[3px] -top-[3px] w-px bg-fg3" style={{ left: `${x}%`, bottom: low ? -15 : undefined }}><em className={`absolute left-0 ${low ? 'top-[29px]' : 'top-[17px]'} -translate-x-1/2 whitespace-nowrap text-[10px] not-italic leading-none text-fg3`}>{l}</em></i>))}
      </div>
      {line && <p className="sr-only">{ticks.map(x => x[1]).join(', ')}{E != null ? ' on this theatre\'s scale' : ''}.</p>}
      {!today && <TrendLine t={t} W={W} />}
      {!today && t.shares && <Shares t={t} />}
      <Facts items={[
        [<>{t.tells.filter(x => x.on).length}<span className="text-[12px] font-normal text-fg3"> / {t.tells.length}</span></>, <><Explain k="tripwire">tripwires</Explain> lit</>],
        [t.signals.strong, <><Explain k="strong">strong signals</Explain> of {t.signals.scored} scoring</>],
        [t.confidence || 'n/a', 'confidence in the reading'],
      ]} />
    </section>
  )
}

/* ---------------------------------------------------------------- the two answers */
/* Every theatre answers two questions, side by side and labelled: Now, what is happening (set by hand with the context line, in the
   ivory kept for things that happened, never in warning colour), and Build-up, whether its signals are building (the level). A war
   under way can read Steady: the pair says so plainly instead of one word answering both. */
function StatusPair({ t, brief, day }: { t: Theatre; brief: Brief; day: { level: string | null; label: string } | null }) {
  const lv = day ? day.level : t.level
  const lit = t.tells.filter(x => x.on).length
  const W = t.lines?.watch ?? 50, s = t.score
  const gap = !day && s != null && !modelOn(brief, t) && t.level === 'Normal' && s < W ? Math.max(1, lineWhole(W) - wholeAt(s, [W])) : null
  const cell = 'flex min-w-0 flex-col gap-1 px-3.5 py-3'
  return (
    <div className="mt-3 grid grid-cols-2 overflow-hidden rounded-r2 border border-line2" role="group" aria-label="Two answers">
      <div className={cell}>
        <span className="eyebrow"><Explain k="now">Now</Explain></span>
        {t.now && !day ? <span className="text-[16px] font-medium leading-[1.25]"><NowMark now={t.now} word={false} className="mr-2 align-[1px]" /><span className="text-happened">{t.context || NOW_WORD[t.now]}</span></span>
          : <span className="text-[16px] font-medium leading-[1.25] text-fg2">{day ? 'Not kept' : 'No fighting set'}</span>}
        <span className="text-[12px] leading-[1.4] text-fg3">{day ? `The Now answer is not kept per day.` : t.now ? `Set by hand${t.contextChecked ? `, checked ${shortDate(t.contextChecked)}` : ''}. It never changes the build-up.` : 'Nothing under way is set by hand for this theatre.'}</span>
      </div>
      <div className={`${cell} border-l border-line2`}>
        <span className="eyebrow"><Explain k="buildup">Build-up</Explain>{day && `, ${day.label}`}</span>
        <span className="text-[16px] font-medium leading-[1.25]" style={{ color: lv === 'Critical' ? 'var(--crit)' : lv === 'Elevated' ? 'var(--z3-text)' : lv === 'Watch' ? 'var(--z2-text)' : 'var(--fg)' }}>{lv ? levelWord(lv) : 'Not kept'}</span>
        <span className="text-[12px] leading-[1.4] text-fg3">{day ? 'The level at that day\'s first run.' : gap != null ? `${gap} ${gap === 1 ? 'point' : 'points'} below the Watch line.` : lv === 'Normal' ? 'Signals near their usual levels.' : 'Signals well away from their usual levels.'}{!day && lit > 0 ? ` ${lit} ${lit === 1 ? 'tripwire' : 'tripwires'} lit.` : ''}</span>
      </div>
    </div>
  )
}

/* The question the theatre opens with (config.QUESTIONS) and its one-line answer from a named series. Context: not in the reading. */
function QuestionLine({ q }: { q: NonNullable<Theatre['question']> }) {
  return (
    <div className="mt-3">
      <p className="font-serif text-[17px] leading-[1.4] text-fg [text-wrap:pretty]"><span className="text-fg2">{q.q}</span> <b className="font-medium">{q.word}</b> {q.say}</p>
      <p className="mt-1 text-[11.5px] leading-[1.4] text-fg3">{q.label.replace(/\s*\(([^)]*)\)\s*$/, '')} · {q.url ? <a href={q.url} target="_blank" rel="noreferrer" className="lnk !text-fg3">{(q.label.match(/\(([^)]*)\)\s*$/) || [])[1] || 'source'}</a> : 'source'} · latest {shortDate(q.last.slice(0, 10))} · <Explain k="context">context</Explain>, not in the reading</p>
    </div>
  )
}

/* The reading over the last 30 days (rebuilt from each group's history with today's lines), with the Watch line, and its change */
function TrendLine({ t, W }: { t: Theatre; W: number }) {
  const [ref, w] = useWidth<HTMLSpanElement>()
  const tr = t.trend || [], v = tr.map(x => x[1]), known = v.filter((x): x is number => x != null)
  if (known.length < 2) return null
  const last = tr[tr.length - 1][1], prevAt = tr.length - 8 >= 0 ? tr[tr.length - 8][1] : null
  const ch = last != null && prevAt != null ? last - prevAt : null
  const H = 34, lo = 0, hi = Math.max(100, ...known)
  const X = (i: number) => (i / Math.max(1, v.length - 1)) * (w - 4) + 2, Y = (y: number) => H - 2 - ((y - lo) / (hi - lo)) * (H - 4)
  const d = v.map((y, i) => y == null ? '' : `${i && v[i - 1] != null ? 'L' : 'M'}${X(i).toFixed(1)},${Y(y).toFixed(1)}`).join('')
  return (
    <div className="mt-1 border-t border-line pt-2.5">
      <div className="mb-1 flex items-baseline justify-between gap-3 text-[11.5px] text-fg3"><span>Last {v.length} days, rebuilt from each signal's history</span>
        <span className="num shrink-0 text-fg2">{ch == null ? 'no change kept' : `${fmtChange(ch)} over 7 days`}</span></div>
      <span ref={ref} className="block w-full" style={{ height: H }} role="img" aria-label={`Reading over the last ${v.length} days, from ${Math.round(known[0])} to ${Math.round(known[known.length - 1])}${ch == null ? '' : `, ${fmtChange(ch)} over 7 days`}. The dashed line is Watch at ${lineWhole(W)}.`}>
        {w > 0 && <svg width={w} height={H} className="overflow-visible" aria-hidden>
          <line x1={0} x2={w} y1={Y(W)} y2={Y(W)} stroke="var(--fg3)" strokeDasharray="2 3" strokeWidth={1} />
          <path d={d} fill="none" stroke="var(--fg2)" strokeWidth={1.5} strokeLinejoin="round" />
          {last != null && <circle cx={X(v.length - 1)} cy={Y(last)} r={2.6} fill="var(--fg)" />}
        </svg>}
      </span>
    </div>
  )
}

/* How the reading is made: each group's share as its own labelled bar, the same ink for every group, so no pale shade has to be told
   apart. A row opens its top signals below it; the rows themselves never move or resize on hover. */
function Shares({ t }: { t: Theatre }) {
  const [open, setOpen] = useState<Group | null>(null)
  const sh = t.shares || {}
  const rows = GROUPS.map(g => [g, sh[g] ?? 0] as const).sort((a, b) => b[1] - a[1])
  return (
    <div className="mt-2.5 border-t border-line pt-2.5">
      <p className="mb-1.5 text-[11.5px] text-fg3">What makes up the reading</p>
      <ul>{rows.map(([g, p]) => { const on = open === g, top = t.groups[g]?.top || []; return (
        <li key={g}>
          <button onClick={() => setOpen(on ? null : g)} aria-expanded={on} aria-controls={`share-${g}`} disabled={!top.length}
            className="grid min-h-7 w-full grid-cols-[72px_minmax(0,1fr)_40px_12px] items-center gap-2.5 rounded-r1 text-left text-[12.5px] transition-colors duration-[120ms] enabled:hover:text-fg disabled:cursor-default max-[899px]:min-h-11">
            <span className={on ? 'text-fg' : 'text-fg2'}>{g}</span>
            <span className="relative h-2 rounded-[2px] bg-z0" aria-hidden><i className="absolute inset-y-0 left-0 rounded-[2px] bg-fg2" style={{ width: `${Math.max(p, p > 0 ? 1.5 : 0)}%` }} /></span>
            <span className="num text-right font-medium text-fg">{Math.round(p)}%</span>
            {top.length ? <ChevronDown size={12} aria-hidden className={`text-fg3 transition-transform duration-[120ms] ${on ? 'rotate-180' : ''}`} /> : <span />}
          </button>
          <AnimatePresence initial={false}>{on && (
            <motion.ul id={`share-${g}`} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: .2, ease: [.2, .8, .2, 1] }} className="overflow-hidden pl-[82px] max-[420px]:pl-0">
              {top.slice(0, 3).map(x => <li key={x.id} className="flex justify-between gap-3 py-[3px] text-[12px] text-fg2"><span className="min-w-0 truncate">{x.label}</span><span className="num shrink-0 text-fg">{fmtZ(x.z)}</span></li>)}
              <li className="h-1" aria-hidden />
            </motion.ul>)}
          </AnimatePresence>
        </li>) })}
      </ul>
    </div>
  )
}

/* ---------------------------------------------------------------- Situation */
/* The theatre's context numbers (contract.situation): each with its value, its change over 7 days, what is usual, and its source and
   licence. Grey and tagged: none of them is in the reading, and none gets warning colour until it passes the same tests. */
const fmtN = (x: number) => Math.abs(x) >= 100 ? Math.round(x).toLocaleString('en-GB') : Math.abs(x) >= 10 ? x.toFixed(0) : x.toFixed(1).replace(/\.0$/, '')
function Situation({ t }: { t: Theatre; go: Go }) {
  const L = t.situation || []
  return (
    <Block title="Situation" aside={<><Explain k="context">context</Explain>, not in the reading</>}>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,190px),1fr))] gap-2">
        {L.map(c => (
          <li key={c.id} className="flex min-w-0 flex-col gap-1 rounded-r2 border border-line bg-s2 px-3 py-2.5">
            <span className="flex items-baseline gap-2"><b className="num text-[20px] font-medium leading-none tracking-[-0.02em]">{fmtN(c.value)}</b>
              {c.change7 != null && <span className="num text-[11.5px] text-fg2">{c.change7 === 0 ? '0' : (c.change7 > 0 ? '+' : '−') + fmtN(Math.abs(c.change7))} in 7 days</span>}</span>
            {/* the label always takes two lines, so the usual line and the source sit at the same height in every card of a row */}
            <span className="line-clamp-2 min-h-[calc(2*1.35em)] text-[12px] leading-[1.35] text-fg2">{c.label.replace(/\s*\([^)]*\)\s*$/, '')}</span>
            <span className="text-[11px] leading-[1.4] text-fg3">{c.usual ? `Usual ${fmtN(c.usual.median)} (${fmtN(c.usual.low)}–${fmtN(c.usual.high)})` : 'No usual level yet'} · {shortDate(c.last.slice(0, 10))}</span>
            <span className="text-[11px] leading-[1.4] text-fg3">{c.url ? <a href={c.url} target="_blank" rel="noreferrer" className="lnk !text-fg3">{c.source}</a> : c.source}, {c.licence}</span>
          </li>))}
      </ul>
    </Block>
  )
}

/* ---------------------------------------------------------------- Overview */
function Overview({ t, brief, on, go }: { t: Theatre; brief: Brief; on: boolean; go: Go }) {
  return <>
    {(t.situation?.length ?? 0) > 0 && <Situation t={t} go={go} />}
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
      {on
        ? 'The level comes from the 30-day model, which has passed its checks. The reading measures how unusual today is and are not a chance of war.'
        : held(brief, t)
        ? 'The build-up level comes from the reading alone, which measures how unusual today is and are not a chance of war. The 30-day model has passed its checks overall but not yet for this theatre, so it gives no chance here.'
        : 'The build-up level comes from the reading alone, which measures how unusual today is and are not a chance of war. A 30-day chance model runs in shadow: its figures are on the History tab and do not set the level.'}{' '}
      <Lnk to={{ v: 'record' }} go={go} className="lnk">See the record</Lnk>
    </Note>
  </>
}

/* Build-up, slow to fast: each group's last 60 days as cells shaded by how unusual the day was (the board's own steps) */
function Ladder({ t, brief, go }: { t: Theatre; brief: Brief; go: Go }) {
  const [open, setOpen] = useState<Group | null>(null)
  const end = parseGen(brief.generated).getTime()
  const day = (k: number) => shortDate(new Date(end - k * 864e5).toISOString().slice(0, 10))
  const n = Math.max(0, ...GROUPS.map(g => (t.groups[g]?.history || []).slice(-60).length))
  const cols = 'grid grid-cols-[70px_minmax(0,1fr)_36px] gap-2.5'
  return (
    <Block title={<><Explain k="group">Build-up</Explain>, slow to fast</>} aside={`${n > 1 ? `${n} days` : 'Daily'}, darker is more unusual`}>
      {GROUPS.map(g => {
        const d = t.groups[g], h = (d?.history || []).slice(-60), on = open === g
        const vals = h.filter((v): v is number => v != null), peak = vals.length ? Math.max(...vals) : null
        return (
          <div key={g}>
            <button onClick={() => setOpen(on ? null : g)} aria-expanded={on} aria-controls={`lad-${g}`}
              className={`${cols} -mx-2 w-[calc(100%+16px)] items-center max-[899px]:min-h-11 rounded-r1 px-2 py-1 text-left hover:bg-s2`}>
              <span className="text-[12.5px] leading-[1.15] text-fg">{g}<small className="block text-[10.5px] text-fg3">{GLOSS[g]}</small></span>
              <span className="grid h-[18px] gap-px" aria-hidden style={{ gridTemplateColumns: `repeat(${Math.max(h.length, 1)}, minmax(0,1fr))` }}>
                {h.map((z, i) => <i key={i} className="rounded-[1px]" style={{ background: groupTone(z) }} />)}
              </span>
              <span className="num flex items-center justify-end gap-0.5 text-[12px] font-medium text-fg2">{d?.z == null ? '–' : stepFixed(d.z)}<ChevronDown size={11} aria-hidden className={`shrink-0 text-fg3 transition-transform ${on ? 'rotate-180' : ''}`} /></span>
              <span className="sr-only">{`: ${d?.z == null ? 'no reading today' : `${stepFixed(d.z)} standard deviations from usual today`}${peak != null ? `, highest ${peak.toFixed(1)} in the last ${h.length} days` : ', no reading in the last 60 days'}. Show its top signals.`}</span>
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
        <span />{n > 1 ? <span className="flex justify-between"><span>{day(n - 1)}</span>{n > 20 && <span>{day(Math.round((n - 1) / 2))}</span>}<span>today</span></span> : <span />}<span />
      </div>
    </Block>
  )
}

/* the theatre's tripwires that the feed shows fired in a replayed week, each with its latest day (feed titles are the rules' names) */
/* the theatre's tripwires lit at a replayed day's run (the ids contract.day_wires kept); null when that day was not kept */
function wiresOn(t: Theatre, ids: string[] | null): Tell[] | null {
  return ids && t.tells.filter(x => ids.includes(x.id))
}
function daySummary(name: string, day: string, level: string | null, wires: string[] | null): string {
  const d = shortDate(day)
  const a = level ? `At the first run of ${d}, ${name} was ${level === 'Normal' ? 'steady' : `at ${level}`}.` : `${name}'s level was not kept for ${d}.`
  const b = !wires ? ` Which tripwires were lit that day was not kept.`
    : wires.length ? ` ${countWord(wires.length)} ${wires.length === 1 ? 'tripwire was' : 'tripwires were'} lit at the run of ${d}: ${wires.map(w => w.toLowerCase()).join(', ')}.` : ` No tripwire was lit at the run of ${d}.`
  return a + b
}
/* follow: keep this theatre at the top of the board, in this browser */
function FollowButton({ id, name }: { id: string; name: string }) {
  const { has, toggle } = useFollow(), on = has(id)
  return <button onClick={() => toggle(id)} data-follow={id} aria-pressed={on} aria-label={on ? `Following ${name}, press to stop` : `Follow ${name}`} title={on ? 'Following: it sits at the top of the board in this browser' : 'Keep it at the top of the board in this browser'}
    className={`tap mt-1 inline-flex min-h-8 pointer-coarse:min-h-11 shrink-0 items-center gap-1.5 rounded-r2 border px-2.5 text-[12px] transition-colors duration-[120ms] ${on ? 'border-line2 bg-s3 text-fg' : 'border-line text-fg2 hover:border-line2 hover:text-fg'}`}>
    <Pin size={13} aria-hidden fill={on ? 'currentColor' : 'none'} />{on ? 'Following' : 'Follow'}</button>
}

/* Tripwires: fixed rules over the last 7 days. Lit ones first, with the day they fired; every one with its record, plainly:
   most firings were not followed by anything. Each opens to the rule it checks. */
const year = (d?: string) => d ? d.slice(0, 4) : ''
const monthYear = (d: string) => new Date(d.slice(0, 10) + 'T00:00Z').toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).replace('Sept', 'Sep')
export function recordLine(x: Tell): string {
  const r = x.record
  if (!r || r.episodes == null) return 'New, no record yet'
  /* the record is summed over every theatre the rule was replayed on (tells.py), so the row says so */
  const where = r.theatres ? ` across ${r.theatres} ${r.theatres === 1 ? 'theatre' : 'theatres'}` : ''
  if (!r.episodes) return `Has not fired${where} since the record began${r.first ? ` in ${year(r.first)}` : ''}`
  return `Fired ${r.episodes} ${r.episodes === 1 ? 'time' : 'times'}${where} since ${year(r.first)}, ${r.hits ?? 0} followed by an event`
}
function Tripwires({ t: today }: { t: Theatre }) {
  const [open, setOpen] = useState<string | null>(null)
  /* replaying, a tripwire is lit when the record shows it lit at that day's run; a day not kept lights none and says so */
  const rp = useReplay(), day = rp?.theatres[today.id], unknown = !!day && !day.wires
  const t = useMemo(() => { if (!day) return today; const m = new Set((wiresOn(today, day.wires) || []).map(x => x.id)); return { ...today, tells: today.tells.map(x => ({ ...x, on: m.has(x.id), date: null })) } }, [today, day])
  const list = useMemo(() => [...t.tells.filter(x => x.on).sort((a, b) => (b.date || '').localeCompare(a.date || '')), ...t.tells.filter(x => !x.on)], [t])
  const lit = list.filter(x => x.on).length
  const eps = t.tells.reduce((n, x) => n + (x.record?.episodes || 0), 0), hits = t.tells.reduce((n, x) => n + (x.record?.hits || 0), 0)
  return (
    <Block title={<Explain k="tripwire">Tripwires</Explain>} aside={rp ? (unknown ? `not kept for ${shortDate(rp.day)}` : `${lit} of ${t.tells.length} lit at the run of ${shortDate(rp.day)}`) : `${lit} of ${t.tells.length} lit, fixed rules over 7 days`}>
      {unknown && <p className="-mt-1 mb-2 text-[11.5px] text-fg2">Which tripwires were lit on {shortDate(rp!.day)} was not kept. The rules are listed without a state.</p>}
      {/* the twelve lamps, always in the same order and place, so a lit one is found at a glance */}
      <ul className="mb-2.5 grid grid-cols-2 gap-1.5 min-[620px]:grid-cols-3" aria-label="All tripwires">
        {t.tells.map(x => <li key={x.id} title={`${wireName(x)}${x.on ? ', lit' : ''}`} className={`flex min-h-8 min-w-0 items-center gap-2 rounded-r1 border px-2.5 py-1 text-[12px] leading-[1.25] ${x.on ? 'border-[color-mix(in_srgb,var(--z2)_55%,transparent)] text-fg' : 'border-line text-fg3'}`}>
          <i aria-hidden className={`h-2 w-2 shrink-0 rounded-full border ${x.on ? 'tw-lit border-z2 bg-z2' : unknown ? 'border-dashed border-line2' : 'border-line2 bg-z0'}`} /><span className="min-w-0">{wireName(x)}</span><span className="sr-only">{x.on ? ', lit' : ''}</span></li>)}
      </ul>
      <ul className="grid gap-1.5">
        {list.map(x => { const on = open === x.id, r = x.record; return (
          <li key={x.id} className="rounded-r2 border" style={{ borderColor: x.on ? 'color-mix(in srgb, var(--z2) 55%, transparent)' : 'var(--line)', background: x.on ? 'color-mix(in srgb, var(--z2) 7%, var(--s2))' : 'var(--s2)' }}>
            <button onClick={() => setOpen(on ? null : x.id)} aria-expanded={on} aria-controls={`tw-${x.id}`} className="grid w-full grid-cols-[10px_minmax(0,1fr)_14px] items-start gap-2.5 rounded-r2 px-2.5 py-2 text-left">
              <i aria-hidden className={`mt-[5px] h-2 w-2 rounded-full border ${x.on ? 'tw-lit' : ''} ${unknown ? 'border-dashed' : ''}`} style={{ background: x.on ? 'var(--z2)' : unknown ? 'transparent' : 'var(--z0)', borderColor: x.on ? 'var(--z2)' : 'var(--line2)' }} />
              <span className="min-w-0">
                <span className="flex flex-wrap items-baseline gap-x-2 text-[12.5px] font-medium leading-[1.3] text-fg">{wireName(x)}
                  {x.on && <span className="num text-[11.5px] font-normal text-fg2">{rp ? `Lit at the run of ${shortDate(rp.day)}` : x.date ? `Fired ${shortDate(x.date)}` : 'Fired this week'}</span>}
                  <span className="sr-only">{unknown ? ', not kept for that day' : x.on ? ', lit' : ', not lit'}.</span></span>
                {x.on && r?.episodes ? <HitRates r={r} /> : <>
                <span className={`mt-0.5 block text-[11px] leading-[1.35] ${x.on ? 'text-fg2' : 'text-fg3'}`}>{recordLine(x)}<span className="sr-only">.</span></span>
                {r?.events ? <span className={`block text-[11px] leading-[1.35] ${x.on ? 'text-fg2' : 'text-fg3'}`}>Fired before {r.caught ?? 0} of {r.events} past events</span> : null}</>}
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
      {eps > 0 && <p className="mt-2.5 text-[11.5px] leading-[1.45] text-fg3">Across all watched theatres, {hits} of {eps} past firings of these rules were followed by an event. A lit tripwire is a reason to look closer, not a forecast.</p>}
    </Block>
  )
}

/* A lit tripwire's record as two strips: how often an event followed when it fired, and how many past events it fired before.
   One tick per firing or event up to 120; past that, one bar filled to the share. Ink only, and a verdict from fixed wording rules. */
function Strip({ k, n, label }: { k: number; n: number; label: string }) {
  return (
    <span className="mt-1.5 block">
      <span className="flex justify-between gap-3 text-[11.5px] leading-[1.3] text-fg2"><span>{label}</span><b className="num shrink-0 font-medium text-fg">{k} of {n}</b></span>
      <span role="img" aria-label={`${k} of ${n}`} className="mt-1 flex h-2.5 gap-px">
        {n <= 120 ? Array.from({ length: n }, (_, i) => <i key={i} className={`min-w-px flex-1 ${i < k ? 'bg-fg' : 'bg-z0'}`} />)
          : <i className="relative block flex-1 bg-z0"><i className="absolute inset-y-0 left-0 bg-fg" style={{ width: `${Math.max(.8, 100 * k / n)}%` }} /></i>}
      </span>
    </span>
  )
}
function HitRates({ r }: { r: NonNullable<Tell['record']> }) {
  const a = (r.hits ?? 0) / Math.max(1, r.episodes ?? 0), b = r.events ? (r.caught ?? 0) / r.events : null
  const verdict = a >= .25 ? 'Often followed by an event.' : a >= .1 ? 'Sometimes followed by an event.' : b != null && b < .1 ? 'Rarely followed by an event, and rarely there before one.' : 'Rarely followed by an event.'
  return <span className="mt-0.5 block">
    <Strip k={r.hits ?? 0} n={r.episodes ?? 0} label={`When it fired${r.theatres ? ` (${r.theatres} theatres)` : ''}, an event followed`} />
    {r.events ? <Strip k={r.caught ?? 0} n={r.events} label="Past events it fired before" /> : null}
    <span className="mt-1.5 block text-[11.5px] leading-[1.4] text-fg2">{verdict} A reason to look closer, not a forecast.</span>
  </span>
}

/* ---------------------------------------------------------------- Signals */
function SignalsTab({ t, go }: { t: Theatre; go: Go }) {
  const q = useSignals()
  const all = useMemo(() => (q.data?.signals || []).filter(s => s.theatre === t.id), [q.data, t.id])
  const top = useMemo(() => all.filter(s => s.z != null).sort((a, b) => Math.abs(b.z!) - Math.abs(a.z!)).slice(0, 14), [all])
  return (
    <Block title="Most unusual now" aside="against each signal's own history">
      {q.isPending ? <Skeleton lines={8} /> : q.isError && !q.data ? <Failed what="the signals" error={q.error} />
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
function HistoryTab({ t, brief, on }: { t: Theatre; brief: Brief; on: boolean }) {
  /* the pipeline writes null where the usual chance is missing: draw only the days that have a value */
  const rows = t.history.filter((x): x is [string, number, number, string] => x[1] != null && Number.isFinite(x[1]))
  const hs = rows.map(x => x[1]), last = rows[rows.length - 1]
  const events = useMemo(() => [...t.events].sort((a, b) => b.date.localeCompare(a.date)), [t.events])
  const [all, setAll] = useState(false)
  const c = t.chance, pct = (p: number) => `${Math.round(p * 100)}%`
  const big = (k: string) => ['strike', 'war', 'onset', 'invasion'].includes(k)
  return <>
    {hs.length > 1 && <Block title={<Explain k="standing">Standing risk</Explain>} aside={`since ${shortDate(rows[0][0])}`}>
      <div className="flex items-center gap-3.5">
        <span role="img" aria-label={`Standing risk since ${shortDate(rows[0][0])}, from ${hs[0]} to ${last[1]} times the usual chance. Lowest ${Math.min(...hs)}, highest ${Math.max(...hs)}.`} className="min-w-0 flex-1">
          <SizedSpark v={hs} h={44} />
        </span>
        <span className="num shrink-0 text-right text-[12.5px] leading-[1.3] text-fg2">{last[1].toFixed(2)}×<small className="block text-[11px] text-fg3">usual, today</small></span>
      </div>
      <p className="mt-1.5 text-[11px] leading-[1.45] text-fg3">{on ? "The model's 30-day chance here, divided by its usual chance. The model has passed its checks and sets the level."
        : `The shadow model's 30-day chance here, divided by its usual chance. ${brief.model.gates?.pass || brief.model.active ? 'It does not set the level for this theatre.' : 'It has not passed its tests and does not set the level.'}`}</p>
    </Block>}
    {hs.length === 1 && <Block title={<Explain k="standing">Standing risk</Explain>}><p className="text-[12px] text-fg2"><span className="num">{last[1].toFixed(2)}×</span> the usual chance on {shortDate(last[0])}. Too few days to draw.</p></Block>}
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
      <b>{on || held(brief, t) ? 'The 30-day model.' : 'Shadow model.'}</b>{' '}
      {held(brief, t) ? 'The 30-day model has passed its checks overall but not yet for this theatre, so it gives no chance here and the build-up level comes from the reading.'
        : <>{c.p != null ? <>It puts the 30-day chance of a qualifying event in {t.name} at {pct(c.p)}{c.lo != null && c.hi != null ? ` (${pct(c.lo)} to ${pct(c.hi)})` : ''}{c.usual != null ? `, against a usual ${pct(c.usual)}` : ''}. </> : 'It gives no chance for this theatre today. '}
          {gatesSentence(brief.model.gates, on)}</>}
    </Note>
  </>
}

/* a sparkline that fills its box: measured once, then drawn at that width */
function SizedSpark({ v, h }: { v: number[]; h: number }) {
  const [ref, w] = useWidth<HTMLSpanElement>()
  return <span ref={ref} className="block w-full" style={{ height: h }}>{w > 0 && <Spark v={v} w={w} h={h} stroke="var(--fg2)" fill={false} />}</span>
}
