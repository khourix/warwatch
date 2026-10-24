import { useEffect, useMemo, useRef, useState } from 'react'
import { Play, Pause } from 'lucide-react'
import { parseGen, shortDate, type Brief, type FeedItem, type Route } from './data'
import { toRoute } from './views'

/* The 30-day strip under the map: what happened each day (timing tells, base changes on radar, unusual fires, official steps),
   from the Brief's feed. Picking a day filters the map's fires and base passes to it; Play steps a day every 160 ms;
   Live returns to now. */

const TONE: Record<FeedItem['kind'], string> = { tell: 'var(--watch)', base: 'var(--elev)', fire: 'var(--elev)', official: 'var(--event)' }
const WORD: Record<FeedItem['kind'], string> = { tell: 'timing tell', base: 'base change', fire: 'unusual fire', official: 'official step' }

export function TimeStrip({ brief, day, setDay, go, style }: { brief: Brief; day: string | null; setDay: (d: string | null) => void; go: (r: Route) => void; style: React.CSSProperties }) {
  const now = parseGen(brief.generated)
  const days = useMemo(() => Array.from({ length: 30 }, (_, i) => new Date(now.getTime() - (29 - i) * 864e5).toISOString().slice(0, 10)), [brief.generated])
  const byDay = useMemo(() => {
    const m: Record<string, FeedItem[]> = {}
    for (const f of brief.feed) (m[f.date.slice(0, 10)] ||= []).push(f)
    return m
  }, [brief.feed])
  const [playing, setPlaying] = useState(false)
  const t = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (!playing) return
    let i = day ? days.indexOf(day) : -1
    t.current = window.setInterval(() => {
      i += 1
      if (i >= days.length) { setPlaying(false); setDay(null); return }
      setDay(days[i])
    }, 160)
    return () => window.clearInterval(t.current)
  }, [playing])
  const name = (id: string) => brief.theatres.find(x => x.id === id)?.name || id
  const sel = day ? byDay[day] || [] : []
  return (
    <div className="absolute z-10 rounded-2xl border border-line bg-panel/85 px-3 pb-2 pt-2 shadow-[var(--shadow)] backdrop-blur-md" style={style}>
      {day && <div className="mb-1.5 flex items-center gap-2 px-1 text-[12px] text-fg2" aria-live="polite">
        <b className="font-medium text-fg">{shortDate(day)}</b>
        <span className="min-w-0 flex-1 truncate">{sel.length ? sel.map(f => `${name(f.theatre)}: ${f.title}`).join(' · ') : 'Nothing logged this day.'}</span>
        {sel[0] && !playing && <button onClick={() => go(toRoute(sel[0].to))} className="shrink-0 text-accent hover:underline">Open</button>}
      </div>}
      <div className="flex items-end gap-3">
        <button onClick={() => { if (!playing && day === days[days.length - 1]) setDay(null); setPlaying(!playing) }} aria-label={playing ? 'Pause' : 'Play the last 30 days'} className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-line text-fg2 hover:bg-hover hover:text-fg">{playing ? <Pause size={13} /> : <Play size={13} className="ml-0.5" />}</button>
        <div className="grid min-w-0 flex-1 items-end gap-[3px]" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))` }} role="listbox" aria-label="Last 30 days">
          {days.map(d => { const fs = byDay[d] || [], on = d === day; return (
            <button key={d} role="option" aria-selected={on} onClick={() => { setPlaying(false); setDay(on ? null : d) }} title={`${shortDate(d)}${fs.length ? ': ' + fs.map(f => `${name(f.theatre)}, ${WORD[f.kind]}`).join('; ') : ''}`}
              className="group flex h-[38px] flex-col items-center justify-end gap-[3px] rounded-[4px] pb-1 hover:bg-hover" style={{ background: on ? 'var(--accent-soft)' : undefined }}>
              {fs.slice(0, 5).map((f, i) => <i key={i} className="h-[5px] w-[5px] rounded-full" style={{ background: TONE[f.kind] }} />)}
              <i className="h-[2px] w-full rounded-full" style={{ background: on ? 'var(--accent)' : 'var(--line-2)' }} />
            </button>) })}
        </div>
        <button onClick={() => { setPlaying(false); setDay(null) }} aria-pressed={!day} className="shrink-0 pb-1 text-right text-[12px] leading-tight">
          <span className={`flex items-center justify-end gap-1.5 font-medium ${day ? 'text-fg3' : 'text-fg'}`}>{!day && <span className="relative h-1.5 w-1.5 rounded-full bg-accent text-accent live-dot" />}Live</span>
          <span className="text-fg3">last 30 days</span>
        </button>
      </div>
    </div>
  )
}
