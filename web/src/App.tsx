import { useEffect, useRef, useState, useCallback, lazy, Suspense } from 'react'
import { motion, AnimatePresence, useDragControls, animate, useMotionValue, MotionConfig } from 'motion/react'
import { Globe, Activity, ClipboardCheck, Sun, Moon, Search, SlidersHorizontal, Link2, BookOpen, X } from 'lucide-react'
import { usePrefs, SettingsSheet, reducedMotion } from './settings'
import { TheatreView } from './views'
import { BaseView } from './ground'
import { Dispatch, Board, Feed, SinceBlock, Timeline, Status, TIME_H, type Order, type Kind } from './watch'
import { NotificationBell } from './bell'
import { HealthReadout, LateBanner } from './health'
import { ReplayProvider, replayWords, replayHead, replayLive } from './replay'
import { useNotifier } from './follow'
import { FollowPrompt } from './settings'
import { useSinceLastVisit } from './since'
import { Wordmark, Mark, Skeleton, Failed, copyText, Boundary } from './ui'
import { loadLayers, saveLayers, parseLayers, layersParam, isDefault, type Layer, type Layers } from './layers'
import { useBrief, useLiveMap, currentRoute, legacyHash, hashIsLegacy, routeHref, parseGen, shortDate, type Brief, type LiveMap, type Route } from './data'

/* The board paints from brief.json first; the map library (most of the download) and the pages other than Watch load after. */
const MapView = lazy(() => import('./MapView').then(m => ({ default: m.MapView })))
const SignalsView = lazy(() => import('./signals').then(m => ({ default: m.SignalsView })))
const SignalView = lazy(() => import('./signals').then(m => ({ default: m.SignalView })))
const RecordView = lazy(() => import('./record').then(m => ({ default: m.RecordView })))
const GroundView = lazy(() => import('./groundpage').then(m => ({ default: m.GroundView })))
const GlossaryView = lazy(() => import('./glossarypage').then(m => ({ default: m.GlossaryView })))
const CommandMenu = lazy(() => import('./command'))
const Wall = lazy(() => import('./wall'))

/* 0 phone, 1 wide (900 px: the sheet gives way to columns), 2 roomy (1200 px: "What changed" gets its own column).
   Only crossing a breakpoint re-renders; column widths follow the window in CSS. */
const breakpoint = () => innerWidth >= 1200 ? 2 : innerWidth >= 900 ? 1 : 0
const useBreakpoint = () => {
  const [b, setB] = useState(breakpoint)
  useEffect(() => { const f = () => setB(breakpoint()); addEventListener('resize', f); return () => removeEventListener('resize', f) }, [])
  return b
}
const EASE = [.2, .8, .2, 1] as const
/* Ground: a diamond within a diamond (the prototype's mark; lucide has none like it) */
function GroundIcon({ size = 19, strokeWidth = 1.6, className }: { size?: number | string; strokeWidth?: number | string; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin="round" className={className} aria-hidden><path d="M12 3l9 9-9 9-9-9z" /><path d="M12 9l3 3-3 3-3-3z" /></svg>
}
type Nav = [Route['v'], string, (p: { size?: number; strokeWidth?: number }) => React.ReactNode][]
const NAV: Nav = [['brief', 'Watch', Globe], ['signals', 'Signals', Activity], ['ground', 'Ground', GroundIcon], ['record', 'Record', ClipboardCheck], ['glossary', 'Guide', BookOpen]]

/* The view in the address, so a copied link reopens it: the theatre and its tab are the path; on Watch (the home, a theatre, a
   base, the map) the picked day is ?d=2026-11-10 and the map layers, when they differ from the usual set, ?l=bases.fires.
   The address changes in place (replaceState), so these never add steps to Back. */
const onWatch = (r: Route) => r.v === 'brief' || r.v === 'map' || r.v === 'theatre' || r.v === 'base'
const query = () => { try { return new URLSearchParams(location.search) } catch { return new URLSearchParams() } }
function dayFromAddress(brief: Brief): string | null {
  const d = query().get('d'); if (!d || !/^\d{4}-\d{2}-\d{2}$/.test(d)) return null
  /* the timeline's own days (watch.tsx Timeline): the 29 before today; today is live */
  const end = parseGen(brief.generated).getTime()
  return Array.from({ length: 29 }, (_, i) => new Date(end - (29 - i) * 864e5).toISOString().slice(0, 10)).includes(d) ? d : null
}

const Kit = import.meta.env.DEV ? lazy(() => import('./kit')) : null
export default function App() {
  if (Kit && new URLSearchParams(location.search).has('kit')) return <Suspense fallback={null}><Kit /></Suspense>
  return <Main />
}
function Main() {
  const brief = useBrief()
  if (brief.isPending) return <div className="grid h-full place-items-center text-fg3"><Mark size={40} /></div>
  /* a failed refresh keeps the data it has (the late banner says how old it is); only a first load that fails shows the error */
  if (!brief.data) return <Failed what="the brief" error={brief.error} />
  return <Shell brief={brief.data} />
}

/* map/live.json (about 900 KB) is not needed for the board: it is asked for once the board has painted, or at once on a page that
   draws from it (a base, Ground, the map address) */
const needsLive = () => { const r = currentRoute(); return r.v === 'base' || r.v === 'ground' || r.v === 'map' }
function Shell({ brief }: { brief: Brief }) {
  const [liveOn, setLiveOn] = useState(needsLive)
  useEffect(() => { const id = requestAnimationFrame(() => setTimeout(() => setLiveOn(true), 0)); return () => cancelAnimationFrame(id) }, [])
  const live = useLiveMap(liveOn).data
  const bp = useBreakpoint(), wide = bp >= 1, roomy = bp >= 2
  /* where the address points; a link from before the switch-over (#iran, #/theatre/iran) moves to its path, an unknown theatre to Watch */
  const fromLocation = useCallback((): Route => {
    const old = hashIsLegacy() ? legacyHash(location.hash) : null
    let r = old || currentRoute()
    if (r.v === 'theatre' && !brief.theatres.some(t => t.id === (r as { id: string }).id)) r = { v: 'brief' }
    if (old || new URL(routeHref(r)).pathname !== location.pathname) history.replaceState(null, '', new URL(routeHref(r)).pathname + location.search + new URL(routeHref(r)).hash)
    return r
  }, [brief])
  const [route, setRoute] = useState<Route>(fromLocation)
  const { prefs, set, theme } = usePrefs()
  const [settings, setSettings] = useState(false)
  const [cmd, setCmd] = useState(false), [cmdSeen, setCmdSeen] = useState(false)
  /* letters typed after ⌘K before the search field is there (its code loads on the first open) are kept and handed to it */
  const early = useRef('')
  useEffect(() => { if (cmd) setCmdSeen(true) }, [cmd])
  const [day, setDay] = useState<string | null>(() => dayFromAddress(brief))
  const [layers, setLayers] = useState<Layers>(() => parseLayers(query().get('l')) ?? loadLayers())
  const toggleLayer = useCallback((k: Layer) => setLayers(l => { const n = { ...l, [k]: !l[k] }; saveLayers(n); return n }), [])
  /* the board's order and the feed's kind outlive the columns that show them (the feed moves between columns at 1200 px) */
  const [order, setOrder] = useState<Order>(prefs.order)
  useEffect(() => setOrder(prefs.order), [prefs.order])
  const [kind, setKind] = useState<Kind>('key')
  const panelRef = useRef<HTMLDivElement>(null)
  const { since, dismiss: dismissSince } = useSinceLastVisit(brief)
  const [newOnly, setNewOnly] = useState(false)
  const dismiss = useCallback(() => { setNewOnly(false); dismissSince() }, [dismissSince])
  /* the map and the command menu's code load once the board has painted */
  const [mapOn, setMapOn] = useState(false)
  useEffect(() => { const id = requestAnimationFrame(() => setTimeout(() => { setMapOn(true); import('./command').catch(() => { /* a failed fetch shows when the menu opens */ }) }, 0)); return () => cancelAnimationFrame(id) }, [])

  /* replace: change the address without a new history entry (a theatre's tabs, an unknown theatre) */
  const go = useCallback((r: Route, replace = false) => {
    /* ?s=<id> is the signal open on the Signals page: it stays while the page does, and goes when the page is left */
    const sp = new URLSearchParams(location.search); if (r.v !== 'signals') sp.delete('s')
    const qs = sp.toString(), u = new URL(routeHref(r)); u.search = qs ? '?' + qs : ''; const href = u.href   // a glossary term stays the anchor, after the query
    if (location.href !== href) history[replace ? 'replaceState' : 'pushState'](null, '', href)
    setRoute(r); if (!replace) panelRef.current?.scrollTo({ top: 0 })
  }, [])
  /* followed theatres: a notification when fresh data shows a level rise or a new tripwire there (follow.ts); never from a replay */
  useNotifier(brief, go)
  /* keep the day and the layers in the address while Watch shows them */
  useEffect(() => {
    const sp = query(), w = onWatch(route)
    if (w && day) sp.set('d', day); else sp.delete('d')
    if (w && !isDefault(layers)) sp.set('l', layersParam(layers)); else sp.delete('l')
    const qs = sp.toString(), next = location.pathname + (qs ? '?' + qs.replace(/%2E/g, '.') : '') + location.hash
    if (next !== location.pathname + location.search + location.hash) history.replaceState(history.state, '', next)
  }, [route, day, layers])
  /* Copy link: the address, with the layers always named on Watch so the link opens the map as it is here */
  const [toast, setToast] = useState<string | null>(null)
  const copyLink = useCallback(async () => {
    const u = new URL(location.href); if (onWatch(route)) u.searchParams.set('l', layersParam(layers))
    const href = u.href.replace(/%2E/g, '.')
    /* what the link keeps, said for this page: the map layers and a replayed day on Watch, the open signal on Signals */
    const keeps = onWatch(route) ? `, with the same map layers${day ? ` and ${shortDate(day)} replayed` : ''}`
      : route.v === 'signals' && u.searchParams.get('s') ? ', with the same signal open' : route.v === 'glossary' && route.term ? ', at the same term' : ''
    setToast(await copyText(href) ? `Link copied. It opens this ${onWatch(route) ? 'view' : 'page'}${keeps}.` : `This browser did not allow copying. The link is ${href}`)
  }, [route, layers, day])
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), toast.startsWith('Link copied') ? 3000 : 9000); return () => clearTimeout(t) }, [toast])
  useEffect(() => { const f = () => copyLink(); addEventListener('ww-copy-link', f); return () => removeEventListener('ww-copy-link', f) }, [copyLink])

  useEffect(() => {
    const f = () => setRoute(fromLocation())
    addEventListener('popstate', f); addEventListener('hashchange', f)
    return () => { removeEventListener('popstate', f); removeEventListener('hashchange', f) }
  }, [fromLocation])
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !(e.target as HTMLElement).closest('input,textarea,select'))) { e.preventDefault(); setCmd(c => !c) }
      else if (e.key === '?' && !cmd && !e.metaKey && !e.ctrlKey && !(e.target as HTMLElement).closest('input,textarea,select,[contenteditable]')) { e.preventDefault(); go({ v: 'glossary', term: 'read' }) }
      if (e.key === 'Escape' && cmd) { e.preventDefault(); setCmd(false); early.current = ''; return }   // the search closes first
      if (cmd && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && !(e.target as HTMLElement).closest('input,textarea')) {
        const field = document.querySelector<HTMLInputElement>('[cmdk-input]')
        if (field) { field.focus(); return }             // the field is there but not focused yet: the key goes on to it
        early.current += e.key; e.preventDefault(); return
      }
      /* a page that used the Escape first (a panel, a filter, an explainer) prevents it; an open dialog keeps it */
      if (e.key !== 'Escape' || e.defaultPrevented || cmd || document.querySelector('[aria-modal="true"]')) return
      if (day && onWatch(route)) { setDay(null); return }      // a replay goes back to now first
      if (route.v !== 'brief') go({ v: 'brief' })
    }
    addEventListener('keydown', k); return () => removeEventListener('keydown', k)
  }, [cmd, route, go, day])
  useEffect(() => { document.title = route.v === 'theatre' ? `${brief.theatres.find(t => t.id === route.id)?.name || route.id} · WarWatch` : route.v === 'base' ? `${live?.bases.find(b => b.id === route.id)?.name.split(',')[0] || 'Base'} · WarWatch`
    : route.v === 'brief' ? 'WarWatch' : `${{ signal: 'Signal', signals: 'Signals', ground: 'Ground', record: 'Track record', map: 'Map', glossary: 'Guide', wall: 'Wall' }[route.v]} · WarWatch` }, [route, brief, live])

  const toggleTheme = () => set({ theme: theme === 'dark' ? 'light' : 'dark' })
  /* Watch is the home (brief), the map address and an open theatre or base; Signals, Ground, Record and the glossary are pages */
  const dossier = route.v === 'theatre' || route.v === 'base'
  const page = route.v === 'signals' || route.v === 'signal' || route.v === 'record' || route.v === 'ground' || route.v === 'glossary'
  /* the board marks the open theatre, or the theatre of the open base */
  const sel = route.v === 'theatre' ? route.id : route.v === 'base' ? live?.bases.find(b => b.id === route.id)?.theatres[0] ?? null : null
  const navActive = (k: string) => route.v === k || (k === 'brief' && (route.v === 'map' || dossier)) || (k === 'signals' && route.v === 'signal')
  const view = (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.div key={route.v === 'theatre' ? 'theatre/' + route.id : route.v === 'signals' ? 'signals' : JSON.stringify(route)} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} transition={{ duration: .2, ease: EASE }}>
        <Boundary what={route.v === 'brief' || route.v === 'map' ? 'this view' : 'this page'}><Suspense fallback={<Skeleton lines={6} />}>
          {route.v === 'theatre' && <TheatreView key={route.id} id={route.id} tab={route.tab} brief={brief} live={live} go={go} />}
          {route.v === 'base' && <BaseView key={route.id} id={route.id} brief={brief} live={live} go={go} />}
          {route.v === 'signal' && <SignalView key={route.id} id={route.id} brief={brief} go={go} />}
          {route.v === 'signals' && <SignalsView th={route.th} brief={brief} go={go} />}
          {route.v === 'ground' && <GroundView brief={brief} live={live} go={go} />}
          {route.v === 'record' && <RecordView brief={brief} go={go} />}
          {route.v === 'glossary' && <GlossaryView go={go} term={route.term} />}
        </Suspense></Boundary>
      </motion.div>
    </AnimatePresence>
  )
  const map = (padBottom: number) => mapOn && <Boundary what="the map" at={wide ? 'm-5' : 'mx-3 mt-[68px]'}><Suspense fallback={null}><MapView brief={brief} live={live} route={route} onPick={go} theme={theme} day={null} flat={prefs.map === 'flat'} onFlat={f => set({ map: f ? 'flat' : 'globe' })} labels={prefs.labels} wide={wide} padBottom={padBottom} layers={layers} onToggle={toggleLayer} /></Suspense></Boundary>
  /* the dispatch is the page's heading only on the Watch home; a dossier or a page (Signals, Record) has its own h1 */
  /* each part of Watch has its own boundary: one that fails to draw leaves the others working */
  const dispatch = <Boundary what="the dispatch" at="m-3.5"><Dispatch brief={brief} heading={!dossier && !page} /><FirstVisit go={go} /></Boundary>
  const board = <Boundary what="the theatre board" at="m-3.5"><Board brief={brief} sel={sel} go={go} order={order} setOrder={setOrder} /></Boundary>
  const home = <>{dispatch}{board}</>
  const feed = <Boundary what="the feed" at="m-3.5"><Feed brief={brief} day={day} setDay={setDay} kind={kind} setKind={setKind} go={go} since={day ? null : since} dismiss={dismiss} newOnly={newOnly} setNewOnly={setNewOnly} block={wide} /></Boundary>
  /* on phones "since you last looked" sits under the dispatch, above the board; a pick there jumps to the feed it filters */
  const phoneSince = since && !day && <Boundary what="since you last looked" quiet><SinceBlock since={since} dismiss={dismiss} className="mx-3.5 mb-1.5 mt-2"
    newOnly={newOnly} setNewOnly={v => { setDay(null); setNewOnly(v); if (v) requestAnimationFrame(() => document.getElementById('feed')?.scrollIntoView({ block: 'start' })) }} /></Boundary>
  const overlays = <>
    {cmdSeen && <Boundary what="the search" float><Suspense fallback={null}><CommandMenu open={cmd} setOpen={setCmd} early={early} go={go} toggleTheme={toggleTheme} openSettings={() => setSettings(true)} copyLink={copyLink} brief={brief} live={live} /></Suspense></Boundary>}
    <Boundary what="the settings" float><SettingsSheet open={settings} onClose={() => setSettings(false)} go={go} /></Boundary>
    <Boundary what="the follow prompt" quiet><FollowPrompt names={Object.fromEntries(brief.theatres.map(t => [t.id, t.name]))} /></Boundary>
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-[84px] z-[60] flex justify-center px-4 min-[900px]:bottom-6">
      <AnimatePresence>{toast && <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: EASE }}
        className="pointer-events-auto max-w-[min(560px,100%)] break-words rounded-r2 border border-line2 bg-s2 px-3.5 py-2 text-[12.5px] text-fg shadow-[var(--shadow)]">{toast}</motion.p>}</AnimatePresence>
    </div>
  </>

  /* replaying a day: what replays and what does not, and the way back (the timeline has the same button) */
  const replaying = !!day && onWatch(route)
  const back = <button onClick={() => setDay(null)} className="tap min-h-8 shrink-0 rounded-r2 border border-line2 bg-s2 px-2.5 text-[12px] font-medium hover:border-fg3">Back to now</button>
  const banner = replaying && <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-line bg-s2 px-4 py-2 text-[12.5px] leading-[1.4] text-fg">
    <span className="min-w-0 flex-1">{replayWords(day!)}</span>{back}
  </div>
  /* on phones the day and the way back stay at the top of the sheet while it scrolls (sticky, 44 px: --stick puts the sheet's
     other sticky headers under it); what stays live is said once below it */
  const phoneBanner = replaying && <>
    <div role="status" className="sticky top-0 z-[5] flex h-11 items-center gap-3 border-b border-line bg-s2 px-4 text-[12.5px] text-fg">
      <b className="min-w-0 flex-1 truncate font-medium">{replayHead(day!)}</b>{back}
    </div>
    <p className="border-b border-line bg-s2 px-4 pb-2 pt-1.5 text-[11.5px] leading-[1.4] text-fg2">{replayLive}</p>
  </>
  const mc = prefs.motion === 'reduced' ? 'always' : 'user'

  if (route.v === 'wall') return (
    <MotionConfig reducedMotion={mc}>
      <div className="h-full bg-bg"><Boundary what="the wall"><Suspense fallback={<div className="grid h-full place-items-center text-fg3"><Mark size={40} /></div>}><Wall brief={brief} live={live} /></Suspense></Boundary></div>
      {overlays}
    </MotionConfig>
  )

  if (!wide) return (
    <MotionConfig reducedMotion={mc}>
    <ReplayProvider brief={brief} day={replaying ? day : null}>
      <div className="relative h-full overflow-hidden bg-bg text-fg">
        <div className="absolute inset-0">{map(route.v === 'map' ? 200 : Math.round(innerHeight * .55))}</div>
        <PhoneShell route={route} go={go} navActive={navActive} openCmd={() => setCmd(true)} openSettings={() => setSettings(true)} panelRef={panelRef} brief={brief} live={live}>
          <div style={replaying ? { ['--stick' as string]: '44px' } : undefined}>
            <LateBanner brief={brief} />
            {phoneBanner}
            {dossier || page ? view : <>{dispatch}{phoneSince}<Boundary what="the 30-day timeline" at="m-3.5"><Timeline brief={brief} day={day} setDay={setDay} inline /></Boundary>{board}{feed}</>}
          </div>
        </PhoneShell>
        {overlays}
      </div>
    </ReplayProvider>
    </MotionConfig>
  )

  /* Columns: the board on the left, the map, and on the right "What changed" or the open theatre or base. Below 1200 px the feed
     moves under the board, and an open dossier takes the board's place. Every track stays in the grid so widths can ease. */
  const L = dossier && !roomy ? '0px' : roomy ? 'clamp(320px, 27.5vw, 396px)' : 'clamp(340px, 35vw, 396px)'
  const R = dossier ? 'clamp(400px, 33vw, 472px)' : roomy ? 'clamp(320px, 26vw, 372px)' : '0px'
  const icon = 'grid h-8 w-8 shrink-0 place-items-center rounded-r2 text-fg2 transition-colors duration-[120ms] hover:bg-s2 hover:text-fg'
  return (
    <MotionConfig reducedMotion={mc}>
    <ReplayProvider brief={brief} day={replaying ? day : null}>
    <div className="ww-wide grid h-full grid-cols-[72px_minmax(0,1fr)] overflow-hidden bg-bg text-fg">
      <nav aria-label="Pages" className="z-20 flex flex-col items-center gap-1 border-r border-line bg-bg py-3">
        <button onClick={() => go({ v: 'brief' })} aria-label="WarWatch, back to Watch" className="mb-2.5 grid h-9 w-10 place-items-center rounded-r2 text-fg"><Mark size={24} /></button>
        {NAV.map(([k, label, I]) => <RailButton key={k} label={label} on={navActive(k)} onClick={() => go({ v: k } as Route)}><I size={19} strokeWidth={1.6} /></RailButton>)}
        <div className="flex-1" />
        <RailButton label={theme === 'dark' ? 'Light' : 'Dark'} hint={theme === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme'} onClick={toggleTheme}>{theme === 'dark' ? <Sun size={17} strokeWidth={1.6} /> : <Moon size={17} strokeWidth={1.6} />}</RailButton>
        <RailButton label="Settings" onClick={() => setSettings(true)}><SlidersHorizontal size={17} strokeWidth={1.6} /></RailButton>
      </nav>
      <div className="grid min-h-0 min-w-0 grid-rows-[52px_auto_minmax(0,1fr)]">
        <header className="flex min-w-0 items-center gap-3 border-b border-line px-4">
          <Wordmark mark={false} />
          <i className="h-4 w-px shrink-0 bg-line2" aria-hidden />
          <p className="min-w-0 flex-1 truncate text-[12.5px] text-fg2"><Boundary what="the status line" quiet><Status brief={brief} /></Boundary></p>
          <button onClick={() => setCmd(true)} aria-keyshortcuts="Control+K Meta+K /" className="flex h-8 w-[min(300px,26vw)] shrink-0 items-center gap-2 rounded-r2 border border-line bg-s1 px-2.5 text-[12.5px] text-fg2 transition-colors duration-[120ms] hover:border-line2">
            <Search size={14} aria-hidden /><span className="min-w-0 flex-1 truncate text-left">Search theatres, places, signals</span><kbd className="rounded-[3px] border border-line2 px-1 py-0.5 font-mono text-[10.5px] leading-none">⌘K</kbd>
          </button>
          <button onClick={copyLink} aria-label="Copy link to this view" title="Copy link to this view" className={icon}><Link2 size={15} /></button>
          <NotificationBell brief={brief} live={live} go={go} />
          <Boundary what="data health" float><HealthReadout brief={brief} go={go} /></Boundary>
        </header>
        {/* the late notice and the replay line take the auto row when shown; the content always sits in the last row */}
        <div className="row-start-2"><LateBanner brief={brief} />{banner}</div>
        <div className="relative row-start-3 min-h-0 min-w-0">
          {/* Watch stays mounted under a page, hidden, so the map is built once and keeps its place */}
          <div inert={page} aria-hidden={page || undefined} className={`absolute inset-0 isolate grid ${page ? 'invisible' : ''}`}
            style={{ gridTemplateColumns: `${L} minmax(0,1fr) ${R}`, transition: 'grid-template-columns .22s cubic-bezier(.2,.8,.2,1)' }}>
            <aside aria-label="Dispatch and theatres" className="scroll-thin min-h-0 min-w-0 overflow-y-auto overflow-x-hidden border-r border-line bg-s1">
              {(roomy || !dossier) && <>{home}{!roomy && <div className="border-t border-line">{feed}</div>}</>}
            </aside>
            <div className="relative min-h-0 min-w-0 overflow-hidden" style={{ ['--time-h' as string]: `${TIME_H + 4}px` }}>
              {map(TIME_H)}
              <Boundary what="the 30-day timeline" at="absolute inset-x-3.5 bottom-3.5 z-10"><Timeline brief={brief} day={day} setDay={setDay} /></Boundary>
            </div>
            <aside aria-label={dossier ? 'Details' : 'What changed'} className={`min-h-0 min-w-0 overflow-hidden bg-s1 ${dossier || roomy ? 'border-l border-line' : ''}`}>
              {(dossier || roomy) && <div ref={dossier ? panelRef : undefined} data-scroll className="scroll-thin h-full overflow-y-auto overflow-x-hidden">
                {dossier ? view : feed}
              </div>}
            </aside>
          </div>
          {page && <main ref={panelRef} data-scroll className="scroll-thin absolute inset-0 z-10 overflow-y-auto overflow-x-hidden bg-bg">
            <div className={`mx-auto pb-10 pt-2 ${route.v === 'signals' || route.v === 'ground' ? 'max-w-[1440px]' : route.v === 'record' ? 'max-w-[1120px]' : 'max-w-[760px]'}`}>{view}</div>
          </main>}
        </div>
      </div>
      {overlays}
    </div>
    </ReplayProvider>
    </MotionConfig>
  )
}

/* a rail icon, named by a tip on hover and focus; the current page carries an ivory bar */
/* A rail entry: icon over a short label, so nothing on the rail has to be guessed. The box never changes size; only colour moves. */
function RailButton({ label, hint, on, onClick, children }: { label: string; hint?: string; on?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-label={hint ?? label} title={hint} aria-current={on ? 'page' : undefined}
      className={`relative flex h-[50px] w-[60px] flex-col items-center justify-center gap-[3px] rounded-r2 transition-colors duration-[120ms] ${on ? 'bg-s3 text-fg' : 'text-fg2 hover:bg-s2 hover:text-fg'}`}>
      {on && <motion.i layoutId="rail" className="absolute -left-1.5 bottom-3 top-3 w-[2px] rounded-[2px] bg-sel" transition={{ duration: .2, ease: EASE }} />}
      <span className="grid h-5 place-items-center" aria-hidden>{children}</span>
      <span className="text-[10.5px] font-medium leading-none" aria-hidden>{label}</span>
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
  const y = useMotionValue(snaps[route.v === 'map' ? 2 : route.v === 'theatre' || route.v === 'base' ? 1 : 0])
  const controls = useDragControls()
  const snapTo = (i: number) => reducedMotion() ? y.set(snaps[i]) : animate(y, snaps[i], { duration: .22, ease: EASE })
  /* where the sheet rests for each view: the map gets the screen, a theatre or base shares it, the brief and the pages read full
     height with a strip at the top that opens the map */
  const rest = route.v === 'map' ? 2 : route.v === 'theatre' || route.v === 'base' ? 1 : 0
  const [at, setAt] = useState(rest)
  useEffect(() => y.on('change', v => setAt(snaps.reduce((b, s, k) => Math.abs(s - v) < Math.abs(snaps[b] - v) ? k : b, 0))), [H])
  useEffect(() => { snapTo(rest) }, [route.v, (route as { id?: string }).id])
  const mapped = route.v !== 'signals' && route.v !== 'signal' && route.v !== 'record' && route.v !== 'ground' && route.v !== 'glossary'
  useEffect(() => {   // a fire picked in a list, or a card opened on the map: lower the sheet so the map shows it
    const f = () => snapTo(2)
    addEventListener('ww-focus', f); addEventListener('ww-peek', f)
    return () => { removeEventListener('ww-focus', f); removeEventListener('ww-peek', f) }
  }, [H])
  const round = 'relative grid h-9 w-9 shrink-0 place-items-center rounded-full after:absolute after:-inset-[5px] after:content-[\'\'] border border-line bg-[color-mix(in_oklab,var(--s1)_85%,transparent)] text-fg2 backdrop-blur'
  /* the handle: drag it, or tap it (or Enter) to step the sheet between its three heights */
  const step = () => { const cur = y.get(), i = snaps.reduce((b, s, k) => Math.abs(s - cur) < Math.abs(snaps[b] - cur) ? k : b, 0); snapTo(i === 0 ? 1 : i === 1 ? 2 : 0) }
  return (
    <>
      <header className="absolute inset-x-0 top-0 z-30 flex h-[60px] items-center gap-2.5 px-3" style={{ background: 'linear-gradient(var(--bg), color-mix(in oklab, var(--bg) 0%, transparent))' }}>
        <Wordmark size={16} compact /><div className="flex-1" />
        <Boundary what="data health" float><HealthReadout brief={brief} go={go} phone /></Boundary>
        <NotificationBell brief={brief} live={live} go={go} phone />
        <button onClick={openCmd} aria-label="Search" className={round}><Search size={16} /></button>
        <button onClick={openSettings} aria-label="Settings" className={round}><SlidersHorizontal size={16} /></button>
      </header>
      <motion.section style={{ y, height: sheetH, top }} drag="y" dragListener={false} dragControls={controls} dragConstraints={{ top: 0, bottom: snaps[2] }} dragElastic={.08}
        onDragEnd={(_, i) => { const p = y.get() + i.velocity.y * .18; let best = 0; snaps.forEach((s, k) => { if (Math.abs(s - p) < Math.abs(snaps[best] - p)) best = k }); snapTo(best) }}
        className="absolute inset-x-0 z-20 flex flex-col overflow-hidden rounded-t-[18px] border border-b-0 border-line bg-s1 shadow-[0_-12px_40px_-12px_rgba(0,0,0,.5)]">
        <button type="button" aria-label="Move the panel up or down" onPointerDown={e => controls.start(e)} onClick={step} className={`relative flex ${mapped && at === 0 ? 'h-10' : 'h-6'} shrink-0 cursor-grab touch-none items-start justify-center pt-2.5 after:absolute after:inset-x-0 after:-bottom-5 after:top-0 after:content-['']`}><i className="h-1 w-10 rounded-full bg-line2" /></button>
        {mapped && at === 0 && <button type="button" onClick={() => snapTo(2)} className="absolute right-3 top-[7px] z-10 flex h-7 items-center gap-1.5 rounded-full border border-line px-2.5 text-[11.5px] font-medium leading-none text-fg2 transition-colors duration-[120ms] hover:text-fg"><Globe size={13} strokeWidth={1.7} aria-hidden />Open map</button>}
        <div ref={panelRef} data-scroll className="scroll-thin min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-6">{children}</div>
      </motion.section>
      <nav aria-label="Pages" className="absolute inset-x-0 bottom-0 z-30 flex h-16 border-t border-line bg-bg px-2" style={{ paddingBottom: 'env(safe-area-inset-bottom,0px)' }}>
        {NAV.map(([k, label, I]) => (
          <button key={k} onClick={() => go({ v: k } as Route)} aria-current={navActive(k) ? 'page' : undefined} className={`relative flex min-h-11 flex-1 flex-col items-center justify-center gap-1 text-[11px] ${navActive(k) ? 'text-fg' : 'text-fg2'}`}>
            {navActive(k) && <motion.i layoutId="tabbar" className="absolute top-0 h-[2px] w-8 rounded-full bg-sel" transition={{ duration: .2, ease: EASE }} />}
            <I size={19} strokeWidth={1.6} />{label}
          </button>
        ))}
      </nav>
    </>
  )
}

/* a single line under the dispatch on the first visit, pointing to how to read the page; gone for good once closed or followed */
function FirstVisit({ go }: { go: (r: Route) => void }) {
  const [on, setOn] = useState(() => { try { return !localStorage.getItem('ww-hinted') } catch { return false } })
  if (!on) return null
  const done = () => { try { localStorage.setItem('ww-hinted', '1') } catch { /* private mode */ } setOn(false) }
  return (
    <p className="mx-3.5 mb-1.5 flex min-h-9 items-center gap-2 rounded-r2 border border-line px-3 text-[12.5px] text-fg2">
      <span className="min-w-0 flex-1">New here? <button onClick={() => { done(); go({ v: 'glossary', term: 'read' }) }} className="lnk text-fg">How to read WarWatch</button><span className="max-[899px]:hidden">, or press <kbd className="rounded-[3px] border border-line2 px-1 font-mono text-[10.5px]">?</kbd> any time</span></span>
      <button onClick={done} aria-label="Close the tip" className="-mr-1.5 grid h-7 w-7 shrink-0 place-items-center rounded-r1 text-fg3 hover:bg-s2 hover:text-fg"><X size={14} /></button>
    </p>
  )
}
