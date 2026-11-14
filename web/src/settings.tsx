import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X } from 'lucide-react'
import { ROOT, short, type Route } from './data'
import { useFollow, forgetFollows, permission, askPermission, permissionLine, type Permission } from './follow'

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

/* theme: the theme in force, "System" resolved; it follows the device while the page is open (the rail's toggle and the map read it) */
type Ctx = { prefs: Prefs; set: (p: Partial<Prefs>) => void; theme: 'dark' | 'light' }
const PrefsCtx = createContext<Ctx>({ prefs: DEFAULTS, set: () => {}, theme: 'dark' })
export const usePrefs = () => useContext(PrefsCtx)

export function PrefsProvider({ children }: { children: React.ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(load)
  const set = (p: Partial<Prefs>) => setPrefs(old => { const n = { ...old, ...p }; save(n); return n })
  const [sysDark, setSysDark] = useState(systemDark)
  useEffect(() => { const mq = matchMedia('(prefers-color-scheme: dark)'), f = () => setSysDark(mq.matches); f(); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f) }, [])
  const theme: 'dark' | 'light' = prefs.theme === 'system' ? (sysDark ? 'dark' : 'light') : prefs.theme
  useEffect(() => {
    const apply = () => {
      const t = theme, d = document as any, root = document.documentElement
      const go = () => { root.dataset.theme = t; document.querySelector('meta[name=theme-color]')?.setAttribute('content', t === 'dark' ? '#080b11' : '#f2efe7') }
      if (root.dataset.theme !== t && d.startViewTransition && prefs.motion === 'on' && !matchMedia('(prefers-reduced-motion: reduce)').matches) d.startViewTransition(go); else go()
      root.dataset.motion = prefs.motion
    }
    apply()
  }, [theme, prefs.motion])
  return <PrefsCtx.Provider value={{ prefs, set, theme }}>{children}</PrefsCtx.Provider>
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
/* the last element focused outside a dialog: the opener, even when the dialog's own field has taken the focus by the time the
   effect below runs (the command menu's input focuses itself as it mounts) */
let opener: HTMLElement | null = null
if (typeof document !== 'undefined') document.addEventListener('focusin', e => { const t = e.target as HTMLElement; if (t instanceof HTMLElement && !t.closest('[role=dialog]')) opener = t }, true)
export function useDialogFocus(open: boolean, box: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return
    const now = document.activeElement as HTMLElement | null
    const back = now && now !== document.body && !box.current?.contains(now) ? now : opener
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

export function SettingsSheet({ open, onClose, go }: { open: boolean; onClose: () => void; go: (r: Route) => void }) {
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
    forgetFollows()
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
                    className={`min-h-9 pointer-coarse:min-h-11 rounded-[6px] px-2.5 transition-colors duration-[120ms] ${prefs[k] === v ? 'bg-s3 font-medium text-fg' : 'text-fg2 hover:text-fg'}`}>{label}</button>)}
                </span>
              </div>
            ))}
            <div className="border-t border-line py-3"><NotifySwitch /></div>
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line py-3">
              <div className="min-w-[180px] flex-1"><span className="block text-[13.5px] text-fg">Wall</span><span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">Watch in large type for a spare screen, updating itself. Escape leaves it.</span></div>
              <a href={new URL('wall/', ROOT).href} onClick={e => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return; e.preventDefault(); onClose(); go({ v: 'wall' }) }} className="lnk inline-flex min-h-9 pointer-coarse:min-h-11 items-center text-[12.5px]">Open</a>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line py-3">
              <div className="min-w-[180px] flex-1"><span className="block text-[13.5px] text-fg">Classic page</span><span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">The old dashboard stays available until 7 Dec 2026.</span></div>
              <a href={new URL('classic/', ROOT).href} className="lnk inline-flex min-h-9 pointer-coarse:min-h-11 items-center text-[12.5px]">Open</a>
            </div>
            <div className="border-t border-line py-3">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <div className="min-w-[180px] flex-1"><span className="block text-[13.5px] text-fg">What this browser remembers</span><span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">These settings, the theatres you follow and whether to notify, the map layers, your last visit, the read marks on the bell and recent searches. They stay in this browser and are never sent anywhere.</span></div>
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

/* "Notify me": a switch, in settings and on the first follow. The browser is asked for permission only from a press on it. */
export function NotifySwitch({ compact = false }: { compact?: boolean }) {
  const { notify, setNotify, ids } = useFollow()
  const [perm, setPerm] = useState<Permission>(permission)
  const [busy, setBusy] = useState(false)
  const on = notify && perm === 'granted'
  const flip = async () => {
    if (on) { setNotify(false); return }
    if (perm === 'unsupported' || perm === 'denied') { setPerm(permission()); return }
    setBusy(true)
    const p = perm === 'granted' ? 'granted' : await askPermission()
    setBusy(false); setPerm(p)
    setNotify(p === 'granted')
  }
  const line = permissionLine(perm)
  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 flex-1">
          <span id="notify-h" className="block text-[13.5px] text-fg">Notify me</span>
          {!compact && <span className="mt-0.5 block text-[11.5px] leading-[1.4] text-fg2">When a theatre you follow rises to Watch or above, or a tripwire fires there. {ids.length ? `You follow ${ids.length} ${ids.length === 1 ? 'theatre' : 'theatres'}.` : 'Follow a theatre with the pin on its row or its page.'}</span>}
        </div>
        <button role="switch" aria-checked={on} aria-labelledby="notify-h" onClick={flip} disabled={busy}
          className={`relative h-7 w-12 shrink-0 rounded-full border transition-colors duration-[120ms] after:absolute after:-inset-2 after:content-[''] ${on ? 'border-sel bg-sel' : 'border-line2 bg-s3'}`}>
          <i className={`absolute top-[3px] h-5 w-5 rounded-full transition-[left] duration-[150ms] ${on ? 'left-[23px] bg-selink' : 'left-[3px] bg-fg2'}`} aria-hidden />
        </button>
      </div>
      <p className="mt-1.5 text-[11.5px] leading-[1.4] text-fg2">Only while WarWatch is open in a tab, or open from your home screen. A closed page cannot notify.</p>
      {line && <p role="status" className="mt-1 text-[11.5px] leading-[1.4] text-fg">{line}</p>}
    </div>
  )
}

/* The first follow in this browser: what following does, and the notify switch, once */
export function FollowPrompt({ names }: { names: Record<string, string> }) {
  const [id, setId] = useState<string | null>(null)
  const { ids } = useFollow()
  useEffect(() => { const f = (e: Event) => setId((e as CustomEvent<string>).detail); addEventListener('ww-followed', f); return () => removeEventListener('ww-followed', f) }, [])
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => { if (!id) return; requestAnimationFrame(() => box.current?.querySelector<HTMLElement>('[role=switch]')?.focus())
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setId(null) } }
    addEventListener('keydown', k, true); return () => removeEventListener('keydown', k, true) }, [id])
  const name = id ? names[id] || '' : ''
  return (
    <AnimatePresence>
      {id && <motion.div ref={box} role="dialog" aria-labelledby="follow-h" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: [.2, .8, .2, 1] }}
        className="fixed bottom-[84px] left-1/2 z-[55] w-[min(420px,calc(100vw-24px))] -translate-x-1/2 rounded-r3 border border-line2 bg-s1 px-4 pb-3 pt-3 shadow-[var(--shadow)] min-[900px]:bottom-6">
        <div className="flex items-start justify-between gap-3">
          <h2 id="follow-h" className="text-[14px] font-medium text-fg">Following {name ? short(name) : `${ids.length} ${ids.length === 1 ? 'theatre' : 'theatres'}`}</h2>
          <button onClick={() => setId(null)} aria-label="Close" className="-mr-2 -mt-1.5 grid h-9 w-9 place-items-center rounded-r2 text-fg2 hover:bg-s2 hover:text-fg"><X size={15} /></button>
        </div>
        <p className="mb-2.5 mt-0.5 text-[12.5px] leading-[1.45] text-fg2">It sits at the top of the board, in this browser only. You can also be notified when its level rises to Watch or above, or a tripwire fires there.</p>
        <NotifySwitch compact />
      </motion.div>}
    </AnimatePresence>
  )
}
