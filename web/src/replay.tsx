import { createContext, useContext, useMemo } from 'react'
import { GROUPS, useBuildup, shortDate, type Brief, type FeedItem, type Group, type Level } from './data'

/* Replaying a day of the last 30 on Watch (the timeline, ?d=2026-11-04). Only what the data keeps per day is replayed:
   - each theatre's level at that day's first run: brief theatres[].levels (contract.day_levels, the forward record's level on the
     days the model was off). A day that is not there was not kept, and the board says "not kept", never "quiet";
   - the tripwires lit at that day's first run: brief theatres[].wires (contract.day_wires, the forward tells record). A day the
     record has no rows for was not kept, and says so; an empty list is a day with nothing lit;
   - each signal group's reading that day: signals/buildup.json, the 60-day strips rebuilt from every signal's own score history with
     today's grouping (display only, as on the Signals page);
   - what changed on that day and in the week to it: the dated feed. Heat is kept fewer days than the feed (brief.replay.heatFrom),
     so a day before that says heat was not kept, not that there was none.
   Live, not replayed: the map's marks, the 0 to 100 readings, the context tags and the dossier's tabs. Since-you-last-looked and
   notifications read the live brief and never this. */

export const WINDOW = 7
/* wires: the tripwire ids lit at that day's run, null when the record was not kept for that day */
export type DayTheatre = { level: Level | null; groups: Record<Group, number | null> | null; wires: string[] | null }
/* partial: the week reaches back past the feed's first day; heatFrom: the first day heat is kept (null in older data: unknown);
   groupsPending: the day's group readings are still loading; names: tripwire id to name */
export type Replay = { day: string; theatres: Record<string, DayTheatre>; week: FeedItem[]; groupsKept: boolean; groupsPending: boolean
  wiresKept: boolean; names: Record<string, string>; heatFrom: string | null; partial: boolean; feedFrom: string }

const Ctx = createContext<Replay | null>(null)
export const useReplay = () => useContext(Ctx)
export const minusDays = (d: string, n: number) => new Date(Date.parse(d + 'T12:00Z') - n * 864e5).toISOString().slice(0, 10)
/* the feed items of the 7 days to `day`, that day included */
export const inWeek = (f: FeedItem, day: string) => { const d = f.date.slice(0, 10); return d <= day && d > minusDays(day, WINDOW) }

export function ReplayProvider({ brief, day, children }: { brief: Brief; day: string | null; children: React.ReactNode }) {
  const bq = useBuildup(!!day)
  const value = useMemo<Replay | null>(() => { try { return build() } catch (e) {
    /* data the replay cannot read: the day is shown with nothing kept, never today's data under the day's name */
    console.warn('WarWatch: the replay could not read the data', e)
    return day ? { day, theatres: Object.fromEntries(brief.theatres.map(t => [t.id, { level: null, groups: null, wires: null }])), week: [], groupsKept: false, groupsPending: false,
      wiresKept: false, names: {}, heatFrom: null, partial: false, feedFrom: minusDays(brief.generated.slice(0, 10), 29) } : null
  } function build(): Replay | null {
    if (!day) return null
    const week = brief.feed.filter(f => inWeek(f, day))
    const b = bq.data, i = b ? b.dates.indexOf(day) : -1
    const theatres: Record<string, DayTheatre> = {}
    for (const t of brief.theatres) {
      const row = i >= 0 ? b!.theatres.find(x => x.id === t.id) : undefined
      const lit = (t.wires || []).find(x => x[0] === day)
      theatres[t.id] = {
        level: (t.levels || []).find(x => x[0] === day)?.[1] ?? null,
        groups: row ? Object.fromEntries(GROUPS.map(g => [g, row.groups[g]?.[i] ?? null])) as Record<Group, number | null> : null,
        wires: lit ? lit[1] : null,
      }
    }
    const feedFrom = minusDays(brief.generated.slice(0, 10), 29)
    return { day, theatres, week, groupsKept: i >= 0, groupsPending: bq.isPending, wiresKept: Object.values(theatres).some(x => x.wires), names: brief.replay?.tripwires ?? {},
      heatFrom: brief.replay?.heatFrom ?? null, partial: minusDays(day, WINDOW - 1) < feedFrom, feedFrom }
  } }, [brief, day, bq.data, bq.isPending])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

/* one row per tripwire: a rule that fired on two days of the week is one tripwire, with its latest day (as the board counts lit ones) */
export const latestWires = (fs: FeedItem[]) => { const m = new Map<string, FeedItem>(); for (const f of fs) { const k = f.theatre + '|' + f.title, o = m.get(k); if (!o || f.date > o.date) m.set(k, f) } return [...m.values()].sort((a, b) => b.date.localeCompare(a.date)) }

/* a strike wave in the feed (contract.feed, from tells.wave_onsets): the start of a wave of alerts, an event of its own, not a tripwire */
export const isWave = (f: FeedItem) => f.kind === 'tell' && f.title === 'Strike wave'

/* the replay line: the day, and everything that stays live beside it */
export const replayHead = (day: string) => `Replaying ${shortDate(day)}`
export const replayLive = 'Levels, tripwires, signal groups and the feed are that day\'s. Still live: the map\'s marks, the 0 to 100 readings, context tags, the dossier\'s tabs and the data health readout.'
export const replayWords = (day: string) => `${replayHead(day)}. ${replayLive}`
