import { useEffect, useMemo, useRef, useState, type ReactNode, type KeyboardEvent } from 'react'
import { motion } from 'motion/react'
import NumberFlow from '@number-flow/react'
import { GROUPS, short, levelWord, groupTone, feedDetail, fmtZ, fmtChange, shortDate, parseGen, isKey, NOW_WORD, type Brief, type BriefTheatre, type FeedItem, type Route, wholeScore } from './data'
import { usePrefs, fmtTime } from './settings'
import { toRoute } from './views'
import { feedKey, type Since } from './since'
import { Explain, NowMark, hoverTheatre, useHoveredTheatre } from './ui'
import { X, Pin, ChevronLeft, ChevronRight } from 'lucide-react'
import { useFollow } from './follow'
import { useReplay, minusDays, WINDOW, isWave, type Replay, type DayTheatre } from './replay'

/* Watch: the dispatch, the theatre board, what changed, and the 30-day timeline under the map. Everything here is written
   from brief.json in the browser. The 0 to 100 "unusual readings" number has shown no predictive skill, so its meter and
   number stay grey at every value; colour on the board belongs to the signal groups and the tripwires. */

type Go = (r: Route) => void
const EASE = [.2, .8, .2, 1] as const
const RANK: Record<string, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }
const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']
const word = (n: number, cap = false) => { const w = WORDS[n] ?? String(n); return cap ? w[0].toUpperCase() + w.slice(1) : w }
const byScore = (a: BriefTheatre, b: BriefTheatre) => (b.score ?? -1) - (a.score ?? -1)
/* theatres at Watch or above, highest level first; and the quiet theatre with the highest reading */
const above = (b: Brief) => b.theatres.filter(t => t.level !== 'Normal').sort((x, y) => RANK[y.level] - RANK[x.level] || byScore(x, y))
const closest = (b: Brief) => b.theatres.filter(t => t.level === 'Normal' && t.score != null).sort(byScore)[0]
/* the line of 50 sets the level only while the forecast model is off; then a quiet theatre under it is "closest to Watch" */
/* the line sets a theatre's level while the model is off, or while the model passes but holds this sub-theatre (it then gives
   it no chance, so no standing risk) */
const lineSets = (b: Brief, t: BriefTheatre) => !b.model.active || t.standingRisk == null
const underLine = (b: Brief, t?: BriefTheatre) => !!t && lineSets(b, t) && t.score! < 50
const utcDay = (d: Date) => d.toISOString().slice(0, 10)

/* ---------------------------------------------------------------- the top bar's status sentence */
export function Status({ brief }: { brief: Brief }) {
  const rp = useReplay()
  if (rp) return <ReplayStatus brief={brief} rp={rp} />
  const up = above(brief), near = closest(brief), n = brief.theatres.length
  const sep = <i className="mx-2 inline-block h-3.5 w-px translate-y-[2px] bg-line2" aria-hidden />
  if (up.length) return <><b className="font-medium text-fg">{up.length} of {n} theatres at Watch or above</b>{sep}<span>{up.slice(0, 3).map((t, i) => <span key={t.id}>{i > 0 && ' · '}<span className="whitespace-nowrap">{short(t.name)}, {t.level}</span></span>)}{up.length > 3 ? ' …' : ''}</span></>
  return <><b className="font-medium text-fg">{n} of {n} theatres steady</b>{near && <>{sep}<span>{underLine(brief, near) ? `Closest to Watch: ${short(near.name)}, ${wholeScore(near.score!)} against 50` : `Highest reading: ${short(near.name)}, ${wholeScore(near.score!)}`}</span></>}</>
}

/* ---------------------------------------------------------------- the dispatch card */
export function sentence(brief: Brief): ReactNode {
  const up = above(brief), near = closest(brief)
  const most = [...brief.theatres].sort((a, b) => b.tellsOn - a.tellsOn)[0], n = brief.counts.tells
  const lead = !up.length ? <>Every theatre reads steady. </>
    : up.length === 1 ? <><em>{short(up[0].name)}</em> is at {up[0].level}; every other theatre reads steady. </>
    : <>{word(up.length, true)} theatres are at Watch or above, led by <em>{short(up[0].name)}</em> at {up[0].level}. </>
  const gap = !near ? null : underLine(brief, near) ? <>{up.length ? 'Of the rest, ' : ''}<em>{short(near.name)}</em> comes closest to Watch, at {wholeScore(near.score!)} against a line of 50. </>
    : <>{up.length ? 'Of the rest, ' : ''}<em>{short(near.name)}</em> has the highest reading, at {wholeScore(near.score!)} of 100. </>
  const wires = !n ? 'No tripwire fired this week.'
    : n === 1 ? `One tripwire fired this week, on ${short(most.name)}.`
    : `${word(n, true)} tripwires fired this week, ${most.tellsOn === n ? (n === 2 ? 'both' : 'all of them') : `${word(most.tellsOn)} of them`} on ${short(most.name)}.`
  return <>{lead}{gap}{wires}</>
}

/* the sentence is the page's heading on Watch; with a theatre or base open, that dossier's name is */
export function Dispatch({ brief, heading }: { brief: Brief; heading: boolean }) {
  const H = heading ? 'h1' : 'p'
  const { prefs } = usePrefs()
  const rp = useReplay()
  const at = parseGen(brief.generated)
  const date = at.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: prefs.tz === 'utc' ? 'UTC' : undefined })
  const c = brief.counts
  const still = prefs.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches
  const num = (v: number) => <NumberFlow value={v} animated={!still} transformTiming={{ duration: 200, easing: 'ease-out' }} spinTiming={{ duration: 200, easing: 'ease-out' }} opacityTiming={{ duration: 120, easing: 'ease-out' }} />
  /* replaying: the same card, written from what the day keeps (replay.tsx). A count the data does not keep for that day is a dash
     with the reason, never a zero. */
  const facts: [number | null, ReactNode][] = rp ? replayFacts(rp)
    : [[c.tells, <><Explain k="tripwire">{c.tells === 1 ? 'tripwire' : 'tripwires'}</Explain> fired this week</>], [c.bases, c.bases === 1 ? 'base changed on radar' : 'bases changed on radar'], [c.strong, <>{c.strong === 1 ? 'signal' : 'signals'} reading <Explain k="strong">strong</Explain></>]]
  /* what is usual for the tripwire count: the lit totals at each kept day's run over the last 30 days (contract.day_wires) */
  const usual = rp ? null : litUsual(brief)
  return (
    <section aria-label="Dispatch" className="m-3.5 mb-1.5 rounded-r3 border border-inkline bg-paper px-[18px] pb-3.5 pt-4 text-ink">
      <div className="eyebrow flex flex-wrap items-center gap-x-2 !text-ink2">{rp ? <><span>Replay</span><span>{shortDate(rp.day)}</span></> : <><span>Dispatch</span><span>{date}</span><span>{fmtTime(at, prefs.tz)}</span></>}{brief.demo && <span className="text-crit">demo data</span>}</div>
      <H className="mb-3.5 mt-[11px] font-serif text-[21.5px] font-normal leading-[1.27] tracking-[-0.012em] [text-wrap:pretty]">{rp ? daySentence(brief, rp) : sentence(brief)}</H>
      <dl className="grid grid-cols-3 border-t border-inkline pt-[11px]">
        {facts.map(([v, label], i) => (
          <div key={i} className={`flex flex-col-reverse justify-end ${i ? 'border-l border-inkline pl-3' : ''}`}>
            <dt className="mt-[5px] text-[11.5px] leading-[1.25] text-ink2">{label}{i === 0 && usual && <span className="mt-[3px] block text-[11px] leading-[1.3] text-ink2" title={`Tripwires lit at each day's run across all theatres, over the last ${usual.n} kept days`}>usual {usual.median} <span className="num">({usual.low}–{usual.high})</span></span>}</dt>
            <dd className="num text-[25px] font-medium leading-none tracking-[-0.03em]">{v == null ? <span aria-label="not kept">–</span> : num(v)}</dd>
          </div>))}
      </dl>
      {rp?.partial && <p className="mt-2.5 text-[11.5px] leading-[1.4] text-ink2">The data holds the last 30 days, from {shortDate(rp.feedFrom)}, so anything earlier in this week is missing from the base count.</p>}
    </section>
  )
}

/* the usual lit-tripwire count: the median and range of the totals lit at each kept day's run, today left out; null with under 7 days */
export function litUsual(brief: Brief): { median: number; low: number; high: number; n: number } | null {
  const by = new Map<string, number>(), today = brief.generated.slice(0, 10)
  for (const t of brief.theatres) for (const [d, ids] of t.wires || []) if (d < today) by.set(d, (by.get(d) || 0) + ids.length)
  const v = [...by.values()].sort((a, b) => a - b)
  if (v.length < 7) return null
  return { median: v[Math.floor(v.length / 2)], low: v[0], high: v[v.length - 1], n: v.length }
}

/* the replayed day's three counts: tripwires lit at that day's run, base changes and heat reports in the week to it */
function replayFacts(rp: Replay): [number | null, ReactNode][] {
  const d = shortDate(rp.day), lit = Object.values(rp.theatres).reduce((a, x) => a + (x.wires?.length ?? 0), 0)
  const n = (k: FeedItem['kind'], from = '') => rp.week.filter(f => f.kind === k && f.date.slice(0, 10) >= from).length
  const wk = minusDays(rp.day, WINDOW - 1)
  /* heat: kept from heatFrom only; a day before it has no count, a week that starts before it counts from heatFrom */
  const heat: [number | null, ReactNode] = rp.heatFrom && rp.day < rp.heatFrom ? [null, 'heat reports: not kept that far back']
    : rp.heatFrom && wk < rp.heatFrom ? [n('fire', rp.heatFrom), `${n('fire', rp.heatFrom) === 1 ? 'heat report' : 'heat reports'} from ${shortDate(rp.heatFrom)} to ${d}, as far back as heat is kept`]
    : [n('fire'), `${n('fire') === 1 ? 'heat report' : 'heat reports'} in the week to ${d}`]
  return [
    rp.wiresKept ? [lit, <><Explain k="tripwire">{lit === 1 ? 'tripwire' : 'tripwires'}</Explain> lit at the run of {d}</>] : [null, <><Explain k="tripwire">tripwires</Explain> lit on {d}: not kept</>],
    [n('base'), `${n('base') === 1 ? 'base change' : 'base changes'} on radar in the week to ${d}`],
    heat,
  ]
}

/* a replayed day in words: the levels kept for it (each theatre's level at that day's first run) and the tripwires lit at that run */
function daySentence(brief: Brief, rp: Replay): ReactNode {
  const d = shortDate(rp.day), kept = brief.theatres.filter(t => rp.theatres[t.id].level)
  const up = kept.filter(t => rp.theatres[t.id].level !== 'Normal').sort((x, y) => RANK[rp.theatres[y.id].level!] - RANK[rp.theatres[x.id].level!])
  const missing = brief.theatres.length - kept.length
  const lead = !kept.length ? <>No theatre's level was kept for {d}. </>
    : !up.length ? <>At the first run of {d}, {missing ? `all ${kept.length} theatres with a level kept` : 'every theatre'} read steady. </>
    : up.length === 1 ? <>At the first run of {d}, <em>{short(up[0].name)}</em> was at {rp.theatres[up[0].id].level}; {missing ? 'the others with a level kept' : 'every other theatre'} read steady. </>
    : <>At the first run of {d}, {word(up.length)} theatres were at Watch or above, led by <em>{short(up[0].name)}</em> at {rp.theatres[up[0].id].level}. </>
  const gap = missing && kept.length ? <>{word(missing, true)} {missing === 1 ? 'theatre has' : 'theatres have'} no level kept for that day. </> : null
  if (!rp.wiresKept) return <>{lead}{gap}Which tripwires were lit that day was not kept.</>
  const by = brief.theatres.map(t => [t, rp.theatres[t.id].wires?.length ?? 0] as const).sort((a, b) => b[1] - a[1])
  const w = by.reduce((a, x) => a + x[1], 0), top = by[0]
  const wires = !w ? 'No tripwire was lit at that run.'
    : w === 1 ? `One tripwire was lit at that run, on ${short(top[0].name)}.`
    : `${word(w, true)} tripwires were lit at that run, ${top[1] === w ? (w === 2 ? 'both' : 'all of them') : `${word(top[1])} of them`} on ${short(top[0].name)}.`
  return <>{lead}{gap}{wires}</>
}

/* the top bar's sentence while replaying: the day, and its levels as kept, never today's */
function ReplayStatus({ brief, rp }: { brief: Brief; rp: Replay }) {
  const sep = <i className="mx-2 inline-block h-3.5 w-px translate-y-[2px] bg-line2" aria-hidden />
  const kept = brief.theatres.filter(t => rp.theatres[t.id].level), up = kept.filter(t => rp.theatres[t.id].level !== 'Normal')
  return <><b className="font-medium text-fg">Replaying {shortDate(rp.day)}</b>{sep}<span>{!kept.length ? 'No level kept for that day' : `${up.length} of ${kept.length} theatres with a level kept at Watch or above`}</span></>
}

/* ---------------------------------------------------------------- the theatre board */
export type Order = 'closest' | 'region'
export function Board({ brief, sel, go, order, setOrder }: { brief: Brief; sel: string | null; go: Go; order: Order; setOrder: (o: Order) => void }) {
  const first = useRef(true)
  useEffect(() => { first.current = false }, [])
  const rp = useReplay()
  const { ids: follow } = useFollow()
  const byId = useMemo(() => Object.fromEntries(brief.theatres.map(t => [t.id, t])), [brief])
  /* live: by reading; replaying, the reading is not kept, so by that day's level, then the week's tripwires, then the board's order */
  const sorted = useMemo(() => rp ? brief.theatres.map((t, k) => [t, k] as const).sort(([a, i], [b, j]) => RANK[rp.theatres[b.id].level ?? 'Normal'] - RANK[rp.theatres[a.id].level ?? 'Normal']
    || (rp.theatres[b.id].wires?.length ?? 0) - (rp.theatres[a.id].wires?.length ?? 0) || i - j).map(x => x[0]) : [...brief.theatres].sort(byScore), [brief, rp])
  const line = !rp && brief.theatres.some(t => lineSets(brief, t))
  const pinned = follow.map(id => byId[id]).filter(Boolean)
  const rest = (L: BriefTheatre[]) => L.filter(t => !follow.includes(t.id))
  const row = (t: BriefTheatre, i: number) => <BoardRow key={t.id} t={t} i={i} rise={first.current} on={sel === t.id} line={lineSets(brief, t)} go={go} day={rp ? rp.theatres[t.id] : null} />
  return (
    <section aria-label="Theatres">
      <div className="flex items-center justify-between gap-2.5 px-4 pb-2 pt-4">
        <h2 className="text-[13px] font-semibold tracking-[-0.005em]">Theatres{rp && <span className="font-normal text-fg2">, {shortDate(rp.day)}</span>}</h2>
        <span className="inline-flex rounded-r2 border border-line p-0.5 text-[11.5px]" role="group" aria-label="Order of the board">
          {([['closest', rp ? 'By level' : 'Closest to Watch'], ['region', 'By region']] as const).map(([k, label]) => (
            <button key={k} aria-pressed={order === k} onClick={() => setOrder(k)} className={`relative rounded-[6px] px-2 py-0.5 after:absolute after:inset-x-0 after:-inset-y-3 after:content-[''] transition-colors duration-[120ms] ${order === k ? 'bg-sel text-selink' : 'text-fg2 hover:text-fg'}`}>{label}</button>))}
        </span>
      </div>
      {/* the column heads, on the row's own grid (BOARD_COLS), so each head sits over its column */}
      <div className={`grid h-[22px] ${BOARD_COLS} items-end pb-1 pl-4 pr-7 text-[11px] text-fg3`} aria-hidden>
        <span>Theatre</span>
        <span title="The five signal groups, slowest to move first: Logistics, Markets, People, News, Physical. Taller and warmer is further from usual.">Groups</span>
        <span className="col-span-2" title={rp ? 'The 0 to 100 reading is not kept per day.' : `How unusual today's signals are, 0 to 100.${line ? ' The tick is the Watch line at 50.' : ''}`}>{rp ? 'Not kept' : 'Reading'}</span>
        <span className="text-right" title="The reading's change over the last 7 days">7 d</span>
      </div>
      {pinned.length > 0 && <div role="group" aria-label="Following"><div className="px-4 pb-[5px] pt-1 text-[11px] font-medium text-fg2">Following</div>{pinned.map(row)}<div className="h-2" /></div>}
      {order === 'closest' ? <div role={pinned.length ? 'group' : undefined} aria-label={pinned.length ? 'All theatres' : undefined}>{pinned.length > 0 && <div className="px-4 pb-[5px] pt-1 text-[11px] font-medium text-fg2">All theatres</div>}{rest(sorted).map(row)}</div>
        : brief.regions.map(r => { const L = rest(r.theatres.map(id => byId[id]).filter(Boolean)); return L.length > 0 && <div key={r.id} role="group" aria-label={r.name}><div className="px-4 pb-[5px] pt-3 text-[11px] font-medium text-fg3">{r.name}</div>{L.map(row)}</div> })}
      {rp ? <p className="mx-4 mb-[18px] mt-3 text-[11.5px] leading-normal text-fg3">Each theatre's level is the one shown at the first run of {shortDate(rp.day)}{rp.groupsKept ? ', and the five cells are that day\'s signal groups, rebuilt from each signal\'s own history' : rp.groupsPending ? '; the group cells for that day are loading' : '; the group cells for that day could not be loaded'}. {rp.wiresKept ? <>The dot counts the <Explain k="tripwire">tripwires</Explain> lit at that run.</> : <>Which <Explain k="tripwire">tripwires</Explain> were lit that day was not kept.</>} The 0 to 100 reading is not kept per day.</p>
        : <p className="mx-4 mb-[18px] mt-3 text-[11.5px] leading-normal text-fg3">Each row gives two answers: <Explain k="now">Now</Explain>, what is happening, set by hand, and <Explain k="buildup">build-up</Explain>, whether signals are building. The <Explain k="unusual">reading</Explain> runs from 0 to 100 and is not a chance of war.{line ? <> <Explain k="lines">Watch</Explain> begins at 50.</> : ''} The five bars are the signal <Explain k="group">groups</Explain> Logistics, Markets, People, News and Physical, from slow to fast. <button onClick={() => go({ v: 'glossary', term: 'read' })} className="lnk">How to read WarWatch</button></p>}
    </section>
  )
}

/* the group cells in words, for the row's name: only groups at 1 SD or more, as the cells colour them */
const groupWords = (g: Record<string, number | null>) => { const w = GROUPS.flatMap(k => { const z = g[k]; return z == null || z < 1 ? [] : [`${k} ${z >= 3 ? 'very strong' : z >= 2 ? 'strong' : 'unusual'}`] }); return w.length ? w.join(', ') : 'No signal group unusual' }

/* The board's columns: the theatre (name, then its build-up level and Now answer), the five group bars, the reading's bar and number,
   and its change over 7 days. The head (Board) and every row share them, so heads and values line up. */
export const BOARD_COLS = 'grid-cols-[minmax(0,1fr)_58px_44px_22px_30px] gap-x-2.5'
/* a group's bar: height and colour both carry the step (none, 1, 2, 3+ SD), so the bars read in greyscale and for colour-blind
   readers; a group with no reading is a dashed outline */
const STEP_H = ['h-[4px]', 'h-[8px]', 'h-[12px]', 'h-[16px]']
export function GroupBars({ g, className = '' }: { g: Partial<Record<string, number | null>> | null; className?: string }) {
  return (
    <span className={`grid h-4 grid-cols-5 items-end gap-[3px] ${className}`} aria-hidden title={g ? GROUPS.map(k => `${k} ${g[k] == null ? 'no data' : fmtZ(g[k]) + ' SD'}`).join(' · ') : 'Not kept for this day'}>
      {GROUPS.map(k => { const z = g?.[k]; const st = z == null ? -1 : z < 1 ? 0 : z < 2 ? 1 : z < 3 ? 2 : 3
        return <i key={k} className={`block rounded-[2px] ${st < 0 ? 'h-[4px] border border-dashed border-line2' : STEP_H[st]}`} style={st < 0 ? undefined : { background: groupTone(z) }} /> })}
    </span>
  )
}
const levelText = (l: string) => l === 'Critical' ? 'var(--crit)' : l === 'Elevated' ? 'var(--z3-text)' : l === 'Watch' ? 'var(--z2-text)' : 'var(--fg3)'

/* a row: the theatre (opens its dossier) and, beside it, its follow pin. Replaying (day), the level, bars and tripwire count are
   that day's, and the reading and its change are left empty because they are not kept per day. A reading that changes while the
   page is open (a new run) rolls to its new value and the row washes once in ivory. */
function BoardRow({ t, i, rise, on, line, go, day }: { t: BriefTheatre; i: number; rise: boolean; on: boolean; line: boolean; go: Go; day: DayTheatre | null }) {
  const { has, toggle } = useFollow()
  const lit = useHoveredTheatre() === t.id
  const { prefs } = usePrefs()
  const still = prefs.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches
  const pin = has(t.id)
  const score = day ? null : t.score == null ? null : Math.max(0, Math.min(100, t.score))
  const level = day ? day.level : t.level, groups = day ? day.groups : t.groups, wires = day ? day.wires?.length ?? 0 : t.tellsOn
  const ch = day ? null : t.change7 ?? null
  /* a new run that moved the whole number: wash the row once (1.8 s), never on first paint */
  const prev = useRef(score == null ? null : wholeScore(score)), [wash, setWash] = useState(0)
  useEffect(() => { const w = score == null ? null : wholeScore(score); if (prev.current !== w && prev.current != null && w != null) setWash(k => k + 1); prev.current = w }, [score])
  const lvSay = level ? levelWord(level).toLowerCase() : 'level not kept for this day'
  const say = `${t.name}. Now: ${t.now && !day ? NOW_WORD[t.now].toLowerCase() : 'nothing set'}. Build-up ${lvSay}. ${groups ? groupWords(groups) : 'Group readings not kept for this day'}.${day ? '' : ` Reading ${score == null ? 'not available' : `${wholeScore(score)} of 100`}${ch == null ? '' : `, ${Math.round(ch) === 0 ? 'unchanged' : `${Math.round(ch) > 0 ? 'up' : 'down'} ${Math.abs(Math.round(ch))}`} over 7 days`}.`}${day && !day.wires ? ' Tripwires not kept for this day.' : wires ? ` ${wires} ${wires === 1 ? 'tripwire' : 'tripwires'} ${day ? 'lit at that day\'s run' : 'fired this week'}.` : ''}`
  return (
    <motion.div layout={still ? false : 'position'} transition={{ layout: { duration: .28, ease: EASE } }}
      className={`group relative grid grid-cols-[minmax(0,1fr)_28px] items-center border-t border-line transition-colors duration-[120ms] ${on ? 'bg-s3' : lit ? 'bg-s2' : 'hover:bg-s2'} ${rise ? 'rise' : ''}`} style={{ ['--i' as string]: i }}
      onPointerEnter={e => { if (e.pointerType === 'mouse') hoverTheatre(t.id) }} onPointerLeave={() => hoverTheatre(null)}>
      {wash > 0 && !still && <i key={wash} aria-hidden className="ww-wash pointer-events-none absolute inset-0" />}
      <button onClick={() => go({ v: 'theatre', id: t.id })} aria-current={on ? 'true' : undefined} aria-label={say}
        className={`relative grid h-11 w-full ${BOARD_COLS} items-center pl-4 text-left`}>
        {on && <i className="absolute inset-y-0 left-0 w-[2px] bg-sel" aria-hidden />}
        <span className="flex min-w-0 flex-col justify-center gap-[3px]" aria-hidden>
          <span className="flex min-w-0 items-center gap-[7px] leading-none">
            <b className="min-w-0 truncate text-[13.5px] font-medium leading-[1.1]">{short(t.name)}</b>
            {wires > 0 && <span className="inline-flex shrink-0 items-center gap-[3px] font-mono text-[11px] font-medium leading-none text-z2t" title={`${wires} ${wires === 1 ? 'tripwire' : 'tripwires'} ${day ? 'lit at that day\'s run' : 'fired this week'}`}>
              <i className="h-1.5 w-1.5 rounded-full bg-z2 shadow-[0_0_6px_color-mix(in_srgb,var(--z2)_70%,transparent)]" />{wires}</span>}
          </span>
          <span className="flex min-w-0 items-center gap-1.5 text-[11px] leading-none">
            {level ? <span className="shrink-0 font-medium" style={{ color: levelText(level) }}>{levelWord(level)}</span> : <span className="shrink-0 text-fg2">not kept</span>}
            {!day && t.now && <><i className="h-2.5 w-px shrink-0 bg-line2" /><NowMark now={t.now} className="min-w-0 truncate" /></>}
          </span>
        </span>
        <GroupBars g={groups} />
        <span className="relative h-1.5 rounded-[3px] bg-z0" aria-hidden>
          <motion.i className="absolute inset-y-0 left-0 rounded-[3px] bg-fg2" initial={{ width: 0 }} animate={{ width: `${score ?? 0}%` }} transition={{ duration: .22, ease: EASE, delay: rise ? Math.min(i, 8) * .02 : 0 }} />
          {line && !day && <i className="absolute -inset-y-1 left-1/2 w-px bg-fg3" />}
        </span>
        <b className="num text-right text-[12.5px] font-medium leading-none text-fg2" aria-hidden>{score == null ? '–' : <NumberFlow value={wholeScore(score)} animated={!still} transformTiming={{ duration: 200, easing: 'ease-out' }} spinTiming={{ duration: 200, easing: 'ease-out' }} />}</b>
        <span className={`num text-right text-[12px] leading-none ${ch != null && Math.round(ch) !== 0 ? 'text-fg2' : 'text-fg3'}`} aria-hidden>{fmtChange(ch)}</span>
      </button>
      {/* on touch the pin's tap area reaches 44 px: 16 px to its left, over the row's gap, and the row's full height */}
      <button onClick={() => toggle(t.id)} data-follow={t.id} aria-pressed={pin} aria-label={pin ? `Following ${short(t.name)}, press to stop` : `Follow ${short(t.name)}`} title={pin ? `Following ${short(t.name)}. Press to stop.` : `Follow ${short(t.name)}: keep it at the top of the board`}
        className={`relative grid h-11 w-7 place-items-center transition-opacity duration-[120ms] pointer-coarse:after:absolute pointer-coarse:after:inset-y-0 pointer-coarse:after:-left-4 pointer-coarse:after:right-0 pointer-coarse:after:content-[''] ${pin ? 'text-fg' : 'text-fg3 opacity-0 hover:text-fg focus-visible:opacity-100 group-hover:opacity-100 max-[899px]:opacity-100 pointer-coarse:opacity-100'}`}>
        <Pin size={13} strokeWidth={pin ? 2.2 : 1.7} fill={pin ? 'currentColor' : 'none'} aria-hidden />
      </button>
    </motion.div>
  )
}

/* ---------------------------------------------------------------- what changed: one stream */
/* What changed, the bell and "since you last looked" are one stream with two tiers (contract.tier): Key (a tripwire or strike wave,
   a build-up level change, a base that differed on two radar passes, a government raising its advice) and All (the rest joins: heat,
   single passes, advice rewritten, ratings). What is new since the last visit carries a dot; one line above the list says how many
   and can show only those. A base seen differing on several passes is one row, with its other days named. */
export type Kind = 'key' | 'all'
const KIND_WORD: Record<FeedItem['kind'], string> = { tell: 'Tripwire', base: 'Base', fire: 'Heat', official: 'Official', level: 'Build-up' }
/* a small glyph per kind, the same marks the timeline and the map use */
const GLYPH: Record<FeedItem['kind'], ReactNode> = {
  tell: <i className="h-2 w-2 rounded-full bg-z2 shadow-[0_0_7px_color-mix(in_srgb,var(--z2)_60%,transparent)]" />,
  base: <i className="h-2 w-2 rotate-45 bg-z3" />,
  fire: <i className="h-[7px] w-[7px] rounded-full border-[1.5px] border-z3" />,
  official: <i className="h-[7px] w-[9px] rounded-[1px] border-[1.5px] border-fg2" />,
  level: <i className="h-[9px] w-[9px] rounded-[2px] border-[1.5px] border-z2" />,
}
const dayLabel = (d: string, today: string) => {
  const n = Math.round((Date.parse(today + 'T12:00Z') - Date.parse(d + 'T12:00Z')) / 864e5), x = new Date(d + 'T12:00Z')
  const dm = x.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  return `${n === 0 ? 'Today' : n === 1 ? 'Yesterday' : x.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })}, ${dm}`
}
/* a base that differed on several passes in the window: its newest row stays, the others fold into it as "also on" days */
type Row = { f: FeedItem; also: string[] }
export function foldRows(items: FeedItem[]): Row[] {
  const out: Row[] = [], at = new Map<string, Row>()
  for (const f of [...items].sort((a, b) => b.date.localeCompare(a.date))) {
    const k = f.kind === 'base' ? `${f.to?.id}|${f.title}` : ''
    const r = k ? at.get(k) : undefined
    if (r) { r.also.push(f.date.slice(0, 10)); continue }
    const row = { f, also: [] }; out.push(row); if (k) at.set(k, row)
  }
  return out
}

/* newOnly: show only what arrived since the last visit (the line above the list sets it); block: draw that line here
   (on phones it sits under the dispatch instead) */
export function Feed({ brief, day, setDay, kind, setKind, go, since, dismiss, newOnly = false, setNewOnly, block = true }: { brief: Brief; day: string | null; setDay: (d: string | null) => void; kind: Kind; setKind: (k: Kind) => void; go: Go
  since?: Since | null; dismiss?: () => void; newOnly?: boolean; setNewOnly?: (b: boolean) => void; block?: boolean }) {
  const today = utcDay(parseGen(brief.generated))
  const only = newOnly && !!since
  const rp = useReplay(), noHeat = !!day && !!rp?.heatFrom && day < rp.heatFrom
  const scope = useMemo(() => brief.feed.filter(f => (!day || f.date.slice(0, 10) === day) && (!only || since!.fresh.has(feedKey(f)))), [brief.feed, day, only, since])
  const nKey = useMemo(() => scope.filter(isKey).length, [scope])
  const days = useMemo(() => {
    const m = new Map<string, Row[]>()
    for (const r of foldRows(scope.filter(f => kind === 'all' || isKey(f)))) { const d = r.f.date.slice(0, 10); m.set(d, [...(m.get(d) || []), r]) }
    return [...m]
  }, [scope, kind])
  const name = (id: string) => { const t = brief.theatres.find(x => x.id === id); return t ? short(t.name) : '' }
  const seg = (k: Kind, label: string, n: number) => (
    <button key={k} aria-pressed={kind === k} onClick={() => setKind(k)} aria-label={`${label}, ${n} ${day ? `on ${shortDate(day)}` : 'in the last 30 days'}`}
      className={`tap inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[12px] leading-none transition-colors duration-[120ms] ${kind === k ? 'bg-sel font-medium text-selink' : 'text-fg2 hover:text-fg'}`}>
      {label}<span className={`num text-[11px] ${kind === k ? 'text-selink/75' : 'text-fg3'}`}>{n}</span></button>)
  return (
    <section aria-label="What changed" id="feed" className="scroll-mt-2">
      <div className="flex items-center justify-between gap-2.5 px-4 pb-2 pt-4">
        <h2 className="text-[13px] font-semibold leading-6 tracking-[-0.005em]">What changed</h2>
        <span className="inline-flex items-center gap-0.5 rounded-full border border-line p-0.5" role="group" aria-label="Show">{seg('key', 'Key', nKey)}{seg('all', 'All', scope.length)}</span>
      </div>
      <p className="-mt-1 px-4 pb-2 text-[11.5px] leading-[1.4] text-fg3">{day ? <><span className="text-fg2">{shortDate(day)} only</span> · <button onClick={() => setDay(null)} className="lnk">Back to now</button></> : kind === 'key' ? 'Tripwires, build-up changes, bases changed on two passes and raised advice, last 30 days' : 'Everything in the last 30 days, heat and single passes included'}</p>
      {block && since && dismiss && setNewOnly && <SinceBlock since={since} dismiss={dismiss} newOnly={only} setNewOnly={v => { setDay(null); setNewOnly(v) }} />}
      {noHeat && kind === 'all' && <p className="mx-4 mb-2 text-[11.5px] leading-[1.4] text-fg2">Heat is kept from {shortDate(rp!.heatFrom!)} only, so this day shows no heat reports whether or not there were any.</p>}
      {days.length === 0 && <p className="mx-4 mb-5 mt-3 text-[12.5px] text-fg3">{only ? `Nothing ${kind === 'key' ? 'key ' : ''}new since your last visit.` : day ? `Nothing ${kind === 'key' ? 'key ' : ''}on that day.` : `Nothing ${kind === 'key' ? 'key ' : ''}in the last 30 days.`}{kind === 'key' && scope.length > 0 && <> <button onClick={() => setKind('all')} className="lnk">Show all {scope.length}</button></>}</p>}
      {days.map(([d, rows]) => (
        <div key={d} role="group" aria-label={dayLabel(d, today)}>
          <div className="sticky top-[var(--stick,0px)] z-[1] bg-s1 px-4 pb-1 pt-2.5 text-[11px] font-medium text-fg3">{dayLabel(d, today)}</div>
          <ul>{rows.map(({ f, also }, i) => { const isNew = !!since?.fresh.has(feedKey(f)); return (
            <li key={i}>
              {/* a focused item draws over the sticky day header, its ring inside, and focus scrolls clear of the header */}
              <button onClick={() => go(toRoute(f.to))} className="group grid w-full scroll-mt-9 grid-cols-[16px_minmax(0,1fr)] gap-x-2.5 px-4 py-[7px] text-left transition-colors duration-[120ms] hover:bg-s2 focus-visible:relative focus-visible:z-[2] focus-visible:outline-offset-[-2px]">
                <span className="grid h-[18px] w-4 place-items-center" aria-hidden>{GLYPH[f.kind] ?? GLYPH.official}</span>
                <span className="min-w-0">
                  <span className="block text-[13px] leading-[18px]">{isNew && <i className="mr-1.5 inline-block h-1.5 w-1.5 -translate-y-px rounded-full bg-sel align-middle" />}<span className="sr-only">{isNew ? 'New. ' : ''}{isWave(f) ? 'Strike wave' : KIND_WORD[f.kind] ?? 'Change'}: </span>{name(f.theatre) && <><b className="font-medium">{name(f.theatre)}</b> · </>}{f.title}</span>
                  <span className="mt-px block text-[11.5px] leading-[1.4] text-fg3 group-hover:text-fg2">{feedDetail(f.detail).replace(/\.$/, '')}{also.length > 0 && ` · also ${also.map(x => shortDate(x)).join(', ')}`}</span>
                </span>
              </button>
            </li>) })}
          </ul>
        </div>))}
    </section>
  )
}

/* ---------------------------------------------------------------- since you last looked (since.ts keeps the snapshot) */
/* One line: how many key and other items are new since the last visit, a switch to show only those, and a dismiss. The board's
   7-day change and the stream's build-up rows say what moved, so the block no longer lists theatres. */
export function SinceBlock({ since, dismiss, newOnly, setNewOnly, className = 'mx-4 mb-2.5' }: { since: Since; dismiss: () => void; newOnly: boolean; setNewOnly: (b: boolean) => void; className?: string }) {
  const { prefs } = usePrefs()
  const when = `${since.at.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: prefs.tz === 'utc' ? 'UTC' : undefined })}, ${fmtTime(since.at, prefs.tz)}`
  const n = since.fresh.size, k = since.key
  return (
    <section aria-label="Since you last looked" className={`${className} flex items-center gap-2 rounded-r2 border border-line bg-s2 py-1.5 pl-3 pr-1.5`}>
      <i className="h-1.5 w-1.5 shrink-0 rounded-full bg-sel" aria-hidden />
      <p className="min-w-0 flex-1 text-[12px] leading-[1.35] text-fg2"><span className="text-fg">{n ? `${n} new` : 'Nothing new'}</span>{n ? `, ${k} key,` : ''} since {when}</p>
      {n > 0 && <button onClick={() => setNewOnly(!newOnly)} aria-pressed={newOnly} className={`tap h-7 shrink-0 rounded-r1 px-2 text-[12px] transition-colors duration-[120ms] ${newOnly ? 'bg-sel font-medium text-selink' : 'text-fg2 hover:bg-s3 hover:text-fg'}`}>{newOnly ? 'Showing new' : 'Show new'}</button>}
      <button onClick={dismiss} aria-label="Dismiss since you last looked" className="tap grid h-7 w-7 shrink-0 place-items-center rounded-r1 text-fg3 hover:bg-s3 hover:text-fg"><X size={14} /></button>
    </section>
  )
}

/* ---------------------------------------------------------------- the 30-day timeline */
const LANES: [Exclude<FeedItem['kind'], 'level'>, string, string][] = [['tell', 'Tripwires', 'var(--z2)'], ['base', 'Bases', 'var(--z3)'], ['fire', 'Heat', 'color-mix(in srgb, var(--z3) 55%, var(--z0))'], ['official', 'Official', 'var(--fg2)']]
const WORD_OF: Record<string, [string, string]> = { tell: ['tripwire', 'tripwires'], base: ['base change', 'base changes'], fire: ['heat report', 'heat reports'], official: ['official step', 'official steps'] }
export const TIME_H = 146   // px the timeline takes at the foot of the map, with its margin

/* The timeline is also the replay: picking a day (a click or tap, a drag across the days, or the arrow keys) shows that day on the
   board, the dispatch, the tripwires and the feed (replay.tsx). Today is live. "Back to now" or Escape returns to it.
   inline: drawn in the flow of a column (the phone's sheet) instead of over the foot of the map. */
export function Timeline({ brief, day, setDay, inline = false }: { brief: Brief; day: string | null; setDay: (d: string | null) => void; inline?: boolean }) {
  const end = parseGen(brief.generated).getTime()
  const days = useMemo(() => Array.from({ length: 30 }, (_, i) => utcDay(new Date(end - (29 - i) * 864e5))), [end])
  const { counts, waves } = useMemo(() => {
    const c = Object.fromEntries(LANES.map(([k]) => [k, days.map(() => 0)])) as Record<FeedItem['kind'], number[]>, w = days.map(() => 0)
    for (const f of brief.feed) { const i = days.indexOf(f.date.slice(0, 10)); if (i >= 0 && c[f.kind]) { c[f.kind][i] += 1; if (isWave(f)) w[i] += 1 } }
    return { counts: c, waves: w }
  }, [brief.feed, days])
  /* heat before heatFrom and tripwire days the record did not keep are not zeros: their cells are left open and say so */
  const heatFrom = brief.replay?.heatFrom ?? null
  const litKept = useMemo(() => new Set(brief.theatres.flatMap(t => (t.wires || []).map(x => x[0]))), [brief.theatres])
  const noHeat = (i: number) => !!heatFrom && days[i] < heatFrom
  const at = day ? days.indexOf(day) : 29
  const btns = useRef<(HTMLButtonElement | null)[]>([]), strip = useRef<HTMLDivElement>(null), drag = useRef<{ x: number; y: number; on: boolean } | null>(null)
  /* index 29 is today: live, so it clears the replay */
  const pick = (k: number, focus = false) => { const i = Math.max(0, Math.min(29, k)); setDay(i === 29 ? null : days[i]); if (focus) btns.current[i]?.focus() }
  const key = (e: KeyboardEvent) => {
    const to = e.key === 'ArrowLeft' ? at - 1 : e.key === 'ArrowRight' ? at + 1 : e.key === 'Home' ? 0 : e.key === 'End' ? 29 : null
    if (to == null) return
    e.preventDefault(); pick(to, true)
  }
  const fromX = (x: number) => { const r = strip.current!.getBoundingClientRect(); return Math.floor((x - r.left) / r.width * 30) }
  const say = (i: number) => {
    const n = (k: FeedItem['kind']) => k === 'tell' ? counts.tell[i] - waves[i] : counts[k][i]
    const parts = LANES.map(([k]) => n(k) ? `${n(k)} ${WORD_OF[k][n(k) === 1 ? 0 : 1]} ${k === 'tell' ? 'fired' : ''}`.trim() : '').filter(Boolean)
    if (waves[i]) parts.splice(1, 0, `${waves[i]} ${waves[i] === 1 ? 'strike wave began' : 'strike waves began'}`)
    const gaps = [noHeat(i) ? 'heat not kept that far back' : '', i < 29 && litKept.size && !litKept.has(days[i]) ? 'lit tripwires not kept' : ''].filter(Boolean)
    return `${i === 29 ? 'Today, live, ' : ''}${shortDate(days[i])}: ${parts.length ? parts.join(', ') : 'nothing logged'}${gaps.length ? `; ${gaps.join(', ')}` : ''}`
  }
  const step = 'tap grid h-7 min-w-7 place-items-center rounded-r1 border border-line text-fg2 hover:border-line2 hover:text-fg disabled:opacity-40 disabled:hover:border-line'
  return (
    <div className={inline ? 'mx-3.5 mb-1 mt-2 rounded-r3 border border-line bg-s2 px-3 pb-2 pt-2.5' : 'absolute inset-x-3.5 bottom-3.5 z-10 rounded-r3 border border-line bg-[color-mix(in_oklab,var(--bg)_88%,transparent)] px-3.5 pb-2 pt-2.5 backdrop-blur-[12px]'}>
      <div className="mb-[7px] flex items-center justify-between gap-2">
        <span className="eyebrow min-w-0 truncate">{day ? `Replaying ${shortDate(day)}` : 'Last 30 days, all theatres'}</span>
        <span className="flex shrink-0 items-center gap-1.5 text-[11px] text-fg3">
          {!day && <span className="max-[459px]:hidden">Pick or drag to replay a day</span>}
          <button onClick={() => pick(at - 1, false)} disabled={at === 0} aria-label="One day earlier" className={step}><ChevronLeft size={13} aria-hidden /></button>
          <button onClick={() => pick(at + 1, false)} disabled={at === 29} aria-label="One day later" className={step}><ChevronRight size={13} aria-hidden /></button>
          {day && <button onClick={() => setDay(null)} className="tap min-h-7 rounded-r1 border border-sel bg-sel px-2 font-medium text-selink">Back to now</button>}
        </span>
      </div>
      <div className="flex gap-0">
        <div className="flex w-[62px] shrink-0 flex-col gap-[3px] text-[10.5px] leading-[11px] text-fg3" aria-hidden>{LANES.map(([k, label]) => <span key={k} className="h-[11px]">{label}</span>)}</div>
        <div ref={strip} role="listbox" aria-label="Last 30 days. Arrow keys replay a day; the last day is today, live." onKeyDown={key}
          /* a day is picked on a tap (lifted within 8 px of where it went down) or once a drag is clearly sideways; a swipe that
             starts here going up or down scrolls and picks nothing */
          onPointerDown={e => { if (e.button) return; drag.current = { x: e.clientX, y: e.clientY, on: false } }}
          onPointerMove={e => {
            const g = drag.current; if (!g) return
            const dx = Math.abs(e.clientX - g.x), dy = Math.abs(e.clientY - g.y)
            if (!g.on) { if (dy > 8 && dy >= dx) { drag.current = null; return } if (dx > 8 && dx > dy * 1.5) { g.on = true; (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId) } else return }
            const k = fromX(e.clientX); if (k >= 0 && k < 30 && k !== at) pick(k)
          }}
          onPointerUp={e => { const g = drag.current; drag.current = null; if (!g || g.on || Math.hypot(e.clientX - g.x, e.clientY - g.y) > 8) return; const k = fromX(e.clientX); if (k >= 0 && k < 30) pick(k, true) }}
          onPointerCancel={() => { drag.current = null }}
          className="grid min-w-0 flex-1 touch-pan-y gap-0.5 py-1" style={{ gridTemplateColumns: 'repeat(30, minmax(0, 1fr))' }}>
          {/* a hovered day gets a hairline outline; its cells keep their size, so nothing in the strip moves under the pointer */}
          {days.map((d, i) => { const on = i === at && !!day, today = i === 29; return (
            <button key={d} ref={el => { btns.current[i] = el }} role="option" aria-selected={day ? on : today} aria-label={say(i)} title={say(i)} tabIndex={i === at ? 0 : -1}
              onClick={e => { if (e.detail === 0) pick(i, true) }}
              className={`group flex flex-col gap-[3px] rounded-[3px] outline-offset-1 ${on ? 'outline outline-1 outline-sel' : 'hover:outline hover:outline-1 hover:outline-fg3'} ${day && i > at ? 'opacity-40' : ''}`}>
              {LANES.map(([k, , tone]) => { const n = counts[k][i], mx = Math.max(1, ...counts[k]), open = k === 'fire' && noHeat(i); return (
                <i key={k} className={`h-[11px] w-full rounded-[2px] ${open ? 'border border-dashed border-line2' : ''}`} style={{ background: open ? 'transparent' : n ? tone : 'var(--z0)', opacity: !n ? 1 : n / mx > .6 ? 1 : n / mx > .25 ? .7 : .45 }} />) })}
            </button>) })}
        </div>
      </div>
      <div className="ml-[62px] mt-[3px] grid gap-0.5 font-mono text-[9.5px] leading-[10px] text-fg3" style={{ gridTemplateColumns: 'repeat(30, minmax(0, 1fr))' }} aria-hidden>
        {days.map((d, i) => <span key={d} className={`whitespace-nowrap ${i === 29 ? 'text-right font-medium text-fg2' : ''}`} style={i === 29 ? { direction: 'rtl' } : undefined}>{i === 29 ? 'today' : i % (inline ? 10 : 5) === 0 && i < 25 ? shortDate(d) : ''}</span>)}
      </div>
    </div>
  )
}
