import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { GROUPS, short, levelWord, groupTone, wholeScore, shortDate, parseGen, type Brief, type BriefTheatre, type LiveMap } from './data'
import { usePrefs, fmtTime, reducedMotion } from './settings'
import { DEFAULT_LAYERS } from './layers'
import { useAge, ageWords, lateAfter } from './health'
import { sentence } from './watch'
import { Mark, Boundary } from './ui'
import { latestWires, isWave } from './replay'

/* Wall: Watch on a spare screen, read from across a room (/wall/). No controls: a small hint says how to leave and fades after a few
   seconds, coming back on a pointer move or a key. Escape returns to Watch (App), F switches the browser's full screen.
   It shows the status sentence and the time of the data, the theatres closest to Watch, the week's tripwires and how old the data
   is, and a globe that moves slowly from one of the closest theatres to the next: the one approved loop. Under reduced motion it
   holds still and changes theatre with a cut, once a minute. The brief is fetched again every 10 minutes (data.ts), and the screen
   is kept awake where the browser allows it. Below 900 px it is one readable column without the globe.
   The globe moves for 3 seconds every 30 and draws nothing in between (MapView asks for no frame while the camera is still), so a
   screen left on all day costs little. The smallest text never goes under 12 px. If the globe cannot load, the text side stays. */

const MapView = lazy(() => import('./MapView').then(m => ({ default: m.MapView })))
const RANK: Record<string, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }
const ROWS = 8, TOUR = 5, EVERY = 30_000, EVERY_STILL = 60_000
/* the smallest text on the wall: never under 12 px, whatever the screen */
const SMALL = 'text-[max(12px,.8em)]', LABEL = 'text-[max(12px,.85em)]'

/* above Watch first, highest level first, then the highest readings: the board's "closest to Watch" */
const closest = (b: Brief) => [...b.theatres].sort((x, y) => RANK[y.level] - RANK[x.level] || (y.score ?? -1) - (x.score ?? -1))

export default function Wall({ brief, live }: { brief: Brief; live?: LiveMap }) {
  const { prefs, theme } = usePrefs()
  const [wide, setWide] = useState(() => innerWidth >= 900)
  /* a short screen (under 800 px tall, as 1280 x 720) lists fewer rows, so nothing is cut off at the foot */
  const [short_, setShort] = useState(() => innerHeight < 800)
  useEffect(() => { const f = () => { setWide(innerWidth >= 900); setShort(innerHeight < 800) }; addEventListener('resize', f); return () => removeEventListener('resize', f) }, [])
  const nRows = wide && short_ ? 6 : ROWS, nWires = wide && short_ ? 3 : 6
  const rows = useMemo(() => closest(brief).slice(0, nRows), [brief, nRows])
  const tour = useMemo(() => closest(brief).filter(t => t.center).slice(0, TOUR).map(t => t.id), [brief])
  const [k, setK] = useState(0)
  const still = prefs.motion === 'reduced' || reducedMotion()
  useEffect(() => { if (!tour.length) return; const i = setInterval(() => setK(n => (n + 1) % tour.length), still ? EVERY_STILL : EVERY); return () => clearInterval(i) }, [tour.length, still])
  const now = tour[k % Math.max(1, tour.length)], nowT = brief.theatres.find(t => t.id === now)

  /* the exit hint: shown on arrival, gone after 4 seconds, back on any pointer move or key */
  const [hint, setHint] = useState(true)
  useEffect(() => {
    let t = setTimeout(() => setHint(false), 4000)
    const wake = () => { setHint(true); clearTimeout(t); t = setTimeout(() => setHint(false), 4000) }
    const key = (e: KeyboardEvent) => {
      wake()
      if ((e.key === 'f' || e.key === 'F') && !e.metaKey && !e.ctrlKey && !e.altKey) {
        try { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.() } catch { /* not allowed: nothing happens */ }
      }
    }
    addEventListener('pointermove', wake); addEventListener('keydown', key)
    return () => { clearTimeout(t); removeEventListener('pointermove', wake); removeEventListener('keydown', key) }
  }, [])

  /* keep the screen awake while the wall is open; a browser without the API, or one that refuses, is left alone */
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null, gone = false
    const ask = async () => { try { const w = (navigator as any).wakeLock; if (w && document.visibilityState === 'visible') { lock = await w.request('screen'); if (gone) lock?.release().catch(() => {}) } } catch { /* refused: fine */ } }
    const vis = () => { if (document.visibilityState === 'visible') ask() }
    ask(); document.addEventListener('visibilitychange', vis)
    return () => { gone = true; document.removeEventListener('visibilitychange', vis); lock?.release().catch(() => {}) }
  }, [])
  useEffect(() => () => { try { if (document.fullscreenElement) document.exitFullscreen() } catch { /* already gone */ } }, [])

  const age = useAge(brief), late = age > lateAfter(brief)
  const at = parseGen(brief.generated)
  const week = useMemo(() => { const from = new Date(at.getTime() - 6 * 864e5).toISOString().slice(0, 10); return latestWires(brief.feed.filter(f => f.kind === 'tell' && !isWave(f) && f.date.slice(0, 10) >= from)) }, [brief])   // a strike wave is an event, not a tripwire
  const name = (id: string) => short(brief.theatres.find(t => t.id === id)?.name || id)
  const size = wide ? 'clamp(13px, min(0.9vw, 1.6vh), 40px)' : '15px'

  /* how to leave: at the foot of the globe, right, clear of the map's credit on the left; at the foot of the screen on phones */
  const hintEl = <p aria-hidden={!hint} className={`pointer-events-none ${wide ? 'absolute bottom-[1.4em] right-[1.6em]' : 'fixed bottom-4 left-1/2 -translate-x-1/2 shadow-sm'} z-20 rounded-full border border-line bg-s2 px-[1em] py-[.35em] ${SMALL} text-fg2 transition-opacity duration-200 ${hint ? 'opacity-100' : 'opacity-0'}`}>
    {wide ? 'Esc to leave · F for full screen' : 'Esc or Back to leave'}</p>
  return (
    <div className={`bg-bg text-fg ${wide ? 'grid h-full grid-cols-[minmax(0,.92fr)_minmax(0,1.08fr)] overflow-hidden' : 'h-full overflow-y-auto'}`} style={{ fontSize: size }}>
      <main className={`flex min-h-0 min-w-0 flex-col ${wide ? 'overflow-hidden px-[2.4em] py-[1.8em]' : 'px-4 py-5'}`}>
        <div className="flex items-center justify-between gap-[1em] text-fg2">
          <span className="flex items-center gap-[.5em] font-semibold text-fg" style={{ fontSize: '1.15em' }}><Mark size={22} />WarWatch</span>
          <span className="num text-right text-[.95em]">Updated {fmtTime(at, prefs.tz)}, {ageWords(age)}</span>
        </div>
        {late && <p role="status" className="mt-[1em] rounded-r2 border border-line2 bg-s2 px-[1em] py-[.6em] text-[1em] leading-[1.35]">
          Late: this data is from {shortDate(brief.generated.slice(0, 10))}, {fmtTime(at, prefs.tz)}. WarWatch updates every {brief.health?.everyMinutes ?? 30} minutes, so what is shown may be out of date.</p>}
        <h1 className="mt-[.9em] font-serif text-[1.85em] font-normal leading-[1.22] tracking-[-0.012em] [text-wrap:pretty]">{sentence(brief)}</h1>

        <section aria-label="Theatres closest to Watch" className="mt-[1.3em] min-h-0">
          <h2 className={`mb-[.4em] ${LABEL} font-medium uppercase tracking-[.08em] text-fg2`}>Closest to Watch</h2>
          <ol>{rows.map(t => <WallRow key={t.id} t={t} on={wide && t.id === now} />)}</ol>
          <p className={`mt-[.5em] ${SMALL} leading-[1.35] text-fg2`}>Reading, 0 to 100, grey: not a chance of war. Five cells: Logistics, Markets, People, News, Physical.</p>
        </section>

        <section aria-label="Tripwires this week" className="mt-[1.2em] min-h-0 overflow-hidden">
          <h2 className={`mb-[.4em] ${LABEL} font-medium uppercase tracking-[.08em] text-fg2`}>Tripwires this week{week.length ? `, ${week.length}` : ''}</h2>
          {week.length ? <ul>{week.slice(0, nWires).map((f, i) => (
            <li key={i} className="flex items-baseline gap-[.6em] border-t border-line py-[.3em] text-[1em]">
              <i className="h-[.5em] w-[.5em] shrink-0 translate-y-[-.1em] rounded-full bg-z2" aria-hidden />
              <span className="num w-[4.2em] shrink-0 text-fg2">{shortDate(f.date.slice(0, 10))}</span>
              <span className="min-w-0 truncate"><b className="font-medium">{name(f.theatre)}</b> · {f.title}</span>
            </li>))}{week.length > nWires && <li className={`pt-[.3em] ${LABEL} text-fg2`}>and {week.length - nWires} more</li>}</ul>
            : <p className="text-[1em] text-fg2">No tripwire fired this week.</p>}
        </section>
      </main>

      {wide && <div className="relative min-h-0 min-w-0 border-l border-line" inert>
        <Boundary what="the globe" at="m-[2em]"><Suspense fallback={null}>
          <MapView brief={brief} live={live} route={now ? { v: 'theatre', id: now } : { v: 'brief' }} onPick={() => {}} theme={theme} wide padBottom={0}
            flat={false} labels={1.35} layers={DEFAULT_LAYERS} onToggle={() => {}} wall />
        </Suspense>
        {/* the caption sits at the top of the globe, clear of the map's credit line at the foot; no blur, so a moving globe is not
            blurred again on every frame */}
        {nowT && <div data-wall-caption className="pointer-events-none absolute inset-x-[1.6em] top-[1.4em] z-10 flex items-baseline justify-between gap-[1em] rounded-r3 border border-line bg-[color-mix(in_oklab,var(--bg)_92%,transparent)] px-[1.1em] py-[.7em]">
          <span className="min-w-0 truncate text-[1.35em] font-medium">{short(nowT.name)}<span className="ml-[.5em] text-[.75em] font-normal text-fg2">{levelWord(nowT.level)}</span></span>
          <span className="num shrink-0 text-fg2">readings <b className="font-medium text-fg2">{nowT.score == null ? '–' : wholeScore(nowT.score)}</b> of 100</span>
        </div>}
        </Boundary>
        {hintEl}
      </div>}

      {!wide && hintEl}
    </div>
  )
}

function WallRow({ t, on }: { t: BriefTheatre; on: boolean }) {
  const s = t.score == null ? null : Math.max(0, Math.min(100, t.score))
  return (
    <li className={`grid grid-cols-[minmax(0,1fr)_5.2em_7em_2em] items-center gap-[.8em] border-t border-line py-[.42em] ${on ? 'bg-s2' : ''}`}
      aria-label={`${t.name}, ${levelWord(t.level).toLowerCase()}, reading ${s == null ? 'not available' : wholeScore(s)}${t.tellsOn ? `, ${t.tellsOn} ${t.tellsOn === 1 ? 'tripwire' : 'tripwires'} this week` : ''}`}>
      <span className="flex min-w-0 items-baseline gap-[.5em]" aria-hidden>
        <b className="truncate text-[1.15em] font-medium">{short(t.name)}</b>
        {t.level !== 'Normal' && <span className={`shrink-0 ${LABEL} font-medium`} style={{ color: t.level === 'Critical' ? 'var(--crit)' : t.level === 'Elevated' ? 'var(--z3-text)' : 'var(--z2-text)' }}>{t.level}</span>}
        {t.tellsOn > 0 && <span className={`inline-flex shrink-0 items-center gap-[.25em] font-mono ${SMALL} text-fg2`}><i className="h-[.45em] w-[.45em] rounded-full bg-z2" />{t.tellsOn}</span>}
      </span>
      <span className="grid grid-cols-5 gap-[.15em]" aria-hidden>{GROUPS.map(g => <i key={g} className="h-[1em] rounded-[2px]" style={{ background: groupTone(t.groups[g]) }} />)}</span>
      <span className="relative h-[.4em] rounded-full bg-z0" aria-hidden><i className="absolute inset-y-0 left-0 rounded-full bg-fg2" style={{ width: `${s ?? 0}%` }} /></span>
      <b className="num text-right text-[1.05em] font-medium text-fg2" aria-hidden>{s == null ? '–' : wholeScore(s)}</b>
    </li>
  )
}
