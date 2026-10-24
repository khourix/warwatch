import { useEffect, useRef, useState, useCallback, lazy, Suspense } from 'react'
import { motion, AnimatePresence, useDragControls, animate, useMotionValue } from 'motion/react'
import { Command } from 'cmdk'
import { Newspaper, Globe2, Rows3, BadgeCheck, Sun, Moon, Search, MapPin, Activity, Satellite } from 'lucide-react'
// The map library is most of the download, so it loads after the Brief has painted from its small JSON file.
const MapView = lazy(() => import('./MapView').then(m => ({ default: m.MapView })))
import { BriefView, TheatreView, SignalsView, RecordView } from './views'
import { BaseView } from './ground'
import { TimeStrip } from './strip'
import { Wordmark, Mark, LevelChip, Skeleton, Failed } from './ui'
import { useBrief, useLiveMap, useSignals, parseHash, routeHash, parseGen, levelVar, fmtZ, type Brief, type LiveMap, type Route } from './data'

function useWide() {
  const [w, setW] = useState(() => innerWidth >= 900)
  useEffect(() => { const f = () => setW(innerWidth >= 900); addEventListener('resize', f); return () => removeEventListener('resize', f) }, [])
  return w
}
const store = { get: (k: string) => { try { return localStorage.getItem(k) } catch { return null } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } } }

export default function App() {
  const brief = useBrief(), live = useLiveMap()
  if (brief.isPending) return <div className="grid h-full place-items-center text-fg3"><Mark size={40} /></div>
  if (brief.isError) return <Failed what="the brief" error={brief.error} />
  return <Shell brief={brief.data} live={live.data} />
}

function Shell({ brief, live }: { brief: Brief; live?: LiveMap }) {
  const wide = useWide()
  const [route, setRoute] = useState<Route>(() => parseHash(location.hash))
  const [theme, setTheme] = useState<'dark' | 'light'>(() => (document.documentElement.dataset.theme as 'dark' | 'light') || 'dark')
  const [cmd, setCmd] = useState(false)
  const [day, setDay] = useState<string | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const now = parseGen(brief.generated)

  const go = useCallback((r: Route) => { if (location.hash !== routeHash(r)) location.hash = routeHash(r); else setRoute(r); panelRef.current?.scrollTo({ top: 0 }) }, [])
  useEffect(() => { const f = () => setRoute(parseHash(location.hash)); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  useEffect(() => { document.documentElement.dataset.theme = theme; store.set('ww-theme', theme) }, [theme])
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !(e.target as HTMLElement).closest('input,textarea,select'))) { e.preventDefault(); setCmd(c => !c) }
      if (e.key === 'Escape' && !cmd && route.v !== 'brief') go({ v: 'brief' })
    }
    addEventListener('keydown', k); return () => removeEventListener('keydown', k)
  }, [cmd, route, go])
  useEffect(() => { document.title = route.v === 'theatre' ? `${brief.theatres.find(t => t.id === route.id)?.name || route.id} · WarWatch` : route.v === 'base' ? `${live?.bases.find(b => b.id === route.id)?.name.split(',')[0] || 'Base'} · WarWatch` : 'WarWatch' }, [route, brief, live])

  const toggleTheme = () => { const n = theme === 'dark' ? 'light' : 'dark'; const d = document as any; if (d.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) d.startViewTransition(() => setTheme(n)); else setTheme(n) }
  const panelOpen = route.v !== 'map'
  const PANEL = wide ? (route.v === 'signals' ? 600 : 460) : 0
  const view = (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div key={JSON.stringify(route)} initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: .26, ease: [.22, 1, .36, 1] }}>
        {route.v === 'brief' && <BriefView brief={brief} go={go} />}
        {route.v === 'theatre' && <TheatreView key={route.id} id={route.id} tab={route.tab} brief={brief} live={live} go={go} />}
        {route.v === 'base' && <BaseView key={route.id} id={route.id} brief={brief} go={go} />}
        {route.v === 'signals' && <SignalsView th={route.th} brief={brief} go={go} />}
        {route.v === 'record' && <RecordView brief={brief} go={go} />}
      </motion.div>
    </AnimatePresence>
  )
  const nav: [Route['v'], string, typeof Newspaper][] = [['brief', 'Brief', Newspaper], ['map', 'Map', Globe2], ['signals', 'Signals', Rows3], ['record', 'Record', BadgeCheck]]
  const navActive = (k: string) => route.v === k || (k === 'brief' && (route.v === 'theatre' || route.v === 'base'))

  return (
    <div className={`relative h-full overflow-hidden bg-bg text-fg ${wide ? 'ww-wide' : ''}`}>
      <div className="absolute inset-0" style={{ left: wide ? 64 : 0 }}>
        <Suspense fallback={null}><MapView brief={brief} live={live} route={route} onPick={go} theme={theme} day={day} padRight={wide && panelOpen ? PANEL + 16 : 0} padBottom={wide ? 0 : Math.round(innerHeight * .55)} /></Suspense>
      </div>

      {wide ? <>
        <TimeStrip brief={brief} day={day} setDay={setDay} go={go} style={{ left: 80, right: (panelOpen ? PANEL + 16 : 0) + 16, bottom: 12 }} />
        <nav aria-label="Pages" className="absolute inset-y-0 left-0 z-20 flex w-16 flex-col items-center gap-1 border-r border-line bg-panel py-3">
          <button onClick={() => go({ v: 'brief' })} aria-label="WarWatch home" className="mb-3 grid h-10 w-10 place-items-center text-fg"><Mark size={26} /></button>
          {nav.map(([k, label, I]) => (
            <button key={k} onClick={() => go({ v: k } as Route)} aria-current={navActive(k) ? 'page' : undefined} className={`group relative flex w-14 flex-col items-center gap-1 rounded-lg py-2 text-[10.5px] transition-colors ${navActive(k) ? 'text-fg' : 'text-fg3 hover:text-fg2'}`}>
              {navActive(k) && <motion.i layoutId="rail" className="absolute inset-0 rounded-lg bg-hover" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
              <I size={18} className="relative" strokeWidth={1.7} /><span className="relative">{label}</span>
            </button>
          ))}
          <div className="flex-1" />
          <button onClick={toggleTheme} aria-label={theme === 'dark' ? 'Switch to light' : 'Switch to dark'} className="grid h-10 w-10 place-items-center rounded-lg text-fg3 hover:bg-hover hover:text-fg">{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</button>
        </nav>
        <header className="pointer-events-none absolute left-16 top-0 z-10 flex items-center gap-3 p-4" style={{ right: panelOpen ? PANEL + 16 : 0 }}>
          <div className="pointer-events-auto"><Wordmark /></div>
          <button onClick={() => setCmd(true)} className="pointer-events-auto ml-4 flex w-[min(380px,40vw)] items-center gap-2 rounded-xl border border-line bg-panel/80 px-3 py-2 text-[13px] text-fg3 shadow-[var(--shadow)] backdrop-blur-md hover:border-line2">
            <Search size={14} /><span className="flex-1 text-left">Search theatres, bases, signals</span><kbd className="rounded border border-line px-1.5 font-mono text-[10.5px]">⌘K</kbd>
          </button>
          <div className="flex-1" />
          <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-line bg-panel/80 px-3 py-1.5 text-[12px] text-fg2 backdrop-blur-md" title={`Built ${brief.generated}. The next run is due within 30 minutes.`}>
            <span className="relative h-1.5 w-1.5 rounded-full bg-accent text-accent live-dot" /><span className="num">Updated {now.toISOString().slice(11, 16)} UTC</span>
          </div>
        </header>
        <AnimatePresence>
          {panelOpen && (
            <motion.aside key="panel" aria-label="Details" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1, width: PANEL }} exit={{ x: 40, opacity: 0 }} transition={{ type: 'spring', stiffness: 380, damping: 40 }}
              className="absolute bottom-3 right-3 top-3 z-20 overflow-hidden rounded-2xl border border-line bg-panel shadow-[var(--shadow)]">
              <div ref={panelRef} className="scroll-thin h-full overflow-y-auto overflow-x-hidden">{view}</div>
            </motion.aside>
          )}
        </AnimatePresence>
      </> : <PhoneShell route={route} go={go} nav={nav} navActive={navActive} openCmd={() => setCmd(true)} toggleTheme={toggleTheme} theme={theme} panelRef={panelRef} brief={brief}>{view}</PhoneShell>}

      <CommandMenu open={cmd} setOpen={setCmd} go={go} toggleTheme={toggleTheme} brief={brief} live={live} />
    </div>
  )
}

/* ---------------------------------------------------------------- Phone: map behind, sheet on top */
function PhoneShell({ route, go, nav, navActive, openCmd, toggleTheme, theme, children, panelRef, brief }: {
  route: Route; go: (r: Route) => void; nav: [Route['v'], string, typeof Newspaper][]; navActive: (k: string) => boolean; openCmd: () => void; toggleTheme: () => void
  theme: string; children: React.ReactNode; panelRef: React.RefObject<HTMLDivElement | null>; brief: Brief
}) {
  const [H, setH] = useState(innerHeight)
  useEffect(() => { const f = () => setH(innerHeight); addEventListener('resize', f); return () => removeEventListener('resize', f) }, [])
  const top = 60, bar = 64, sheetH = H - top - bar
  const snaps = [0, sheetH * .45, sheetH - 132]
  const y = useMotionValue(snaps[1])
  const controls = useDragControls()
  const snapTo = (i: number) => animate(y, snaps[i], { type: 'spring', stiffness: 420, damping: 42 })
  useEffect(() => { if (route.v === 'map') snapTo(2); else if (y.get() > snaps[1] + 10) snapTo(1) }, [route])
  return (
    <>
      <header className="absolute inset-x-0 top-0 z-20 flex h-[60px] items-center gap-2 px-4" style={{ background: 'linear-gradient(var(--bg), color-mix(in oklab, var(--bg) 0%, transparent))' }}>
        <Wordmark size={16} /><div className="flex-1" />
        <button onClick={openCmd} aria-label="Search" className="grid h-9 w-9 place-items-center rounded-full border border-line bg-panel/80 backdrop-blur"><Search size={16} /></button>
        <button onClick={toggleTheme} aria-label={theme === 'dark' ? 'Switch to light' : 'Switch to dark'} className="grid h-9 w-9 place-items-center rounded-full border border-line bg-panel/80 backdrop-blur">{theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}</button>
      </header>
      <motion.section style={{ y, height: sheetH, top }} drag="y" dragListener={false} dragControls={controls} dragConstraints={{ top: 0, bottom: snaps[2] }} dragElastic={.08}
        onDragEnd={(_, i) => { const p = y.get() + i.velocity.y * .18; let best = 0; snaps.forEach((s, k) => { if (Math.abs(s - p) < Math.abs(snaps[best] - p)) best = k }); snapTo(best) }}
        className="absolute inset-x-0 z-20 flex flex-col overflow-hidden rounded-t-[22px] border border-b-0 border-line bg-panel shadow-[0_-12px_40px_-12px_rgba(0,0,0,.5)]">
        <div onPointerDown={e => controls.start(e)} className="flex shrink-0 cursor-grab touch-none justify-center pb-1 pt-2.5"><i className="h-1 w-10 rounded-full bg-[var(--line-2)]" /></div>
        <div ref={panelRef} className="scroll-thin min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-6">{route.v === 'map' ? <MapPeek go={go} brief={brief} /> : children}</div>
      </motion.section>
      <nav aria-label="Pages" className="absolute inset-x-0 bottom-0 z-30 flex h-16 border-t border-line bg-panel px-2" style={{ paddingBottom: 'env(safe-area-inset-bottom,0px)' }}>
        {nav.map(([k, label, I]) => (
          <button key={k} onClick={() => go({ v: k } as Route)} aria-current={navActive(k) ? 'page' : undefined} className={`relative flex flex-1 flex-col items-center justify-center gap-1 text-[11px] ${navActive(k) ? 'text-fg' : 'text-fg3'}`}>
            {navActive(k) && <motion.i layoutId="tabbar" className="absolute top-0 h-[2px] w-8 rounded-full bg-accent" />}
            <I size={19} strokeWidth={1.7} />{label}
          </button>
        ))}
      </nav>
    </>
  )
}
function MapPeek({ go, brief }: { go: (r: Route) => void; brief: Brief }) {
  const up = brief.theatres.filter(t => t.level !== 'Normal' || t.tellsOn)
  return <div className="px-5 pt-1"><div className="eyebrow mb-2">On the map</div>{up.length === 0 && <p className="text-[13px] text-fg3">Every theatre reads quiet.</p>}<div className="flex gap-2 overflow-x-auto pb-1">{up.map(t => <button key={t.id} onClick={() => go({ v: 'theatre', id: t.id })} className="shrink-0 rounded-xl border border-line px-3 py-2 text-left"><div className="text-[13px] font-medium">{t.name}</div><LevelChip level={t.level} /></button>)}</div></div>
}

/* ---------------------------------------------------------------- ⌘K */
function CommandMenu({ open, setOpen, go, toggleTheme, brief, live }: { open: boolean; setOpen: (b: boolean) => void; go: (r: Route) => void; toggleTheme: () => void; brief: Brief; live?: LiveMap }) {
  const sigs = useSignals(open)
  const run = (r: Route) => { setOpen(false); go(r) }
  const region = (id: string) => brief.regions.find(r => r.id === id)?.name || ''
  const item = 'flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-[13.5px] text-fg2 data-[selected=true]:bg-hover data-[selected=true]:text-fg'
  const grp = '[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-2'
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-start justify-center bg-black/40 px-4 pt-[12vh] backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={() => setOpen(false)}>
          <motion.div role="dialog" aria-label="Search" initial={{ scale: .97, y: -6, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: .98, opacity: 0 }} transition={{ duration: .18, ease: [.22, 1, .36, 1] }} onClick={e => e.stopPropagation()} className="w-[min(600px,92vw)] overflow-hidden rounded-2xl border border-line2 bg-panel shadow-[var(--shadow)]">
            <Command label="Search WarWatch" loop filter={(v, q) => { const a = v.toLowerCase(), b = q.toLowerCase().trim(); if (!b) return 1; if (a.startsWith(b)) return 1; if (a.includes(' ' + b)) return .9; return a.includes(b) ? .6 : 0 }}>
              <div className="flex items-center gap-2 border-b border-line px-4"><Search size={16} className="text-fg3" /><Command.Input autoFocus placeholder="Search theatres, bases, signals, or type a command" className="h-12 w-full bg-transparent text-[15px] outline-none placeholder:text-fg3" /></div>
              <Command.List className="scroll-thin max-h-[52vh] overflow-y-auto p-2">
                <Command.Empty className="px-3 py-6 text-center text-[13px] text-fg3">Nothing matches. Try a country, a base or a source.</Command.Empty>
                <Command.Group heading="Theatres" className={grp}>
                  {brief.theatres.map(t => <Command.Item key={t.id} value={`${t.name} ${region(t.region)} ${(live?.theatres[t.id]?.countries || []).join(' ')} ${t.id}`} onSelect={() => run({ v: 'theatre', id: t.id })} className={item}><MapPin size={15} style={{ color: levelVar(t.level) }} /><span className="flex-1">{t.name}</span><span className="text-[12px] text-fg3">{region(t.region)}</span></Command.Item>)}
                </Command.Group>
                {live && live.bases.length > 0 && <Command.Group heading="Bases" className={grp}>
                  {live.bases.map(b => <Command.Item key={b.id} value={`${b.name} base ${b.side} ${b.id}`} onSelect={() => run({ v: 'base', id: b.id })} className={item}><Satellite size={15} /><span className="flex-1">{b.name}</span></Command.Item>)}
                </Command.Group>}
                {sigs.data && <Command.Group heading="Signals" className={grp}>
                  {sigs.data.signals.filter(s => s.z != null).slice(0, 400).map(s => <Command.Item key={s.id} value={`${s.label} ${s.sub} ${s.id}`} onSelect={() => run(brief.theatres.some(t => t.id === s.theatre) ? { v: 'theatre', id: s.theatre, tab: 'signals' } : { v: 'signals' })} className={item}><Activity size={15} /><span className="min-w-0 flex-1 truncate">{s.label}</span><span className="num text-[12px] text-fg3">{fmtZ(s.z)}</span></Command.Item>)}
                </Command.Group>}
                {sigs.isPending && <Skeleton lines={2} />}
                <Command.Group heading="Go to" className={grp}>
                  <Command.Item onSelect={() => run({ v: 'brief' })} className={item}><Newspaper size={15} />Brief</Command.Item>
                  <Command.Item onSelect={() => run({ v: 'signals' })} className={item}><Rows3 size={15} />All signals</Command.Item>
                  <Command.Item onSelect={() => run({ v: 'record' })} className={item}><BadgeCheck size={15} />Track record</Command.Item>
                  <Command.Item onSelect={() => { setOpen(false); toggleTheme() }} className={item}><Sun size={15} />Switch light or dark</Command.Item>
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
