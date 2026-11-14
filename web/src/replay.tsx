import { createContext, useContext, useMemo } from 'react'
import { GROUPS, useBuildup, shortDate, type Brief, type FeedItem, type Group, type Level } from './data'

/* Replaying a day of the last 30 on Watch (the timeline, ?d=2026-11-04). Only what the data keeps per day is replayed:
   - each theatre's level at that day's first run: brief theatres[].levels (contract.day_levels, the forward record's level on the
     days the model was off). A day that is not there was not kept, and the board says "not kept", never "quiet";
   - each signal group's reading that day: signals/buildup.json, the 60-day strips rebuilt from every signal's own score history with
     today's grouping (display only, as on the Signals page);
   - the tripwires that fired in the 7 days to that day, and everything else that changed on it: the dated feed.
   The 0 to 100 reading is not kept per day, and the map's marks are live only, so neither replays. Since-you-last-looked and
   notifications read the live brief and never this. */

export const WINDOW = 7
export type DayTheatre = { level: Level | null; groups: Record<Group, number | null> | null; wires: FeedItem[] }
/* partial: the week reaches back past the feed's first day, so tripwires that fired before it are not in the data */
export type Replay = { day: string; theatres: Record<string, DayTheatre>; week: FeedItem[]; groupsKept: boolean; partial: boolean; feedFrom: string }

const Ctx = createContext<Replay | null>(null)
export const useReplay = () => useContext(Ctx)
export const minusDays = (d: string, n: number) => new Date(Date.parse(d + 'T12:00Z') - n * 864e5).toISOString().slice(0, 10)
/* the feed items of the 7 days to `day`, that day included */
export const inWeek = (f: FeedItem, day: string) => { const d = f.date.slice(0, 10); return d <= day && d > minusDays(day, WINDOW) }

export function ReplayProvider({ brief, day, children }: { brief: Brief; day: string | null; children: React.ReactNode }) {
  const bq = useBuildup(!!day)
  const value = useMemo<Replay | null>(() => {
    if (!day) return null
    const week = brief.feed.filter(f => inWeek(f, day))
    const b = bq.data, i = b ? b.dates.indexOf(day) : -1
    const theatres: Record<string, DayTheatre> = {}
    for (const t of brief.theatres) {
      const row = i >= 0 ? b!.theatres.find(x => x.id === t.id) : undefined
      theatres[t.id] = {
        level: (t.levels || []).find(x => x[0] === day)?.[1] ?? null,
        groups: row ? Object.fromEntries(GROUPS.map(g => [g, row.groups[g]?.[i] ?? null])) as Record<Group, number | null> : null,
        wires: latestWires(week.filter(f => f.kind === 'tell' && f.theatre === t.id)),
      }
    }
    const feedFrom = minusDays(brief.generated.slice(0, 10), 29)
    return { day, theatres, week, groupsKept: i >= 0, partial: minusDays(day, WINDOW - 1) < feedFrom, feedFrom }
  }, [brief, day, bq.data])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

/* one row per tripwire: a rule that fired on two days of the week is one tripwire, with its latest day (as the board counts lit ones) */
export const latestWires = (fs: FeedItem[]) => { const m = new Map<string, FeedItem>(); for (const f of fs) { const k = f.theatre + '|' + f.title, o = m.get(k); if (!o || f.date > o.date) m.set(k, f) } return [...m.values()].sort((a, b) => b.date.localeCompare(a.date)) }

/* "Showing 4 Nov." and what does not replay */
export const replayWords = (day: string) => `Showing ${shortDate(day)}. The map shows today's marks; only the board, tripwires and feed replay.`
