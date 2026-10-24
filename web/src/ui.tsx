import { motion } from 'motion/react'
import { levelVar, levelWord, zColor, type Level } from './data'
import type { ReactNode } from 'react'

export function Mark({ size = 22, live = true }: { size?: number; live?: boolean }) {
  // The trace-W: a reading that dips, rises and dips again, ending in the live dot.
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <path d="M3 9.5 9.6 24 16 13.6 22.4 24 26.2 15.4" stroke="currentColor" strokeWidth="3.1" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="28" cy="10.4" r="3.1" fill="var(--accent)">{live && <animate attributeName="opacity" values="1;.45;1" dur="2.4s" repeatCount="indefinite" />}</circle>
    </svg>
  )
}
export function Wordmark({ size = 17 }: { size?: number }) {
  return <span className="flex items-center gap-2 text-fg"><Mark size={size + 5} /><span className="font-semibold tracking-[-0.015em]" style={{ fontSize: size }}>WarWatch</span></span>
}

export function LevelChip({ level, size = 'sm' }: { level: Level; size?: 'sm' | 'lg' }) {
  const i = ['Normal', 'Watch', 'Elevated', 'Critical'].indexOf(level)
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border border-line2 ${size === 'lg' ? 'px-2.5 py-1 text-[13px]' : 'px-2 py-[2px] text-[12px]'} font-medium`} style={{ color: levelVar(level) }}>
      <span className="flex gap-[3px]" aria-hidden>{[0, 1, 2, 3].map(k => <i key={k} className={`${size === 'lg' ? 'h-2.5 w-[5px]' : 'h-2 w-1'} rounded-[1.5px]`} style={{ background: k <= i && i > 0 ? 'currentColor' : 'var(--line-2)' }} />)}</span>
      <span>{levelWord(level)}</span>
    </span>
  )
}

export function TellDots({ on, n }: { on: number; n: number }) {
  return (
    <span className="inline-flex items-center gap-[3px]" aria-label={`${on} of ${n} timing tells this week`}>
      {Array.from({ length: n }).map((_, i) => <i key={i} className="h-[6px] w-[6px] rounded-full" style={{ background: i < on ? 'var(--watch)' : 'var(--line-2)' }} />)}
    </span>
  )
}

export function Spark({ v, w = 96, h = 24, stroke = 'var(--fg-2)', fill = true, band }: { v: (number | null)[]; w?: number; h?: number; stroke?: string; fill?: boolean; band?: [number, number] }) {
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
      <circle cx={X(lastP[0])} cy={Y(lastP[1])} r={2.2} fill={stroke} />
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

export function Tabs({ tabs, value, onChange, id }: { tabs: [string, string, number?][]; value: string; onChange: (v: string) => void; id: string }) {
  return (
    <div role="tablist" className="flex gap-1 px-4">
      {tabs.map(([k, label, n]) => (
        <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)} className={`relative px-2.5 pb-2.5 pt-1 text-[13.5px] transition-colors ${value === k ? 'text-fg' : 'text-fg3 hover:text-fg2'}`}>
          {label}{n != null && <span className="num ml-1.5 text-[11.5px] text-fg3">{n}</span>}
          {value === k && <motion.i layoutId={'tab-' + id} className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-accent" transition={{ type: 'spring', stiffness: 520, damping: 40 }} />}
        </button>
      ))}
    </div>
  )
}

export const listAnim = (i: number) => ({ initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { delay: Math.min(i, 12) * .025, duration: .32, ease: [.22, 1, .36, 1] as any } })

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2.5 px-5 py-5" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className="h-3.5 animate-pulse rounded bg-[var(--line)]" style={{ width: `${92 - i * 14}%` }} />)}
    </div>
  )
}

export function Failed({ what, error }: { what: string; error: unknown }) {
  return <div className="m-5 rounded-xl border border-line bg-raised px-3.5 py-3 text-[13px] text-fg2">Could not load {what}. {error instanceof Error ? error.message : ''} The next run rebuilds it within 30 minutes.</div>
}
