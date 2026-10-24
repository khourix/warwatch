import { createContext, useContext, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X } from 'lucide-react'

/* Settings: a small sheet, not a page (theme, map, label size, time zone, motion). Saved per browser; nothing here changes the data. */

export type Prefs = { theme: 'dark' | 'light' | 'system'; map: 'globe' | 'flat'; labels: number; tz: 'utc' | 'local'; motion: 'on' | 'reduced' }
const DEFAULTS: Prefs = { theme: 'dark', map: 'globe', labels: 1, tz: 'utc', motion: 'on' }
const KEY = 'ww-prefs'

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
      const go = () => { root.dataset.theme = t }
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

export function SettingsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { prefs, set } = usePrefs()
  useEffect(() => { if (!open) return; const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); addEventListener('keydown', k); return () => removeEventListener('keydown', k) }, [open])
  const rows: [string, string, keyof Prefs, [Prefs[keyof Prefs], string][]][] = [
    ['Theme', 'Dark is the default; System follows your device.', 'theme', [['dark', 'Dark'], ['light', 'Light'], ['system', 'System']]],
    ['Map', 'A globe at world view, or a flat map.', 'map', [['globe', 'Globe'], ['flat', 'Flat']]],
    ['Map labels', 'Theatre, city and chokepoint names.', 'labels', [[0.9, 'Small'], [1, 'Medium'], [1.2, 'Large']]],
    ['Times', 'Run times and dates.', 'tz', [['utc', 'UTC'], ['local', 'Your time']]],
    ['Motion', 'Camera flights, pulses and panel slides.', 'motion', [['on', 'On'], ['reduced', 'Reduced']]],
  ]
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-[2px] sm:items-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={onClose}>
          <motion.div role="dialog" aria-modal="true" aria-label="Settings" onClick={e => e.stopPropagation()}
            initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 16, opacity: 0 }} transition={{ type: 'spring', stiffness: 420, damping: 40 }}
            className="w-full max-w-[440px] rounded-t-2xl border border-line2 bg-panel p-5 shadow-[var(--shadow)] sm:rounded-2xl" style={{ paddingBottom: 'max(20px, env(safe-area-inset-bottom))' }}>
            <div className="mb-3 flex items-center justify-between"><h2 className="text-[17px] font-semibold">Settings</h2><button onClick={onClose} aria-label="Close" className="grid h-8 w-8 place-items-center rounded-md text-fg3 hover:bg-hover hover:text-fg"><X size={16} /></button></div>
            {rows.map(([name, hint, k, opts]) => (
              <div key={k} className="border-t border-line py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[13.5px]">{name}</span>
                  <span className="inline-flex rounded-lg border border-line p-0.5 text-[12px]" role="radiogroup" aria-label={name}>
                    {opts.map(([v, label]) => <button key={String(v)} role="radio" aria-checked={prefs[k] === v} onClick={() => set({ [k]: v } as Partial<Prefs>)}
                      className={`rounded-md px-2.5 py-1 ${prefs[k] === v ? 'bg-hover text-fg' : 'text-fg3 hover:text-fg2'}`}>{label}</button>)}
                  </span>
                </div>
                <p className="mt-1 text-[11.5px] text-fg3">{hint}</p>
              </div>
            ))}
            <p className="border-t border-line pt-3 text-[11.5px] text-fg3">Saved in this browser only.</p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
