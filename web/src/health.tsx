import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useRecord, parseGen, type Brief, type Route } from './data'
import { usePrefs, fmtTime } from './settings'
import { fmtAsOf } from './ui'

/* Data health in view: the top bar's readout says how old the data is and how many sources reported a problem; opening it lists
   the signals scoring, collecting and failed, each source's problem and how often each source updates. Read from brief.health
   (contract.health, added November 2026); older data has none, and then the readout shows the age alone.
   The data is late when it is older than lateAfterMinutes (90, the live freshness check's limit: by then the two half-hourly runs due
   after it have not come through, and a third is due). "Reported a problem" is the honest count: some of those sources fell back to
   another feed that worked, and some are WarWatch's own caches. No warning colour here: a problem is an ink ring, all well the ok dot. */

const LATE = 90, EVERY = 30
export const lateAfter = (b: Brief) => b.health?.lateAfterMinutes ?? LATE
/* minutes since the run, kept current while the page stays open; below zero when the run's time is ahead of this device's clock */
export function useAge(b: Brief) {
  const at = parseGen(b.generated).getTime(), [now, setNow] = useState(Date.now)
  useEffect(() => { setNow(Date.now()); const i = setInterval(() => setNow(Date.now()), 60_000); return () => clearInterval(i) }, [at])
  return Math.round((now - at) / 6e4)
}
/* a run timed more than 5 minutes ahead says so, rather than "just now": this device's clock, or the run's, is off */
export const AHEAD = -5
export const ageWords = (m: number) => m < AHEAD ? "timed ahead of this device's clock" : m < 2 ? 'just now' : m < 60 ? `${m} minutes ago` : m < 120 ? 'an hour ago' : m < 48 * 60 ? `${Math.round(m / 60)} hours ago` : `${Math.round(m / 1440)} days ago`
const ageShort = (m: number) => m < AHEAD ? 'ahead' : m < 60 ? `${Math.max(1, m)} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`

export function HealthReadout({ brief, go, phone = false }: { brief: Brief; go: (r: Route) => void; phone?: boolean }) {
  const { prefs } = usePrefs()
  const age = useAge(brief), late = age > lateAfter(brief)
  const sources = brief.health?.sources || []
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null), btn = useRef<HTMLButtonElement>(null), panel = useRef<HTMLDivElement>(null)
  const rec = useRecord(open)
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); setOpen(false); btn.current?.focus() } }
    const c = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    /* a non-modal panel: it closes when the focus moves out of it (Tab past its last link), as on a tap elsewhere */
    const out = (e: FocusEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    addEventListener('keydown', k, true); addEventListener('pointerdown', c); document.addEventListener('focusin', out)
    requestAnimationFrame(() => panel.current?.focus())
    return () => { removeEventListener('keydown', k, true); removeEventListener('pointerdown', c); document.removeEventListener('focusin', out) }
  }, [open])
  const at = parseGen(brief.generated)
  const say = `Data updated ${fmtTime(at, prefs.tz)}, ${ageWords(age)}${late ? ', later than expected' : ''}.${sources.length ? ` ${sources.length} ${sources.length === 1 ? 'source' : 'sources'} reported a problem.` : ''} Show data health.`
  const trouble = late || sources.length > 0
  const st = brief.health?.statuses
  return (
    <div ref={box} className="relative">
      <button ref={btn} onClick={() => setOpen(o => !o)} aria-expanded={open} aria-label={say}
        className={phone ? 'relative flex h-9 items-center gap-1.5 rounded-full after:absolute after:-inset-[5px] after:content-[\'\'] border border-line bg-[color-mix(in_oklab,var(--s1)_85%,transparent)] px-2.5 text-[11.5px] text-fg2 backdrop-blur'
          : 'flex h-8 shrink-0 items-center gap-[7px] whitespace-nowrap rounded-r2 px-2 text-[12px] text-fg2 transition-colors duration-[120ms] hover:bg-s2 hover:text-fg'}>
        <span className={`relative h-[7px] w-[7px] shrink-0 rounded-full ${trouble ? 'border-[1.5px] border-fg' : 'bg-ok'}`} aria-hidden />
        {phone ? <span className="num">{ageShort(age)}</span>
          : <span className="num">Updated {fmtTime(at, prefs.tz)}{sources.length ? <span className="text-fg2"> · {sources.length} <span className="max-[1279px]:hidden">{sources.length === 1 ? 'source' : 'sources'} reported a problem</span><span className="min-[1280px]:hidden">{sources.length === 1 ? 'problem' : 'problems'}</span></span> : null}</span>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div ref={panel} tabIndex={-1} role="dialog" aria-label="Data health" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: .16, ease: [.2, .8, .2, 1] }}
            className={`z-40 flex flex-col overflow-hidden rounded-r3 border border-line2 bg-s1 text-left shadow-[var(--shadow)] outline-none ${phone ? 'fixed inset-x-2 top-[60px] max-h-[74dvh]' : 'absolute right-0 top-10 max-h-[min(640px,calc(100vh-90px))] w-[420px]'}`}>
            <div className="shrink-0 border-b border-line px-4 py-3">
              <h2 className="text-[14px] font-medium text-fg">Data health</h2>
              <p className="mt-0.5 text-[12px] leading-[1.45] text-fg2">This run was built {fmtAsOf(brief.generated, prefs.tz)}, {ageWords(age)}. A new run is due every {brief.health?.everyMinutes ?? EVERY} minutes{late ? ', so this data is later than it should be' : ''}.</p>
            </div>
            <div className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 pb-3">
              {st ? <section className="pt-3">
                <h3 className="eyebrow mb-2 !text-fg2">Signals</h3>
                <StatusBar st={st} />
                <dl className="mt-1.5">{statusRows(st).map(([k, label, n]) => <div key={k} className="flex justify-between gap-3 py-1 text-[12.5px]"><dt className="text-fg2">{label}</dt><dd className="num text-fg">{n}</dd></div>)}</dl>
              </section> : <p className="pt-3 text-[12.5px] text-fg2">This data run does not say how its sources did.</p>}
              {brief.health && <section className="mt-2 border-t border-line pt-3">
                {sources.length > 0 && <p className="mb-1 text-[12px] leading-[1.45] text-fg2">Not all of these lost data: some fell back to another feed, and some are WarWatch's own caches.</p>}
                <h3 className="eyebrow mb-1.5 !text-fg2">{sources.length ? `Sources that reported a problem, ${sources.length}` : 'Sources'}</h3>
                {sources.length ? <ul>{sources.map((s, i) => <li key={i} className="py-1.5 text-[12.5px] leading-[1.45]"><b className="font-medium text-fg">{s.source || 'Unnamed source'}</b><span className="block text-fg2">{s.why}</span></li>)}</ul>
                  : <p className="text-[12.5px] text-fg2">No source reported a problem this run.</p>}
              </section>}
              <section className="mt-2 border-t border-line pt-3">
                <h3 className="eyebrow mb-1.5 !text-fg2">How often sources update</h3>
                {rec.isPending ? <p className="text-[12.5px] text-fg2">Loading…</p> : rec.isError && !rec.data ? <p className="text-[12.5px] text-fg2">The update notes could not be loaded.</p>
                  : <ul>{rec.data.health.updates.map((u, i) => <li key={i} className="py-1.5 text-[12px] leading-[1.4]"><span className="flex flex-wrap justify-between gap-x-3"><b className="font-medium text-fg">{u.s}</b><span className="text-fg2">{u.e}</span></span><span className="block text-fg2">{u.l}</span></li>)}</ul>}
              </section>
            </div>
            <div className="shrink-0 border-t border-line px-4 py-2.5 text-[12.5px]"><button onClick={() => { setOpen(false); go({ v: 'record' }); requestAnimationFrame(() => document.getElementById('rec-health')?.scrollIntoView({ block: 'start' })) }} className="lnk">Data health on the Record page</button></div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* signal statuses as a bar (scoring, collecting, waiting for a key, failed) and as rows */
const STATUS: [string, string, string][] = [['ok', 'Scoring', 'var(--ok)'], ['collecting', 'Collecting history, not scored yet', 'var(--fg3)'], ['awaiting_key', 'Waiting for a free key', 'var(--fg3)'], ['error', 'Failed this run', 'ring']]
export function StatusBar({ st }: { st: Record<string, number> }) {
  const total = Object.values(st).reduce((a, b) => a + b, 0) || 1
  return <span className="flex h-2 gap-px overflow-hidden rounded-full bg-z0" aria-hidden>{STATUS.map(([k, , c]) => st[k] ? <i key={k} style={c === 'ring' ? { width: `${st[k] / total * 100}%`, boxShadow: 'inset 0 0 0 1px var(--fg)', borderRadius: 999 } : { width: `${st[k] / total * 100}%`, background: c }} /> : null)}</span>
}
export const statusRows = (st: Record<string, number>) => STATUS.filter(([k]) => st[k] || k === 'ok' || k === 'error').map(([k, label]) => [k, label, st[k] || 0] as const)

/* A calm line across the top when the data is late: what it is, how old, and that the page is not broken */
export function LateBanner({ brief }: { brief: Brief }) {
  const { prefs } = usePrefs()
  const age = useAge(brief)
  if (age <= lateAfter(brief)) return null
  return (
    <div role="status" className="border-b border-line bg-s2 px-4 py-2 text-[12.5px] leading-[1.4] text-fg">
      This data is from {fmtAsOf(brief.generated, prefs.tz)}, {ageWords(age)}. WarWatch normally updates every {brief.health?.everyMinutes ?? EVERY} minutes, so the latest runs have not come through and what you see may be out of date.
    </div>
  )
}
