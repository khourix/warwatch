import { useEffect, useRef, useState, useCallback, lazy, Suspense } from 'react'
import { motion, AnimatePresence, useDragControls, animate, useMotionValue, MotionConfig } from 'motion/react'
import { Command } from 'cmdk'
import { Globe, Activity, ClipboardCheck, Sun, Moon, Search, MapPin, Satellite, SlidersHorizontal } from 'lucide-react'
import { usePrefs, resolvedTheme, fmtTime, SettingsSheet } from './settings'
// The map library is most of the download, so it loads after the Watch board has painted from its small JSON file.
const MapView = lazy(() => import('./MapView').then(m => ({ default: m.MapView })))
import { TheatreView } from './views'
import { SignalsView, SignalView } from './signals'
import { RecordView } from './record'
import { BaseView } from './ground'
import { Status, Dispatch, Board, Feed, Timeline, TIME_H, type Order, type Kind } from './watch'
import { NotificationBell } from './bell'
import { Wordmark, Mark, Skeleton, Failed } from './ui'
import { useBrief, useLiveMap, useSignals, currentRoute, legacyHash, routeHref, parseGen, levelVar, fmtZ, short, type Brief, type LiveMap, type Route } from './data'

/* 0 phone, 1 wide (900 px: the sheet gives way to columns), 2 roomy (1200 px: "What changed" gets its own column).
   Only crossing a breakpoint re-renders; column widths follow the window in CSS. */
const breakpoint = () => innerWidth >= 1200 ? 2 : innerWidth >= 900 ? 1 : 0
const useBreakpoint = () => {
  const [b, setB] = useState(breakpoint)
  useEffect(() => { const f = () => setB(breakpoint()); addEventListener('resize', f); return () => removeEventListener('resize', f) }, [])
  return b
}
const EASE = [.2, .8, .2, 1] as const
type Nav = [Route['v'], string, typeof Globe][]
const NAV: Nav = [['brief', 'Watch', Globe], ['signals', 'Signals', Activity], ['record', 'Record', ClipboardCheck]]

export default function App() {
  const brief = useBrief(), live = useLiveMap()
  if (brief.isPending) return <div className="grid h-full place-items-center text-fg3"><Mark size={40} /></div>
  if (brief.isError) return <Failed what="the brief" error={brief.error} />
  return <Shell brief={brief.data} live={live.data} />
}

function Shell({ brief, live }: { brief: Brief; live?: LiveMap }) {
  const bp = useBreakpoint(), wide = bp >= 1, roomy = bp >= 2
  /* where the address points; a link from before the switch-over (#iran, #/theatre/iran) moves to its path, an unknown theatre to Watch */
  const fromLocation = useCallback((): Route => {
    const old = legacyHash(location.hash)
    let r = old || currentRoute()
    if (r.v === 'theatre' && !brief.theatres.some(t => t.id === (r as { id: string }).id)) r = { v: 'brief' }
    if (old || new URL(routeHref(r)).pathname !== location.pathname) history.replaceState(null, '', routeHref(r) + location.search)
    return r
  }, [brief])
  const [route, setRoute] = useState<Route>(fromLocation)
  const { prefs, set } = usePrefs()
  const theme = resolvedTheme(prefs)
  const [settings, setSettings] = useState(false)
  const [cmd, setCmd] = useState(false)
  const [day, setDay] = useState<string | null>(null)
  /* the board's order and the feed's kind outlive the columns that show them (the feed moves between columns at 1200 px) */
  const [order, setOrder] = useState<Order>('closest')
  const [kind, setKind] = useState<Kind>('all')
  const panelRef = useRef<HTMLDivElement>(null)

  /* replace: change the address without a new history entry (a theatre's tabs, an unknown theatre) */
  const go = useCallback((r: Route, replace = false) => {
    const href = routeHref(r) + location.search
    if (location.href !== href) history[replace ? 'replaceState' : 'pushState'](null, '', href)
    setRoute(r); if (!replace) panelRef.current?.scrollTo({ top: 0 })
  }, [])
  useEffect(() => {
    const f = () => setRoute(fromLocation())
    addEventListener('popstate', f); addEventListener('hashchange', f)
    return () => { removeEventListener('popstate', f); removeEventListener('hashchange', f) }
  }, [fromLocation])
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !(e.target as HTMLElement).closest('input,textarea,select'))) { e.preventDefault(); setCmd(c => !c) }
      if (e.key === 'Escape' && !cmd && route.v !== 'brief') go({ v: 'brief' })
    }
    addEventListener('keydown', k); return () => removeEventListener('keydown', k)
  }, [cmd, route, go])
  useEffect(() => { document.title = route.v === 'theatre' ? `${brief.theatres.find(t => t.id === route.id)?.name || route.id} · WarWatch` : route.v === 'base' ? `${live?.bases.find(b => b.id === route.id)?.name.split(',')[0] || 'Base'} · WarWatch`
    : route.v === 'brief' ? 'WarWatch' : `${{ signal: 'Signal', signals: 'Signals', record: 'Track record', map: 'Map' }[route.v]} · WarWatch` }, [route, brief, live])

  const toggleTheme = () => set({ theme: theme === 'dark' ? 'light' : 'dark' })
  /* Watch is the home (brief), the map address and an open theatre or base; Signals and Record are pages of their own */
  const dossier = route.v === 'theatre' || route.v === 'base'
  const page = route.v === 'signals' || route.v === 'signal' || route.v === 'record'
  /* the board marks the open theatre, or the theatre of the open base */
  const sel = route.v === 'theatre' ? route.id : route.v === 'base' ? live?.bases.find(b => b.id === route.id)?.theatres[0] ?? null : null
  const navActive = (k: string) => route.v === k || (k === 'brief' && (route.v === 'map' || dossier)) || (k === 'signals' && route.v === 'signal')
  const view = (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div key={route.v === 'theatre' ? 'theatre/' + route.id : JSON.stringify(route)} initial={{ opacity: 0, x: 14 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} transition={{ duration: .34, ease: EASE }}>
        {route.v === 'theatre' && <TheatreView key={route.id} id={route.id} tab={route.tab} brief={brief} live={live} go={go} />}
        {route.v === 'base' && <BaseView key={route.id} id={route.id} brief={brief} go={go} />}
        {route.v === 'signal' && <SignalView key={route.id} id={route.id} brief={brief} go={go} />}
        {route.v === 'signals' && <SignalsView th={route.th} brief={brief} go={go} />}
        {route.v === 'record' && <RecordView brief={brief} go={go} />}
      </motion.div>
    </AnimatePresence>
  )
  const map = (padBottom: number) => <Suspense fallback={null}><MapView brief={brief} live={live} route={route} onPick={go} theme={theme} day={day} flat={prefs.map === 'flat'} onFlat={f => set({ map: f ? 'flat' : 'globe' })} labels={prefs.labels} wide={wide} padBottom={padBottom} /></Suspense>
  const home = <><Dispatch brief={brief} heading={!dossier} /><Board brief={brief} sel={sel} go={go} order={order} setOrder={setOrder} /></>
  const feed = <Feed brief={brief} day={day} setDay={setDay} kind={kind} setKind={setKind} go={go} />

  if (!wide) return (
    <MotionConfig reducedMotion={prefs.motion === 'reduced' ? 'always' : 'user'}>
      <div className="relative h-full overflow-hidden bg-bg text-fg">
        <div className="absolute inset-0">{map(route.v === 'map' ? 200 : Math.round(innerHeight * .55))}</div>
        <PhoneShell route={route} go={go} navActive={navActive} openCmd={() => setCmd(true)} openSettings={() => setSettings(true)} panelRef={panelRef} brief={brief} live={live}>
          {dossier || page ? view : <>{home}{feed}</>}
        </PhoneShell>
        <CommandMenu open={cmd} setOpen={setCmd} go={go} toggleTheme={toggleTheme} openSettings={() => setSettings(true)} brief={brief} live={live} />
        <SettingsSheet open={settings} onClose={() => setSettings(false)} />
      </div>
    </MotionConfig>
  )

  /* Columns: the board on the left, the map, and on the right "What changed" or the open theatre or base. Below 1200 px the feed
     moves under the board, and an open dossier takes the board's place. Every track stays in the grid so widths can ease. */
  const L = dossier && !roomy ? '0px' : roomy ? 'clamp(320px, 27.5vw, 396px)' : 'clamp(340px, 35vw, 396px)'
  const R = dossier ? 'clamp(400px, 33vw, 472px)' : roomy ? 'clamp(320px, 26vw, 372px)' : '0px'
  return (
    <MotionConfig reducedMotion={prefs.motion === 'reduced' ? 'always' : 'user'}>
    <div className="ww-wide grid h-full grid-cols-[64px_minmax(0,1fr)] overflow-hidden bg-bg text-fg">
      <nav aria-label="Pages" className="z-20 flex flex-col items-center gap-1 border-r border-line bg-bg py-3">
        <button onClick={() => go({ v: 'brief' })} aria-label="WarWatch, back to Watch" className="mb-2.5 grid h-9 w-10 place-items-center rounded-r2 text-fg"><Mark size={24} /></button>
        {NAV.map(([k, label, I]) => <RailButton key={k} label={label} on={navActive(k)} onClick={() => go({ v: k } as Route)}><I size={19} strokeWidth={1.6} /></RailButton>)}
        <div className="flex-1" />
        <RailButton label={theme === 'dark' ? 'Switch to light' : 'Switch to dark'} onClick={toggleTheme}>{theme === 'dark' ? <Sun size={17} strokeWidth={1.6} /> : <Moon size={17} strokeWidth={1.6} />}</RailButton>
        <RailButton label="Settings" onClick={() => setSettings(true)}><SlidersHorizontal size={17} strokeWidth={1.6} /></RailButton>
      </nav>
      <div className="grid min-h-0 min-w-0 grid-rows-[52px_minmax(0,1fr)]">
        <header className="flex min-w-0 items-center gap-3.5 border-b border-line px-4">
          <Wordmark mark={false} />
          <i className="h-4 w-px shrink-0 bg-line2" aria-hidden />
          <p className="min-w-0 flex-1 truncate text-[12.5px] text-fg2"><Status brief={brief} /></p>
          <button onClick={() => setCmd(true)} className="flex h-8 w-[min(300px,28vw)] shrink-0 items-center gap-2 rounded-r2 border border-line bg-s1 px-2.5 text-[12.5px] text-fg3 transition-colors duration-[120ms] hover:border-line2">
            <Search size={14} /><span className="min-w-0 flex-1 truncate text-left">Search theatres, bases, signals</span><kbd className="rounded-[3px] border border-line2 px-1 py-0.5 font-mono text-[10.5px] leading-none">⌘K</kbd>
          </button>
          <NotificationBell brief={brief} live={live} go={go} />
          <span className="flex shrink-0 items-center gap-[7px] whitespace-nowrap text-[12px] text-fg2" title={`Built ${brief.generated}. The next run is due within 30 minutes.`}>
            <span className="relative h-1.5 w-1.5 rounded-full bg-ok text-ok live-dot" /><span className="num">Updated {fmtTime(parseGen(brief.generated), prefs.tz)}</span>
          </span>
        </header>
        <div className="relative min-h-0 min-w-0">
          {/* Watch stays mounted under a page, hidden, so the map is built once and keeps its place */}
          <div inert={page} aria-hidden={page || undefined} className={`absolute inset-0 isolate grid ${page ? 'invisible' : ''}`}
            style={{ gridTemplateColumns: `${L} minmax(0,1fr) ${R}`, transition: 'grid-template-columns .34s cubic-bezier(.2,.8,.2,1)' }}>
            <aside aria-label="Dispatch and theatres" className="scroll-thin min-h-0 min-w-0 overflow-y-auto overflow-x-hidden border-r border-line bg-s1">
              {(roomy || !dossier) && <>{home}{!roomy && <div className="border-t border-line">{feed}</div>}</>}
            </aside>
            <div className="relative min-h-0 min-w-0 overflow-hidden" style={{ ['--time-h' as string]: `${TIME_H + 4}px` }}>
              {map(TIME_H)}
              <Timeline brief={brief} day={day} setDay={setDay} />
            </div>
            <aside aria-label={dossier ? 'Details' : 'What changed'} className={`min-h-0 min-w-0 overflow-hidden bg-s1 ${dossier || roomy ? 'border-l border-line' : ''}`}>
              {(dossier || roomy) && <div ref={dossier ? panelRef : undefined} data-scroll className="scroll-thin h-full overflow-y-auto overflow-x-hidden">
                {dossier ? view : feed}
              </div>}
            </aside>
          </div>
          {page && <main ref={panelRef} data-scroll className="scroll-thin absolute inset-0 z-10 overflow-y-auto overflow-x-hidden bg-bg">
            <div className={`mx-auto pb-10 pt-2 ${route.v === 'signals' ? 'max-w-[960px]' : 'max-w-[760px]'}`}>{view}</div>
          </main>}
        </div>
      </div>
      <CommandMenu open={cmd} setOpen={setCmd} go={go} toggleTheme={toggleTheme} openSettings={() => setSettings(true)} brief={brief} live={live} />
      <SettingsSheet open={settings} onClose={() => setSettings(false)} />
    </div>
    </MotionConfig>
  )
}

/* a rail icon, named by a tip on hover and focus; the current page carries an ivory bar */
function RailButton({ label, on, onClick, children }: { label: string; on?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} aria-current={on ? 'page' : undefined}
      className={`group relative grid h-10 w-10 place-items-center rounded-r2 transition-colors duration-[120ms] ${on ? 'bg-s3 text-fg' : 'text-fg3 hover:bg-s2 hover:text-fg'}`}>
      {on && <motion.i layoutId="rail" className="absolute -left-3 bottom-2.5 top-2.5 w-[2px] rounded-[2px] bg-sel" transition={{ duration: .34, ease: EASE }} />}
      {children}
      <span className="pointer-events-none absolute left-12 top-1/2 z-30 -translate-y-1/2 whitespace-nowrap rounded-r1 bg-sel px-[7px] py-[3px] text-[11.5px] font-medium text-selink opacity-0 transition-opacity delay-200 duration-[120ms] group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden>{label}</span>
    </button>
  )
}

/* ---------------------------------------------------------------- Phone: map behind, sheet on top */
function PhoneShell({ route, go, navActive, openCmd, openSettings, children, panelRef, brief, live }: {
  route: Route; go: (r: Route) => void; navActive: (k: string) => boolean; openCmd: () => void; openSettings: () => void
  children: React.ReactNode; panelRef: React.RefObject<HTMLDivElement | null>; brief: Brief; live?: LiveMap
}) {
  const [H, setH] = useState(innerHeight)
  useEffect(() => { const f = () => setH(innerHeight); addEventListener('resize', f); return () => removeEventListener('resize', f) }, [])
  const top = 60, bar = 64, sheetH = H - top - bar
  const snaps = [0, sheetH * .45, sheetH - 132]
  const y = useMotionValue(snaps[1])
  const controls = useDragControls()
  const snapTo = (i: number) => animate(y, snaps[i], { type: 'spring', stiffness: 420, damping: 42 })
  useEffect(() => { if (route.v === 'map') snapTo(2); else if (y.get() > snaps[1] + 10) snapTo(1) }, [route])
  useEffect(() => {   // a fire picked in a list, or a card opened on the map: lower the sheet so the map shows it
    const f = () => snapTo(2)
    addEventListener('ww-focus', f); addEventListener('ww-peek', f)
    return () => { removeEventListener('ww-focus', f); removeEventListener('ww-peek', f) }
  }, [H])
  const round = 'grid h-9 w-9 place-items-center rounded-full border border-line bg-[color-mix(in_oklab,var(--s1)_85%,transparent)] text-fg2 backdrop-blur'
  return (
    <>
      <header className="absolute inset-x-0 top-0 z-30 flex h-[60px] items-center gap-2 px-4" style={{ background: 'linear-gradient(var(--bg), color-mix(in oklab, var(--bg) 0%, transparent))' }}>
        <Wordmark size={16} /><div className="flex-1" />
        <NotificationBell brief={brief} live={live} go={go} phone />
        <button onClick={openCmd} aria-label="Search" className={round}><Search size={16} /></button>
        <button onClick={openSettings} aria-label="Settings" className={round}><SlidersHorizontal size={16} /></button>
      </header>
      <motion.section style={{ y, height: sheetH, top }} drag="y" dragListener={false} dragControls={controls} dragConstraints={{ top: 0, bottom: snaps[2] }} dragElastic={.08}
        onDragEnd={(_, i) => { const p = y.get() + i.velocity.y * .18; let best = 0; snaps.forEach((s, k) => { if (Math.abs(s - p) < Math.abs(snaps[best] - p)) best = k }); snapTo(best) }}
        className="absolute inset-x-0 z-20 flex flex-col overflow-hidden rounded-t-[18px] border border-b-0 border-line bg-s1 shadow-[0_-12px_40px_-12px_rgba(0,0,0,.5)]">
        <div onPointerDown={e => controls.start(e)} className="flex shrink-0 cursor-grab touch-none justify-center pb-1 pt-2.5"><i className="h-1 w-10 rounded-full bg-line2" /></div>
        <div ref={panelRef} data-scroll className="scroll-thin min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-6">{children}</div>
      </motion.section>
      <nav aria-label="Pages" className="absolute inset-x-0 bottom-0 z-30 flex h-16 border-t border-line bg-bg px-2" style={{ paddingBottom: 'env(safe-area-inset-bottom,0px)' }}>
        {NAV.map(([k, label, I]) => (
          <button key={k} onClick={() => go({ v: k } as Route)} aria-current={navActive(k) ? 'page' : undefined} className={`relative flex flex-1 flex-col items-center justify-center gap-1 text-[11px] ${navActive(k) ? 'text-fg' : 'text-fg3'}`}>
            {navActive(k) && <motion.i layoutId="tabbar" className="absolute top-0 h-[2px] w-8 rounded-full bg-sel" />}
            <I size={19} strokeWidth={1.6} />{label}
          </button>
        ))}
      </nav>
    </>
  )
}

/* ---------------------------------------------------------------- ⌘K */
function CommandMenu({ open, setOpen, go, toggleTheme, openSettings, brief, live }: { open: boolean; setOpen: (b: boolean) => void; go: (r: Route) => void; toggleTheme: () => void; openSettings: () => void; brief: Brief; live?: LiveMap }) {
  const sigs = useSignals(open)
  const run = (r: Route) => { setOpen(false); go(r) }
  const region = (id: string) => brief.regions.find(r => r.id === id)?.name || ''
  const item = 'flex cursor-pointer items-center gap-3 rounded-r2 px-2.5 py-2 text-[13.5px] text-fg2 data-[selected=true]:bg-s3 data-[selected=true]:text-fg data-[selected=true]:[&_.text-fg3]:text-fg2'
  const grp = '[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-2 [&_[cmdk-group-heading]]:pt-3'
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-start justify-center bg-black/40 px-4 pt-[12vh] backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={() => setOpen(false)}>
          <motion.div role="dialog" aria-label="Search" initial={{ scale: .98, y: -6, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: .98, opacity: 0 }} transition={{ duration: .18, ease: EASE }} onClick={e => e.stopPropagation()} className="w-[min(600px,92vw)] overflow-hidden rounded-r3 border border-line2 bg-s1 shadow-[var(--shadow)]">
            <Command label="Search WarWatch" loop filter={(v, q) => { const a = v.toLowerCase(), b = q.toLowerCase().trim(); if (!b) return 1; if (a.startsWith(b)) return 1; if (a.includes(' ' + b)) return .9; return a.includes(b) ? .6 : 0 }}>
              <div className="flex items-center gap-2 border-b border-line px-4"><Search size={16} className="text-fg3" /><Command.Input autoFocus placeholder="Search theatres, bases, signals, or type a command" className="h-12 w-full bg-transparent text-[15px] outline-none placeholder:text-fg3 focus-visible:outline-none" /></div>
              <Command.List className="scroll-thin max-h-[52vh] overflow-y-auto p-2">
                <Command.Empty className="px-3 py-6 text-center text-[13px] text-fg3">Nothing matches. Try a country, a base or a source.</Command.Empty>
                <Command.Group heading="Theatres" className={grp}>
                  {brief.theatres.map(t => <Command.Item key={t.id} value={`${t.name} ${region(t.region)} ${(live?.theatres[t.id]?.countries || []).join(' ')} ${t.id}`} onSelect={() => run({ v: 'theatre', id: t.id })} className={item}><MapPin size={15} style={{ color: levelVar(t.level) }} /><span className="flex-1">{short(t.name)}</span><span className="text-[12px] text-fg3">{region(t.region)}</span></Command.Item>)}
                </Command.Group>
                {live && live.bases.length > 0 && <Command.Group heading="Bases" className={grp}>
                  {live.bases.map(b => <Command.Item key={b.id} value={`${b.name} base ${b.side} ${b.id}`} onSelect={() => run({ v: 'base', id: b.id })} className={item}><Satellite size={15} /><span className="flex-1">{b.name}</span></Command.Item>)}
                </Command.Group>}
                {sigs.data && <Command.Group heading="Signals" className={grp}>
                  {sigs.data.signals.filter(s => s.z != null).slice(0, 400).map(s => <Command.Item key={s.id} value={`${s.label} ${s.sub} ${s.id}`} onSelect={() => run({ v: 'signal', id: s.id })} className={item}><Activity size={15} /><span className="min-w-0 flex-1 truncate">{s.label}</span><span className="num font-mono text-[11.5px] text-fg3">{fmtZ(s.z)}</span></Command.Item>)}
                </Command.Group>}
                {sigs.isPending && <Skeleton lines={2} />}
                <Command.Group heading="Go to" className={grp}>
                  <Command.Item onSelect={() => run({ v: 'brief' })} className={item}><Globe size={15} />Watch</Command.Item>
                  <Command.Item onSelect={() => run({ v: 'signals' })} className={item}><Activity size={15} />All signals</Command.Item>
                  <Command.Item onSelect={() => run({ v: 'record' })} className={item}><ClipboardCheck size={15} />Track record</Command.Item>
                  <Command.Item onSelect={() => { setOpen(false); toggleTheme() }} className={item}><Sun size={15} />Switch light or dark</Command.Item>
                  <Command.Item onSelect={() => { setOpen(false); openSettings() }} className={item}><SlidersHorizontal size={15} />Settings</Command.Item>
                </Command.Group>
              </Command.List>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
