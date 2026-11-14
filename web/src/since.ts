import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { wholeScore, parseGen, type Brief, type FeedItem, type Level } from './data'

/* "Since you last looked": this browser keeps a small snapshot of the last visit (when, each theatre's level and whole-number
   reading, and the keys of the feed's last week). On the next visit, more than an hour later, Watch shows what moved since.
   The snapshot is written when the visit ends (the page is hidden or closed), or at once when the block is dismissed, so the
   block keeps describing the same gap for the whole visit. A first visit shows nothing and saves a snapshot straight away.
   Storage can be missing or refuse (private mode): then there is simply no block. */

const KEY = 'ww-last-visit'
const HOUR = 36e5
const WINDOW_DAYS = 7
type Snap = { v: 1; at: number; gen: string; from: string; th: [string, Level, number | null][]; feed: string[] }
export type Moved = { id: string; name: string; from: [Level, number | null]; to: [Level, number | null] }
export type Since = { at: Date; moved: Moved[]; fresh: Set<string>; counts: Record<FeedItem['kind'], number> }

/* A feed item's identity between runs. Heat titles carry counts and a site name that change from run to run, and a base's
   title carries its words, so those are keyed by what they are about; tripwire and official titles are fixed names. */
export function feedKey(f: FeedItem): string {
  const d = f.date.slice(0, 10)
  switch (f.kind) {
    case 'fire': return `${d}|${f.theatre}|fire`
    case 'base': return `${d}|base|${f.to?.id || f.title}`
    default: return `${d}|${f.theatre}|${f.kind}|${f.title}`
  }
}
const whole = (s: number | null) => s == null ? null : wholeScore(s)

function snapshot(b: Brief): Snap {
  const from = new Date(parseGen(b.generated).getTime() - WINDOW_DAYS * 864e5).toISOString().slice(0, 10)
  return { v: 1, at: Date.now(), gen: b.generated, from, th: b.theatres.map(t => [t.id, t.level, whole(t.score)]), feed: b.feed.filter(f => f.date.slice(0, 10) >= from).map(feedKey) }
}
/* anything not exactly the shape this file writes is dropped (and later overwritten), never trusted */
const valid = (s: any): s is Snap => !!s && s.v === 1 && Number.isFinite(s.at) && typeof s.from === 'string'
  && Array.isArray(s.th) && s.th.every((x: unknown) => Array.isArray(x) && typeof x[0] === 'string' && typeof x[1] === 'string' && (x[2] === null || Number.isFinite(x[2])))
  && Array.isArray(s.feed) && s.feed.every((k: unknown) => typeof k === 'string')
function read(): Snap | null {
  try { const s = JSON.parse(localStorage.getItem(KEY) || 'null'); return valid(s) ? s : null } catch { return null }
}
function write(b: Brief) {
  try { localStorage.setItem(KEY, JSON.stringify(snapshot(b))) } catch { /* private mode: nothing kept */ }
}

export function diff(prev: Snap, b: Brief): Since {
  const old = new Map(prev.th.map(x => [x[0], x]))
  const moved: Moved[] = []
  for (const t of b.theatres) {
    const p = old.get(t.id); if (!p) continue
    const w = whole(t.score)
    if (p[1] !== t.level || p[2] !== w) moved.push({ id: t.id, name: t.name, from: [p[1], p[2]], to: [t.level, w] })
  }
  const rank: Record<string, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }
  moved.sort((x, y) => Number(y.from[0] !== y.to[0]) - Number(x.from[0] !== x.to[0]) || rank[y.to[0]] - rank[x.to[0]]
    || Math.abs((y.to[1] ?? 0) - (y.from[1] ?? 0)) - Math.abs((x.to[1] ?? 0) - (x.from[1] ?? 0)))
  /* counts are rows, so a count matches the rows its chip shows */
  const seen = new Set(prev.feed), fresh = new Set<string>()
  const counts: Since['counts'] = { tell: 0, base: 0, fire: 0, official: 0 }
  for (const f of b.feed) { const k = feedKey(f); if (f.date.slice(0, 10) >= prev.from && !seen.has(k)) { fresh.add(k); if (f.kind in counts) counts[f.kind] += 1 } }
  return { at: new Date(prev.at), moved, fresh, counts }
}

export function useSinceLastVisit(brief: Brief): { since: Since | null; dismiss: () => void } {
  const [prev] = useState(read)
  const [gone, setGone] = useState(false)
  const latest = useRef(brief); latest.current = brief
  useEffect(() => {
    if (!prev) write(brief)
    const end = () => { if (document.visibilityState === 'hidden') write(latest.current) }
    const hide = () => write(latest.current)
    document.addEventListener('visibilitychange', end); addEventListener('pagehide', hide)
    return () => { document.removeEventListener('visibilitychange', end); removeEventListener('pagehide', hide) }
  }, [])
  const since = useMemo(() => {
    if (!prev || gone || Date.now() - prev.at <= HOUR) return null
    try { return diff(prev, brief) } catch { return null }     // a surprise in old data costs the block, never the page
  }, [prev, gone, brief])
  const dismiss = useCallback(() => { write(latest.current); setGone(true) }, [])
  return { since, dismiss }
}
