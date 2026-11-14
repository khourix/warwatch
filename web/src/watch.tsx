import { useEffect, useMemo, useRef, useState, type ReactNode, type KeyboardEvent } from 'react'
import { motion } from 'motion/react'
import NumberFlow from '@number-flow/react'
import { GROUPS, short, levelWord, groupTone, feedDetail, fmtZ, shortDate, parseGen, type Brief, type BriefTheatre, type FeedItem, type Route, wholeScore } from './data'
import { usePrefs, fmtTime } from './settings'
import { toRoute } from './views'
import { feedKey, type Since } from './since'
import { Lnk } from './ui'
import { X } from 'lucide-react'

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
const underLine = (b: Brief, t?: BriefTheatre) => !b.model.active && !!t && t.score! < 50
const utcDay = (d: Date) => d.toISOString().slice(0, 10)

/* ---------------------------------------------------------------- the top bar's status sentence */
export function Status({ brief }: { brief: Brief }) {
  const up = above(brief), near = closest(brief), n = brief.theatres.length
  const sep = <i className="mx-2 inline-block h-3.5 w-px translate-y-[2px] bg-line2" aria-hidden />
  if (up.length) return <><b className="font-medium text-fg">{up.length} of {n} theatres at Watch or above</b>{sep}<span>{up.slice(0, 3).map(t => `${short(t.name)}, ${t.level}`).join(' · ')}{up.length > 3 ? ' …' : ''}</span></>
  return <><b className="font-medium text-fg">{n} of {n} theatres quiet</b>{near && <>{sep}<span>{underLine(brief, near) ? `Closest to Watch: ${short(near.name)}, ${wholeScore(near.score!)} against 50` : `Highest reading: ${short(near.name)}, ${wholeScore(near.score!)}`}</span></>}</>
}

/* ---------------------------------------------------------------- the dispatch card */
function sentence(brief: Brief): ReactNode {
  const up = above(brief), near = closest(brief)
  const most = [...brief.theatres].sort((a, b) => b.tellsOn - a.tellsOn)[0], n = brief.counts.tells
  const lead = !up.length ? <>Every theatre reads quiet. </>
    : up.length === 1 ? <><em>{short(up[0].name)}</em> is at {up[0].level}; every other theatre reads quiet. </>
    : <>{word(up.length, true)} theatres are at Watch or above, led by <em>{short(up[0].name)}</em> at {up[0].level}. </>
  const gap = !near ? null : underLine(brief, near) ? <>{up.length ? 'Of the rest, ' : ''}<em>{short(near.name)}</em> comes closest to Watch, at {wholeScore(near.score!)} against a line of 50. </>
    : <>{up.length ? 'Of the rest, ' : ''}<em>{short(near.name)}</em> has the most unusual readings, at {wholeScore(near.score!)} of 100. </>
  const wires = !n ? 'No tripwire fired this week.'
    : n === 1 ? `One tripwire fired this week, on ${short(most.name)}.`
    : `${word(n, true)} tripwires fired this week, ${most.tellsOn === n ? (n === 2 ? 'both' : 'all of them') : `${word(most.tellsOn)} of them`} on ${short(most.name)}.`
  return <>{lead}{gap}{wires}</>
}

/* the sentence is the page's heading on Watch; with a theatre or base open, that dossier's name is */
export function Dispatch({ brief, heading }: { brief: Brief; heading: boolean }) {
  const H = heading ? 'h1' : 'p'
  const { prefs } = usePrefs()
  const at = parseGen(brief.generated)
  const date = at.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: prefs.tz === 'utc' ? 'UTC' : undefined })
  const c = brief.counts
  return (
    <section aria-label="Dispatch" className="m-3.5 mb-1.5 rounded-r3 border border-inkline bg-paper px-[18px] pb-3.5 pt-4 text-ink">
      <div className="eyebrow flex flex-wrap items-center gap-x-2 !text-ink2"><span>Dispatch</span><span>{date}</span><span>{fmtTime(at, prefs.tz)}</span>{brief.demo && <span className="text-crit">demo data</span>}</div>
      <H className="mb-3.5 mt-[11px] font-serif text-[21.5px] font-normal leading-[1.27] tracking-[-0.012em] [text-wrap:pretty]">{sentence(brief)}</H>
      <dl className="grid grid-cols-3 border-t border-inkline pt-[11px]">
        {([[c.tells, c.tells === 1 ? 'tripwire fired this week' : 'tripwires fired this week'], [c.bases, c.bases === 1 ? 'base changed on radar' : 'bases changed on radar'], [c.strong, c.strong === 1 ? 'signal reading strong' : 'signals reading strong']] as const).map(([v, label], i) => (
          <div key={i} className={`flex flex-col-reverse ${i ? 'border-l border-inkline pl-3' : ''}`}>
            <dt className="mt-[5px] text-[11.5px] leading-[1.25] text-ink2">{label}</dt>
            <dd className="num text-[25px] font-medium leading-none tracking-[-0.03em]"><NumberFlow value={v} /></dd>
          </div>))}
      </dl>
    </section>
  )
}

/* ---------------------------------------------------------------- the theatre board */
export type Order = 'closest' | 'region'
export function Board({ brief, sel, go, order, setOrder }: { brief: Brief; sel: string | null; go: Go; order: Order; setOrder: (o: Order) => void }) {
  const first = useRef(true)
  useEffect(() => { first.current = false }, [])
  const byId = useMemo(() => Object.fromEntries(brief.theatres.map(t => [t.id, t])), [brief])
  const sorted = useMemo(() => [...brief.theatres].sort(byScore), [brief])
  const line = !brief.model.active
  const row = (t: BriefTheatre, i: number) => <BoardRow key={t.id} t={t} i={i} rise={first.current} on={sel === t.id} line={line} go={go} />
  return (
    <section aria-label="Theatres">
      <div className="flex items-center justify-between gap-2.5 px-4 pb-2 pt-4">
        <h2 className="text-[13px] font-semibold tracking-[-0.005em]">Theatres</h2>
        <span className="inline-flex rounded-r2 border border-line p-0.5 text-[11.5px]" role="group" aria-label="Order of the board">
          {([['closest', 'Closest to Watch'], ['region', 'By region']] as const).map(([k, label]) => (
            <button key={k} aria-pressed={order === k} onClick={() => setOrder(k)} className={`rounded-[6px] px-2 py-0.5 transition-colors duration-[120ms] ${order === k ? 'bg-s3 text-fg' : 'text-fg3 hover:text-fg2'}`}>{label}</button>))}
        </span>
      </div>
      <div className="grid h-[22px] grid-cols-[minmax(0,1fr)_66px_112px] items-center gap-3 px-4 text-[10.5px] text-fg3" aria-hidden>
        <span />
        <span className="flex justify-between" title="The five signal groups, from the slowest to move to the fastest: Logistics, Markets, People, News, Physical"><span>slow</span><span>fast</span></span>
        <span title={`How unusual today's signals are, 0 to 100.${line ? ' The tick is the Watch line at 50.' : ''}`}>Unusual readings</span>
      </div>
      {order === 'closest' ? <div>{sorted.map(row)}</div>
        : brief.regions.map(r => <div key={r.id} role="group" aria-label={r.name}><div className="px-4 pb-[5px] pt-3 text-[11px] font-medium text-fg3">{r.name}</div>{r.theatres.map(id => byId[id]).filter(Boolean).map(row)}</div>)}
      <p className="mx-4 mb-[18px] mt-3 text-[11.5px] leading-normal text-fg3">Unusual readings run from 0 to 100. They are not a chance of war.{line ? ' Watch begins at 50.' : ''} The five cells are Logistics, Markets, People, News and Physical, from slow to fast. <button onClick={() => go({ v: 'record' })} className="lnk">How the number works</button></p>
    </section>
  )
}

/* the group cells in words, for the row's name: only groups at 1 SD or more, as the cells colour them */
const groupWords = (t: BriefTheatre) => { const w = GROUPS.flatMap(g => { const z = t.groups[g]; return z == null || z < 1 ? [] : [`${g} ${z >= 3 ? 'very strong' : z >= 2 ? 'strong' : 'unusual'}`] }); return w.length ? w.join(', ') : 'No signal group unusual' }

function BoardRow({ t, i, rise, on, line, go }: { t: BriefTheatre; i: number; rise: boolean; on: boolean; line: boolean; go: Go }) {
  const score = t.score == null ? null : Math.max(0, Math.min(100, t.score))
  const label = `${t.name}, ${levelWord(t.level).toLowerCase()}${t.context ? `, ${t.context.toLowerCase()}` : ''}. ${groupWords(t)}. Unusual readings ${score == null ? 'not available' : `${wholeScore(score)} of 100`}.${t.tellsOn ? ` ${t.tellsOn} ${t.tellsOn === 1 ? 'tripwire' : 'tripwires'} fired this week.` : ''}`
  return (
    <button onClick={() => go({ v: 'theatre', id: t.id })} aria-current={on ? 'true' : undefined} aria-label={label} style={{ ['--i' as string]: i }}
      className={`group relative grid h-[38px] w-full grid-cols-[minmax(0,1fr)_66px_112px] items-center gap-3 border-t border-line px-4 text-left transition-colors duration-[120ms] ${on ? 'bg-s3' : 'hover:bg-s2'} ${rise ? 'rise' : ''}`}>
      {on && <i className="absolute inset-y-0 left-0 w-[2px] bg-sel" aria-hidden />}
      <span className="flex min-w-0 items-baseline gap-[7px]" aria-hidden>
        <b className="min-w-0 shrink truncate text-[13.5px] font-medium">{short(t.name)}</b>
        <small className={`min-w-0 flex-1 truncate text-[11px] ${on ? 'text-fg2' : 'text-fg3 group-hover:text-fg2'}`}>{t.context || ''}</small>
        {t.level !== 'Normal' && <span className="shrink-0 text-[11px] font-medium" style={{ color: t.level === 'Critical' ? 'var(--crit)' : t.level === 'Elevated' ? 'var(--z3-text)' : 'var(--z2-text)' }}>{t.level}</span>}
        {t.tellsOn > 0 && <span className="inline-flex shrink-0 items-center gap-[3px] font-mono text-[10.5px] font-medium text-z2t" title={`${t.tellsOn} ${t.tellsOn === 1 ? 'tripwire' : 'tripwires'} fired this week`}>
          <i className="h-1.5 w-1.5 rounded-full bg-z2 shadow-[0_0_6px_color-mix(in_srgb,var(--z2)_70%,transparent)]" />{t.tellsOn}</span>}
      </span>
      <span className="grid grid-cols-5 gap-0.5" aria-hidden title={GROUPS.map(g => `${g} ${t.groups[g] == null ? 'no data' : fmtZ(t.groups[g]) + ' SD'}`).join(' · ')}>
        {GROUPS.map(g => <i key={g} className="h-3.5 rounded-[2px]" style={{ background: groupTone(t.groups[g]) }} />)}
      </span>
      <span className="grid grid-cols-[84px_22px] items-center gap-1.5" aria-hidden>
        <span className="relative h-1.5 rounded-[3px] bg-z0">
          <motion.i className="absolute inset-y-0 left-0 rounded-[3px] bg-fg2" initial={{ width: 0 }} animate={{ width: `${score ?? 0}%` }} transition={{ duration: .8, ease: EASE, delay: rise ? i * .022 : 0 }} />
          {line && <i className="absolute -inset-y-1 left-1/2 w-px bg-fg3" />}
        </span>
        <b className="num text-right text-[12px] font-medium text-fg2">{score == null ? '–' : wholeScore(score)}</b>
      </span>
    </button>
  )
}

/* ---------------------------------------------------------------- what changed */
export type Kind = FeedItem['kind'] | 'all'
const KINDS: [Kind, string][] = [['all', 'All'], ['tell', 'Tripwires'], ['base', 'Bases'], ['fire', 'Heat'], ['official', 'Official']]
const KIND_WORD: Record<FeedItem['kind'], string> = { tell: 'Tripwire', base: 'Base', fire: 'Heat', official: 'Official' }
/* a small glyph per kind, the same marks the timeline and the map use */
const GLYPH: Record<FeedItem['kind'], ReactNode> = {
  tell: <i className="h-2 w-2 rounded-full bg-z2 shadow-[0_0_7px_color-mix(in_srgb,var(--z2)_60%,transparent)]" />,
  base: <i className="h-2 w-2 rotate-45 bg-z3" />,
  fire: <i className="h-[7px] w-[7px] rounded-full border-[1.5px] border-z3" />,
  official: <i className="h-[7px] w-[9px] rounded-[1px] border-[1.5px] border-fg2" />,
}
const dayLabel = (d: string, today: string) => {
  const n = Math.round((Date.parse(today + 'T12:00Z') - Date.parse(d + 'T12:00Z')) / 864e5), x = new Date(d + 'T12:00Z')
  const dm = x.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  return `${n === 0 ? 'Today' : n === 1 ? 'Yesterday' : x.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })}, ${dm}`
}

export function Feed({ brief, day, setDay, kind, setKind, go, since, dismiss }: { brief: Brief; day: string | null; setDay: (d: string | null) => void; kind: Kind; setKind: (k: Kind) => void; go: Go; since?: Since | null; dismiss?: () => void }) {
  const today = utcDay(parseGen(brief.generated))
  const scope = useMemo(() => brief.feed.filter(f => !day || f.date.slice(0, 10) === day), [brief.feed, day])
  const days = useMemo(() => {
    const m = new Map<string, FeedItem[]>()
    for (const f of [...scope].sort((a, b) => b.date.localeCompare(a.date))) if (kind === 'all' || f.kind === kind) { const d = f.date.slice(0, 10); m.set(d, [...(m.get(d) || []), f]) }
    return [...m]
  }, [scope, kind])
  const name = (id: string) => { const t = brief.theatres.find(x => x.id === id); return t ? short(t.name) : '' }
  return (
    <section aria-label="What changed">
      <div className="flex items-baseline justify-between gap-2.5 px-4 pb-2 pt-4">
        <h2 className="text-[13px] font-semibold tracking-[-0.005em]">What changed</h2>
        {day ? <span className="text-[11.5px] text-fg3"><span className="text-fg2">{shortDate(day)} only</span> · <button onClick={() => setDay(null)} className="lnk">Show all days</button></span>
          : <span className="text-[11.5px] text-fg3">last 30 days</span>}
      </div>
      {since && dismiss && <SinceBlock since={since} dismiss={dismiss} kind={kind} setKind={k => { setDay(null); setKind(k) }} go={go} />}
      {/* counts sit in the name and tip only, so the five chips keep to one row */}
      <div className="flex flex-wrap gap-1 px-4 pb-2" role="group" aria-label="Kind of change">
        {KINDS.map(([k, label]) => { const n = k === 'all' ? scope.length : scope.filter(f => f.kind === k).length, say = `${label}, ${n} ${day ? `on ${shortDate(day)}` : 'in the last 30 days'}`; return (
          <button key={k} aria-pressed={kind === k} onClick={() => setKind(k)} aria-label={say} title={say}
            className={`rounded-full border px-2 py-[3px] text-[11.5px] transition-colors duration-[120ms] ${kind === k ? 'border-sel bg-sel font-medium text-selink' : 'border-line text-fg2 hover:border-line2'}`}>{label}</button>) })}
      </div>
      {days.length === 0 && <p className="mx-4 mb-5 mt-3 text-[12.5px] text-fg3">{day ? 'Nothing of this kind on that day.' : 'Nothing of this kind in the last 30 days.'}</p>}
      {days.map(([d, fs]) => (
        <div key={d} role="group" aria-label={dayLabel(d, today)}>
          <div className="sticky top-0 z-[1] bg-s1 px-4 pb-1 pt-2.5 text-[11px] font-medium text-fg3">{dayLabel(d, today)}</div>
          <ul>{fs.map((f, i) => (
            <li key={i}>
              {/* a focused item draws over the sticky day header, its ring inside, and focus scrolls clear of the header */}
              <button onClick={() => go(toRoute(f.to))} className="group grid w-full scroll-mt-9 grid-cols-[18px_minmax(0,1fr)] gap-[9px] px-4 py-[7px] text-left transition-colors duration-[120ms] hover:bg-s2 focus-visible:relative focus-visible:z-[2] focus-visible:outline-offset-[-2px]">
                <span className="mt-[3px] grid h-4 w-4 place-items-center" aria-hidden>{GLYPH[f.kind]}</span>
                <span className="min-w-0">
                  <span className="block text-[13px] leading-[1.35]"><span className="sr-only">{KIND_WORD[f.kind]}: </span>{name(f.theatre) && <><b className="font-medium">{name(f.theatre)}</b> · </>}{f.title}{since?.fresh.has(feedKey(f)) && <span className="ml-1.5 whitespace-nowrap rounded-[3px] border border-line2 px-1 py-px align-[1px] font-mono text-[9.5px] uppercase tracking-[.06em] text-fg2">new<span className="sr-only"> since your last visit</span></span>}</span>
                  <span className="mt-px block text-[11.5px] text-fg3 group-hover:text-fg2">{feedDetail(f.detail).replace(/\.$/, '')}</span>
                </span>
              </button>
            </li>))}
          </ul>
        </div>))}
    </section>
  )
}

/* ---------------------------------------------------------------- since you last looked (since.ts keeps the snapshot) */
const SINCE_WORD: Record<FeedItem['kind'], [string, string]> = { tell: ['tripwire', 'tripwires'], base: ['base change', 'base changes'], fire: ['heat report', 'heat reports'], official: ['official step', 'official steps'] }
function SinceBlock({ since, dismiss, kind, setKind, go }: { since: Since; dismiss: () => void; kind: Kind; setKind: (k: Kind) => void; go: Go }) {
  const { prefs } = usePrefs()
  const when = `${since.at.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: prefs.tz === 'utc' ? 'UTC' : undefined })}, ${fmtTime(since.at, prefs.tz)}`
  const kinds = (Object.keys(since.counts) as FeedItem['kind'][]).filter(k => since.counts[k] > 0)
  const shown = since.moved.slice(0, 5)
  const r = (v: number | null) => v == null ? '–' : v
  const nothing = !since.moved.length && !kinds.length
  return (
    <section aria-labelledby="since-h" className="mx-4 mb-2.5 rounded-r2 border border-line bg-s2 px-3 pb-2.5 pt-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0"><h3 id="since-h" className="text-[12px] font-semibold text-fg">Since you last looked</h3><p className="num text-[11.5px] text-fg3">Your last visit: {when}</p></div>
        <button onClick={dismiss} aria-label="Dismiss since you last looked" className="-mr-1.5 -mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-r1 text-fg3 hover:bg-s3 hover:text-fg"><X size={14} /></button>
      </div>
      {nothing && <p className="mt-1 text-[12px] text-fg2">Nothing has changed on the board or in the feed.</p>}
      {shown.length > 0 && <ul className="mt-1.5">{shown.map(m => { const lv = m.from[0] !== m.to[0], rd = m.from[1] !== m.to[1]; return (
        <li key={m.id} className="flex items-baseline justify-between gap-3 py-[2px] text-[12px]">
          <Lnk to={{ v: 'theatre', id: m.id }} go={go} className="min-w-0 truncate font-medium text-fg hover:underline hover:decoration-line2 hover:underline-offset-[3px]">{short(m.name)}</Lnk>
          <span className="num shrink-0 text-right text-fg2">{rd && <>{r(m.from[1])} to {r(m.to[1])}</>}{rd && lv && <span className="text-fg3"> · </span>}{lv && <>{levelWord(m.from[0])} to {levelWord(m.to[0])}</>}</span>
        </li>) })}
        {since.moved.length > shown.length && <li className="text-[11.5px] text-fg3">and {since.moved.length - shown.length} more {since.moved.length - shown.length === 1 ? 'theatre' : 'theatres'} moved</li>}
      </ul>}
      {kinds.length > 0 && <div className="mt-2 flex flex-wrap gap-1" role="group" aria-label="New in the feed since your last visit; pick one to show that kind">
        {kinds.map(k => { const n = since.counts[k], on = kind === k; return (
          <button key={k} aria-pressed={on} onClick={() => setKind(on ? 'all' : k)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-[2px] text-[11.5px] transition-colors duration-[120ms] ${on ? 'border-sel bg-sel font-medium text-selink' : 'border-line2 text-fg2 hover:border-fg3'}`}>
            <span className="grid h-3 w-3 place-items-center" aria-hidden>{GLYPH[k]}</span><span className="num">{n} new {SINCE_WORD[k][n === 1 ? 0 : 1]}</span></button>) })}
      </div>}
    </section>
  )
}

/* ---------------------------------------------------------------- the 30-day timeline */
const LANES: [FeedItem['kind'], string, string][] = [['tell', 'Tripwires', 'var(--z2)'], ['base', 'Bases', 'var(--z3)'], ['fire', 'Heat', 'color-mix(in srgb, var(--z3) 55%, var(--z0))'], ['official', 'Official', 'var(--fg2)']]
const WORD_OF: Record<FeedItem['kind'], [string, string]> = { tell: ['tripwire', 'tripwires'], base: ['base change', 'base changes'], fire: ['heat report', 'heat reports'], official: ['official step', 'official steps'] }
export const TIME_H = 124   // px the timeline takes at the foot of the map, with its margin

export function Timeline({ brief, day, setDay }: { brief: Brief; day: string | null; setDay: (d: string | null) => void }) {
  const end = parseGen(brief.generated).getTime()
  const days = useMemo(() => Array.from({ length: 30 }, (_, i) => utcDay(new Date(end - (29 - i) * 864e5))), [end])
  const counts = useMemo(() => {
    const c = Object.fromEntries(LANES.map(([k]) => [k, days.map(() => 0)])) as Record<FeedItem['kind'], number[]>
    for (const f of brief.feed) { const i = days.indexOf(f.date.slice(0, 10)); if (i >= 0) c[f.kind][i] += 1 }
    return c
  }, [brief.feed, days])
  const [focus, setFocus] = useState(29)
  const btns = useRef<(HTMLButtonElement | null)[]>([])
  const key = (e: KeyboardEvent) => {
    const to = e.key === 'ArrowLeft' ? focus - 1 : e.key === 'ArrowRight' ? focus + 1 : e.key === 'Home' ? 0 : e.key === 'End' ? 29 : null
    if (to == null) return
    e.preventDefault(); const k = Math.max(0, Math.min(29, to)); setFocus(k); btns.current[k]?.focus()
  }
  const say = (i: number) => {
    const parts = LANES.map(([k]) => counts[k][i] ? `${counts[k][i]} ${WORD_OF[k][counts[k][i] === 1 ? 0 : 1]}` : '').filter(Boolean)
    return `${i === 29 ? 'Today, ' : ''}${shortDate(days[i])}: ${parts.length ? parts.join(', ') : 'nothing logged'}`
  }
  return (
    <div className="absolute inset-x-3.5 bottom-3.5 z-10 rounded-r3 border border-line bg-[color-mix(in_oklab,var(--bg)_88%,transparent)] px-3.5 pb-2 pt-2.5 backdrop-blur-[12px]">
      <div className="mb-[7px] flex items-center justify-between gap-3">
        <span className="eyebrow">Last 30 days, all theatres</span>
        {day ? <span className="text-[11px] text-fg3"><span className="text-fg2">{shortDate(day)}</span> · <button onClick={() => setDay(null)} className="lnk">Show all days</button></span>
          : <span className="text-[11px] text-fg3">Pick a day to filter what changed</span>}
      </div>
      <div className="flex gap-0">
        <div className="flex w-[62px] shrink-0 flex-col gap-[3px] text-[10.5px] leading-[11px] text-fg3" aria-hidden>{LANES.map(([k, label]) => <span key={k} className="h-[11px]">{label}</span>)}</div>
        <div role="listbox" aria-label="Last 30 days. Pick a day to filter the map and what changed." onKeyDown={key} className="grid min-w-0 flex-1 gap-0.5" style={{ gridTemplateColumns: 'repeat(30, minmax(0, 1fr))' }}>
          {days.map((d, i) => { const on = d === day; return (
            <button key={d} ref={el => { btns.current[i] = el }} role="option" aria-selected={on} aria-label={say(i)} title={say(i)} tabIndex={i === (day ? days.indexOf(day) : focus) ? 0 : -1}
              onFocus={() => setFocus(i)} onClick={() => setDay(on ? null : d)}
              className={`group flex flex-col gap-[3px] rounded-[3px] outline-offset-1 ${on ? 'outline outline-1 outline-sel' : ''}`}>
              {LANES.map(([k, , tone]) => { const n = counts[k][i], mx = Math.max(1, ...counts[k]); return (
                <i key={k} className="h-[11px] w-full rounded-[2px] transition-transform duration-[120ms] group-hover:scale-y-[1.3]" style={{ background: n ? tone : 'var(--z0)', opacity: !n ? 1 : n / mx > .6 ? 1 : n / mx > .25 ? .7 : .45 }} />) })}
            </button>) })}
        </div>
      </div>
      <div className="ml-[62px] mt-[3px] grid gap-0.5 font-mono text-[9.5px] leading-[10px] text-fg3" style={{ gridTemplateColumns: 'repeat(30, minmax(0, 1fr))' }} aria-hidden>
        {days.map((d, i) => <span key={d} className={`whitespace-nowrap ${i === 29 ? 'text-right font-medium text-fg2' : ''}`} style={i === 29 ? { direction: 'rtl' } : undefined}>{i === 29 ? 'today' : i % 5 === 0 && i < 25 ? shortDate(d) : ''}</span>)}
      </div>
    </div>
  )
}
