import { motion } from 'motion/react'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { Link2 } from 'lucide-react'
import { levelVar, levelWord, zColor, routeHref, shortDate, parseGen, type Level, type Route } from './data'
import { term, type TermKey } from './glossary'
import { usePrefs, fmtTime } from './settings'

export function Mark({ size = 22, live = true }: { size?: number; live?: boolean }) {
  // The trace-W: a reading that dips, rises and dips again, ending in the live dot (a CSS pulse, so reduced motion stops it).
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <path d="M3 9.5 9.6 24 16 13.6 22.4 24 26.2 15.4" stroke="currentColor" strokeWidth="3.1" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="28" cy="10.4" r="3.1" fill="currentColor" data-live={live || undefined} />
    </svg>
  )
}
/* compact: below 360 px the name is read out but not drawn, so the phone bar's buttons fit */
export function Wordmark({ size = 15.5, mark = true, compact = false }: { size?: number; mark?: boolean; compact?: boolean }) {
  return <span className="flex shrink-0 items-center gap-2 text-fg">{mark && <Mark size={size + 6} />}<span className={`font-semibold tracking-[-0.02em] ${compact ? 'max-[359px]:sr-only' : ''}`} style={{ fontSize: size }}>WarWatch</span></span>
}

/* copying a link: the clipboard where the browser allows it, else the older copy command; false when neither works */
export async function copyText(t: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(t); return true } catch { /* not allowed here: try the older way */ }
  try {
    const a = document.createElement('textarea'); a.value = t; a.setAttribute('readonly', ''); a.style.cssText = 'position:fixed;opacity:0;top:0;left:0'
    document.body.appendChild(a); a.select(); const ok = document.execCommand('copy'); a.remove(); return ok
  } catch { return false }
}
/* the Copy link button on a dossier or page: the shell copies the address with the view in it (App.tsx, ww-copy-link) */
export function CopyLink({ className = '' }: { className?: string }) {
  return <button type="button" onClick={() => dispatchEvent(new Event('ww-copy-link'))} className={`tap inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-r2 border border-line px-2.5 text-[12px] text-fg2 transition-colors duration-[120ms] hover:border-line2 hover:text-fg ${className}`}><Link2 size={13} aria-hidden />Copy link</button>
}

export function LevelChip({ level, size = 'sm' }: { level: Level; size?: 'sm' | 'lg' }) {
  const i = ['Normal', 'Watch', 'Elevated', 'Critical'].indexOf(level)
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border border-line2 ${size === 'lg' ? 'px-2.5 py-1 text-[13px]' : 'px-2 py-[2px] text-[12px]'} font-medium`} style={{ color: levelVar(level) }}>
      <span className="flex gap-[3px]" aria-hidden>{[0, 1, 2, 3].map(k => <i key={k} className={`${size === 'lg' ? 'h-2.5 w-[5px]' : 'h-2 w-1'} rounded-[1.5px]`} style={{ background: k <= i && i > 0 ? 'currentColor' : 'var(--line2)' }} />)}</span>
      <span>{levelWord(level)}</span>
    </span>
  )
}

export function Spark({ v, w = 96, h = 24, stroke = 'var(--fg2)', fill = true, band, dot }: { v: (number | null)[]; w?: number; h?: number; stroke?: string; fill?: boolean; band?: [number, number]; dot?: string }) {
  const xs = v.map((x, i) => [i, x] as const).filter(([, x]) => x != null) as [number, number][]
  if (xs.length < 2) return <svg width={w} height={h} />
  const lo = Math.min(...xs.map(p => p[1]), band?.[0] ?? Infinity), hi = Math.max(...xs.map(p => p[1]), band?.[1] ?? -Infinity), r = hi - lo || 1
  const X = (i: number) => (i / (v.length - 1)) * (w - 4) + 2, Y = (y: number) => h - 3 - ((y - lo) / r) * (h - 6)
  const d = xs.map(([i, y], k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)},${Y(y).toFixed(1)}`).join('')
  const lastP = xs[xs.length - 1]
  return (
    <svg width={w} height={h} className="overflow-visible" aria-hidden>
      {band && <rect x={0} width={w} y={Y(band[1])} height={Math.max(1, Y(band[0]) - Y(band[1]))} fill="var(--line)" />}
      {fill && <path d={`${d}L${X(lastP[0])},${h}L${X(xs[0][0])},${h}Z`} fill={stroke} opacity={.1} />}
      <path d={d} fill="none" stroke={stroke} strokeWidth={1.4} strokeLinejoin="round" />
      <circle cx={X(lastP[0])} cy={Y(lastP[1])} r={dot ? 2.4 : 2.2} fill={dot || stroke} />
    </svg>
  )
}

export function Strip({ h, n = 60 }: { h: number[]; n?: number }) {
  const v = h.slice(-n)
  return (
    <span className="grid h-5 w-full gap-px" style={{ gridTemplateColumns: `repeat(${v.length || 1}, minmax(0,1fr))` }}>
      {v.map((z, i) => <i key={i} className="rounded-[1px]" style={{ background: z >= .3 ? zColor(z * 1.6) : 'var(--line)' }} title={`${v.length - i - 1} days ago`} />)}
    </span>
  )
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="border-t border-line px-5 py-4">
      <div className="mb-3 flex items-baseline justify-between gap-3"><h3 className="eyebrow">{title}</h3>{aside && <span className="text-[12px] text-fg3">{aside}</span>}</div>
      {children}
    </section>
  )
}

/* Tabs: arrow keys, Home and End move between them (and choose, as the panels are cheap); only the chosen tab is in the tab order.
   Give panel to name the tabpanel the tabs control (render it with tabPanel()). */
export function Tabs({ tabs, value, onChange, id, panel, sticky, label }: { tabs: [string, string, number?][]; value: string; onChange: (v: string) => void; id: string; panel?: boolean; sticky?: boolean; label?: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const key = (e: KeyboardEvent, i: number) => {
    const n = tabs.length, to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : null
    if (to == null) return
    e.preventDefault(); onChange(tabs[to][0]); refs.current[to]?.focus()
  }
  return (
    <div role="tablist" aria-label={label} className={`flex gap-1 overflow-x-auto px-4 [scrollbar-width:none] ${sticky ? 'sticky top-0 z-[3] border-b border-line bg-s1' : ''}`}>
      {tabs.map(([k, label, n], i) => (
        <button key={k} ref={el => { refs.current[i] = el }} role="tab" id={`${id}-tab-${k}`} aria-selected={value === k} aria-controls={panel ? `${id}-panel` : undefined} tabIndex={value === k ? 0 : -1}
          onClick={() => onChange(k)} onKeyDown={e => key(e, i)}
          className={`relative shrink-0 px-2.5 pb-2.5 pt-2 text-[13.5px] max-[899px]:min-h-11 transition-colors focus-visible:outline-offset-[-2px] ${value === k ? 'text-fg' : 'text-fg3 hover:text-fg2'}`}>
          {label}{n != null && <span className="num ml-1.5 font-mono text-[11px] text-fg3">{n}</span>}
          {value === k && <motion.i layoutId={'tab-' + id} className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-sel" transition={{ duration: .18, ease: [.2, .8, .2, 1] }} />}
        </button>
      ))}
    </div>
  )
}
export const tabPanel = (id: string, value: string) => ({ role: 'tabpanel', id: `${id}-panel`, 'aria-labelledby': `${id}-tab-${value}` } as const)

/* the width of a box, kept as it resizes, so a chart draws at its real size (text in it stays the size it says) */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null), [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current; if (!el) return
    setW(el.clientWidth)
    const ro = new ResizeObserver(() => setW(el.clientWidth)); ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

/* A link to a page of the app: a real address (open in a new tab, copy), and a plain click moves within the app */
export function Lnk({ to, go, className, children, label }: { to: Route; go: (r: Route) => void; className?: string; children: ReactNode; label?: string }) {
  return <a href={routeHref(to)} aria-label={label} className={className} onClick={e => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); go(to) }}>{children}</a>
}

/* A tag under a dossier's name: ink text; a data mark (a level, a lit tripwire, a base change) shows as a small dot before it */
export function Tag({ mark, children }: { mark?: string; children: ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full border border-line2 px-2 py-[2px] text-[11.5px] text-fg2">{mark && <i className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: mark }} aria-hidden />}{children}</span>
}

/* Three facts in a row under a hairline: the value, then what it is */
export function Facts({ items, className = '' }: { items: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={`grid grid-cols-3 border-t border-line pt-2.5 ${className}`}>
      {items.map(([v, label], i) => (
        <div key={i} className={`flex min-w-0 flex-col-reverse ${i ? 'border-l border-line pl-3' : ''}`}>
          <dt className="mt-1 text-[11px] leading-[1.3] text-fg3">{label}</dt>
          <dd className="num text-[17px] font-medium leading-none tracking-[-0.02em] text-fg">{v}</dd>
        </div>))}
    </dl>
  )
}

/* A dossier section: a plain heading (h2 under the dossier's h1) with a quiet aside */
export function Block({ title, aside, children, id }: { title: ReactNode; aside?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section className="border-b border-line px-5 pb-4 pt-3.5" aria-labelledby={id}>
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5"><h2 id={id} className="text-[12.5px] font-semibold leading-[1.2] text-fg">{title}</h2>{aside && <span className="text-[11.5px] text-fg3">{aside}</span>}</div>
      {children}
    </section>
  )
}

/* The closing note of a dossier: dashed, quiet */
export function Note({ children }: { children: ReactNode }) {
  return <div className="mx-5 my-5 rounded-r2 border border-dashed border-line2 px-3 py-2.5 text-[11.5px] leading-[1.5] text-fg3 [&_b]:font-medium [&_b]:text-fg2">{children}</div>
}

export const listAnim = (i: number) => ({ initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { delay: Math.min(i, 8) * .02, duration: .2, ease: [.22, 1, .36, 1] as any } })

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2.5 px-5 py-5" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className="h-3.5 animate-pulse rounded bg-[var(--line)]" style={{ width: `${92 - i * 14}%` }} />)}
    </div>
  )
}

/* A term or number that explains itself: tap it, or focus it from the keyboard, for what it means, where it comes from and (with
   asOf) when it was last updated. The words come from glossary.ts. Hover shows it too; Escape, a second tap or a tap elsewhere
   hides it. Never put one inside another button or link. */
let explainN = 0
export function Explain({ k, asOf, children, className = '' }: { k: TermKey; asOf?: string; children?: ReactNode; className?: string }) {
  const t = term(k), { prefs } = usePrefs()
  const [id] = useState(() => `xp-${++explainN}`)
  const btn = useRef<HTMLButtonElement>(null), tip = useRef<HTMLSpanElement>(null)
  const [hover, setHover] = useState(false), [pinned, setPinned] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number; up: boolean } | null>(null)
  const open = hover || pinned
  const when = asOf ? fmtAsOf(asOf, prefs.tz) : ''
  useLayoutEffect(() => {
    if (!open || !btn.current) { setPos(null); return }
    const place = () => {
      const r = btn.current!.getBoundingClientRect(), w = Math.min(300, innerWidth - 32), h = tip.current?.offsetHeight || 120
      const up = r.bottom + 8 + h > innerHeight - 8 && r.top - 8 - h > 8
      setPos({ left: Math.max(16, Math.min(r.left, innerWidth - 16 - w)), top: up ? r.top - 8 - h : r.bottom + 8, up })
    }
    place()
    addEventListener('resize', place); addEventListener('scroll', place, true)
    return () => { removeEventListener('resize', place); removeEventListener('scroll', place, true) }
  }, [open])
  useEffect(() => {
    if (!pinned) return
    const away = (e: PointerEvent) => { if (!btn.current?.contains(e.target as Node) && !tip.current?.contains(e.target as Node)) { setPinned(false); setHover(false) } }
    addEventListener('pointerdown', away); return () => removeEventListener('pointerdown', away)
  }, [pinned])
  return <>
    <button ref={btn} type="button" aria-describedby={id} aria-expanded={open}
      onClick={() => { setPinned(p => !p); setHover(false) }}
      onFocus={e => { if (e.currentTarget.matches(':focus-visible')) setHover(true) }} onBlur={() => { setHover(false); setPinned(false) }}
      onPointerEnter={e => { if (e.pointerType === 'mouse') setHover(true) }} onPointerLeave={e => { if (e.pointerType === 'mouse') setHover(false) }}
      onKeyDown={e => { if (e.key === 'Escape' && open) { e.preventDefault(); e.stopPropagation(); setHover(false); setPinned(false) } }}
      className={`cursor-help text-left underline decoration-dotted decoration-[color-mix(in_oklab,currentColor_55%,transparent)] underline-offset-[3px] hover:decoration-current ${className}`}>
      {children ?? t.term}
    </button>
    <span id={id} hidden>{t.says} {t.from}{when ? ` Updated ${when}.` : ''}</span>
    {open && createPortal(
      <motion.span ref={tip} aria-hidden initial={{ opacity: 0, y: pos?.up ? 3 : -3 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .14, ease: [.2, .8, .2, 1] }}
        onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}
        className="fixed z-[70] block w-[min(300px,calc(100vw-32px))] rounded-r2 border border-line2 bg-s2 px-3 py-2.5 text-left text-[12.5px] font-normal not-italic leading-[1.45] tracking-normal text-fg2 shadow-[var(--shadow)]"
        style={{ left: pos?.left ?? -9999, top: pos?.top ?? 0, visibility: pos ? 'visible' : 'hidden' }}>
        <b className="block font-sans font-medium text-fg">{t.term}</b>
        <span className="mt-0.5 block font-sans">{t.says}</span>
        <span className="mt-1 block font-sans">{t.from}</span>
        {when && <span className="num mt-1.5 block font-sans text-[11.5px] text-fg2">Updated {when}</span>}
      </motion.span>, document.body)}
  </>
}
/* "13 Nov, 15:14 UTC" for a run time, "2 Nov" for a day */
export function fmtAsOf(s: string, tz: 'utc' | 'local') {
  if (s.length <= 10) return shortDate(s)
  const d = parseGen(s)
  return `${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: tz === 'utc' ? 'UTC' : undefined })}, ${fmtTime(d, tz)}`
}

export function Failed({ what, error }: { what: string; error: unknown }) {
  return <div className="m-5 rounded-xl border border-line bg-raised px-3.5 py-3 text-[13px] text-fg2">Could not load {what}. {error instanceof Error ? error.message : ''} The next run rebuilds it within 30 minutes.</div>
}
