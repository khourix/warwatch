import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X } from 'lucide-react'
import { ROOT } from './data'

/* Settings: a small sheet, not a page (theme, time, units, motion, map, the board's order). Saved in this browser only; nothing
   here changes the data. With storage blocked (a private window) every choice still works, for this visit. */

export type Prefs = { theme: 'dark' | 'light' | 'system'; map: 'globe' | 'flat'; labels: number; tz: 'utc' | 'local'; motion: 'on' | 'reduced'
  order: 'closest' | 'region'; units: 'nautical' | 'metric' }
const DEFAULTS: Prefs = { theme: 'dark', map: 'globe', labels: 1, tz: 'utc', motion: 'on', order: 'closest', units: 'nautical' }
const KEY = 'ww-prefs'
/* everything this app keeps in the browser starts with "ww-": these settings, the theme, the map layers, the last visit, the bell's
   read marks and recent searches */
const PREFIX = 'ww-'

function load(): Prefs {
  try {
    const p = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') }
    const t = localStorage.getItem('ww-theme')     // the theme the inline script in index.html restores before first paint
    if (t === 'light' || t === 'dark' || t === 'system') p.theme = t
    return p
  } catch { return DEFAULTS }
}
function save(p: Prefs) {
  try { localStorage.setItem(KEY, JSON.stringify(p)); localStorage.setItem('ww-theme', p.theme) } catch { /* private mode: the choice lasts this visit */ }
}
/* -> how many items were removed, or null when storage cannot be read */
export function forgetAll(): number | null {
  try {
    const keys = Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).filter((k): k is string => !!k && k.startsWith(PREFIX))
    keys.forEach(k => localStorage.removeItem(k))
    return keys.length
  } catch { return null }
}
const systemDark = () => matchMedia('(prefers-color-scheme: dark)').matches
export const resolvedTheme = (p: Prefs): 'dark' | 'light' => p.theme === 'system' ? (systemDark() ? 'dark' : 'light') : p.theme

type Ctx = { prefs: Prefs; set: (p: Partial<Prefs>) => void }
const PrefsCtx = createContext<Ctx>({ prefs: DEFAULTS, set: () => {} })
export const usePrefs = () => useContext(PrefsCtx)

export function PrefsProvider({ children }: { children: React.ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(load)
  const set = (p: Partial<Prefs>) => setPrefs(old => { const n = { ...old, ...p }; save(n); return n })
  useEffect(() => {
    const apply = () => {
      const t = resolvedTheme(prefs), d = document as any, root = document.documentElement
      const go = () => { root.dataset.theme = t; document.querySelector('meta[name=theme-color]')?.setAttribute('content', t === 'dark' ? '#080b11' : '#f2efe7') }
      if (root.dataset.theme !== t && d.startViewTransition && prefs.motion === 'on' && !matchMedia('(prefers-reduced-motion: reduce)').matches) d.startViewTransition(go); else go()
      root.dataset.motion = prefs.motion
    }
    apply()
    if (prefs.theme !== 'system') return
    const mq = matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [prefs.theme, prefs.motion])
  return <PrefsCtx.Provider value={{ prefs, set }}>{children}</PrefsCtx.Provider>
}

/* "02:38 UTC" or "04:38 local" */
export function fmtTime(d: Date, tz: Prefs['tz']) {
  return tz === 'utc' ? `${d.toISOString().slice(11, 16)} UTC` : `${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })} local`
}
export const reducedMotion = () => document.documentElement.dataset.motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches
/* aircraft and sea figures: as the sources give them (feet, knots, nautical miles) or metric */
export const fmtAlt = (ft: number, u: Prefs['units']) => u === 'metric' ? `${(Math.round(ft * .3048 / 50) * 50).toLocaleString('en')} m` : `${(Math.round(ft / 100) * 100).toLocaleString('en')} ft`
export const fmtSpeed = (kt: number, u: Prefs['units']) => u === 'metric' ? `${Math.round(kt * 1.852)} km/h` : `${Math.round(kt)} kt`
export const fmtDist = (nm: number, u: Prefs['units']) => u === 'metric' ? `${Math.round(nm * 1.852 / 10) * 10} km` : `${nm} nm`

/* keep Tab inside an open dialog, and give focus back to what opened it when it closes */
export function useDialogFocus(open: boolean, box: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return
    const back = document.activeElement as HTMLElement | null
    const f = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !box.current) return
      const els = Array.from(box.current.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input, [tabindex]:not([tabindex="-1"])')).filter(x => x.offsetParent !== null)
      if (!els.length) return
      const a = els[0], z = els[els.length - 1]
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus() } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus() }
    }
    addEventListener('keydown', f)
    return () => { removeEventListener('keydown', f); if (back?.isConnected) back.focus() }
  }, [open])
}

export function SettingsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { prefs, set } = usePrefs()
  const box = useRef<HTMLDivElement>(null), first = useRef<HTMLButtonElement>(null)
  const [cleared, setCleared] = useState<string | null>(null), [confirm, setConfirm] = useState(false)
  useEffect(() => { if (!open) return; setCleared(null); setConfirm(false); const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); onClose() } }; addEventListener('keydown', k); return () => removeEventListener('keydown', k) }, [open])
  useDialogFocus(open, box)
  useEffect(() => { if (open) requestAnimationFrame(() => first.current?.focus()) }, [open])
  const rows: [string, string, keyof Prefs, [Prefs[keyof Prefs], string][]][] = [
    ['Theme', 'Dark is the default. System follows your device.', 'theme', [['dark', 'Dark'], ['light', 'Light'], ['system', 'System']]],
    ['Times', 'Run times and dates.', 'tz', [['utc', 'UTC'], ['local', 'Your time']]],
    ['Units', 'Aircraft height and speed, and distances at sea.', 'units', [['nautical', 'ft, kt, nm'], ['metric', 'm, km/h, km']]],
    ['Motion', 'Panel slides, camera flights and number changes. Reduced is always on when your device asks for less motion.', 'motion', [['on', 'On'], ['reduced', 'Reduced']]],
    ['Theatre board', 'The order the board opens in.', 'order', [['closest', 'Closest to Watch'], ['region', 'By region']]],
    ['Map', 'A globe at world view, or a flat map.', 'map', [['globe', 'Globe'], ['flat', 'Flat']]],
    ['Map labels', 'Theatre, city and strait names.', 'labels', [[0.9, 'Small'], [1, 'Medium'], [1.2, 'Large']]],
  ]
  const forget = () => {
    const n = forgetAll()
    setConfirm(false)
    setCleared(n == null ? 'This browser does not let the page keep anything, so there is nothing to clear.' : n === 0 ? 'There was nothing to clear.' : `Cleared ${n} ${n === 1 ? 'item' : 'items'}. The page now reloads with nothing remembered.`)
    if (n) setTimeout(() => location.reload(), 1200)
  }
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-[2px] sm:items-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={onClose}>
          <motion.div ref={box} role="dialog" aria-modal="true" aria-labelledby="set-h" onClick={e => e.stopPropagation()}
            initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 16, opacity: 0 }} transition={{ duration: .2, ease: [.2, .8, .2, 1] }}
            className="scroll-thin max-h-[92dvh] w-full max-w-[520px] overflow-y-auto rounded-t-2xl border border-line2 bg-s1 px-5 pt-4 shadow-[var(--shadow)] sm:rounded-r3" style={{ paddingBottom: 'max(20px, env(safe-area-inset-bottom))' }}>
            <div className="mb-1 flex items-center justify-between"><h2 id="set-h" className="text-[17px] font-semibold">Settings</h2><button ref={first} onClick={onClose} aria-label="Close settings" className="-mr-2 grid h-11 w-11 place-items-center rounded-r2 text-fg2 hover:bg-s2 hover:text-fg"><X size={17} /></button></div>
            {rows.map(([name, hint, k, opts]) => (
              <div key={k} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line py-3">
                <div className="min-w-[180px] flex-1"><span id={`set-${k}`} className="block text-[13.5px] text-fg">{name}</span><span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">{hint}</span></div>
                <span className="inline-flex shrink-0 rounded-r2 border border-line p-0.5 text-[12.5px]" role="radiogroup" aria-labelledby={`set-${k}`}
                  onKeyDown={e => { const i = opts.findIndex(o => o[0] === prefs[k]); const to = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? (i + 1) % opts.length : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? (i - 1 + opts.length) % opts.length : null
                    if (to == null) return; e.preventDefault(); set({ [k]: opts[to][0] } as Partial<Prefs>); (e.currentTarget.children[to] as HTMLElement)?.focus() }}>
                  {opts.map(([v, label]) => <button key={String(v)} role="radio" aria-checked={prefs[k] === v} tabIndex={prefs[k] === v ? 0 : -1} onClick={() => set({ [k]: v } as Partial<Prefs>)}
                    className={`min-h-9 rounded-[6px] px-2.5 transition-colors duration-[120ms] ${prefs[k] === v ? 'bg-s3 font-medium text-fg' : 'text-fg2 hover:text-fg'}`}>{label}</button>)}
                </span>
              </div>
            ))}
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line py-3">
              <div className="min-w-[180px] flex-1"><span className="block text-[13.5px] text-fg">Classic page</span><span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">The old dashboard stays available until 7 Dec 2026.</span></div>
              <a href={new URL('classic/', ROOT).href} className="lnk inline-flex min-h-9 items-center text-[12.5px]">Open</a>
            </div>
            <div className="border-t border-line py-3">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <div className="min-w-[180px] flex-1"><span className="block text-[13.5px] text-fg">What this browser remembers</span><span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">These settings, the map layers, your last visit, the read marks on the bell and recent searches. They stay in this browser and are never sent anywhere.</span></div>
                {confirm ? <span className="flex gap-1.5"><button onClick={() => setConfirm(false)} className="min-h-9 rounded-r2 border border-line px-2.5 text-[12.5px] text-fg2 hover:text-fg">Keep</button>
                  <button onClick={forget} className="min-h-9 rounded-r2 border border-sel bg-sel px-2.5 text-[12.5px] font-medium text-selink">Clear it all</button></span>
                  : <button onClick={() => setConfirm(true)} className="min-h-9 rounded-r2 border border-line px-2.5 text-[12.5px] text-fg hover:border-line2">Clear</button>}
              </div>
              <p role="status" className="mt-1.5 text-[11.5px] text-fg2 empty:hidden">{cleared || ''}</p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
