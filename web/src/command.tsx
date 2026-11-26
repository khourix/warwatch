import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Command } from 'cmdk'
import { Globe, Activity, ClipboardCheck, Sun, SlidersHorizontal, Search, Satellite, BookOpen, Link2, History, CornerDownLeft, Monitor, MapPin, Newspaper } from 'lucide-react'
import { useSignals, short, baseState, fmtZ, levelWord, wholeScore, type Brief, type LiveMap, type Route } from './data'
import { TERMS, ORDER as TERM_ORDER, type TermKey } from './glossary'
import { useDialogFocus } from './settings'
import { Skeleton } from './ui'
import { focusOnMap } from './sat'
import { gradeAll, GRADE_WORD } from './grade'

/* The command menu (⌘K, Ctrl+K or /): pages and actions first, then what was picked lately, theatres, bases, signals and glossary
   terms. Typing ranks a name that starts with the words first, then a word inside it. Arrow keys move, Enter opens, Escape closes.
   Recent picks are kept in this browser ("ww-recent"); with storage blocked the list simply stays empty. */

type Pick = { k: 'theatre' | 'base' | 'signal' | 'term'; id: string; label: string }
const RECENT = 'ww-recent'
const loadRecent = (): Pick[] => { try { const x = JSON.parse(localStorage.getItem(RECENT) || '[]'); return Array.isArray(x) ? x.filter(p => p && typeof p.id === 'string' && typeof p.label === 'string').slice(0, 5) : [] } catch { return [] } }
const saveRecent = (p: Pick) => { try { localStorage.setItem(RECENT, JSON.stringify([p, ...loadRecent().filter(x => !(x.k === p.k && x.id === p.id))].slice(0, 5))) } catch { /* private mode: nothing kept */ } }
const EASE = [.2, .8, .2, 1] as const
/* Ground: a diamond within a diamond (the rail's mark) */
const GroundIcon = ({ size = 15 }: { size?: number }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinejoin="round" aria-hidden><path d="M12 3l9 9-9 9-9-9z" /><path d="M12 9l3 3-3 3-3-3z" /></svg>
const CHANGED = ['out', 'in', 'changed']
const SIG_MAX = 40
const BASE_MAX = 12
/* Matching is done here, not by cmdk (its filter scores every item on every key): each searchable thing has its words lowercased
   once, and a query ranks it 4 when the name starts with the query, 3 when a word in it does, 2 when the query is inside it, and 1
   when every word of the query is somewhere in it ("crisiswatch south china" finds "CrisisWatch rating, South China Sea region"). */
const rank = (hay: string, q: string, words: string[]) => hay.startsWith(q) ? 4 : hay.includes(' ' + q) || hay.includes('_' + q) ? 3 : hay.includes(q) ? 2
  : words.length > 1 && words.every(x => hay.includes(x)) ? 1 : 0
type Hit<T> = { r: number; x: T }
function search<T>(index: { hay: string; x: T }[], q: string, max = Infinity, tie: (a: T, b: T) => number = () => 0): T[] {
  if (!q) return index.map(i => i.x)
  const words = q.split(/\s+/).filter(Boolean), out: Hit<T>[] = []
  for (const i of index) { const r = rank(i.hay, q, words); if (r) out.push({ r, x: i.x }) }
  return out.sort((a, b) => b.r - a.r || tie(a.x, b.x)).slice(0, max).map(h => h.x)
}

/* the backdrop dims without a blur: a blur over the whole window is redrawn on every key and made typing slow (A14) */
export default function CommandMenu({ open, setOpen, go, toggleTheme, openSettings, copyLink, brief, live, early }: {
  early?: React.RefObject<string>; open: boolean; setOpen: (b: boolean) => void; go: (r: Route) => void; toggleTheme: () => void; openSettings: () => void; copyLink: () => void; brief: Brief; live?: LiveMap }) {
  const sigs = useSignals(open)
  const [q, setQ] = useState('')
  const [recent, setRecent] = useState<Pick[]>(loadRecent)
  const box = useRef<HTMLDivElement>(null)
  useDialogFocus(open, box)
  /* the field takes the focus as the menu opens (autoFocus alone loses it to the motion mount), so typing and Enter go straight to it */
  useEffect(() => { if (!open) return; let n = 0, id = 0; const f = () => { const i = box.current?.querySelector<HTMLInputElement>('[cmdk-input]'); if (i) i.focus(); else if (n++ < 20) id = requestAnimationFrame(f) }; id = requestAnimationFrame(f); return () => cancelAnimationFrame(id) }, [open])
  /* the field is emptied when the menu closes, not when it opens, so keys typed at once after ⌘K are kept */
  useEffect(() => { if (open) { setRecent(loadRecent()); if (early?.current) { const k = early.current; early.current = ''; setQ(x => k + x) } } else setQ('') }, [open])
  const typed = q.trim().length > 0
  /* the lists follow the query deferred, so the field answers each key at once; every signal (921) can be found by its name,
     source or id, from two letters, at most SIG_MAX shown, best first */
  const dq = useDeferredValue(q.trim().toLowerCase())
  const sigIndex = useMemo(() => (sigs.data?.signals || []).map(x => ({ hay: `${x.label} ${x.sub} ${x.id}`.toLowerCase(), x })), [sigs.data])
  const sigHits = useMemo(() => dq.length < 2 ? [] : search(sigIndex, dq, SIG_MAX, (a, b) => Math.abs(b.z ?? 0) - Math.abs(a.z ?? 0)), [dq, sigIndex])
  const run = (r: Route, pick?: Pick) => { if (pick) saveRecent(pick); setOpen(false); go(r) }
  const openTerm = (k: TermKey) => {
    run({ v: 'glossary', term: k }, { k: 'term', id: k, label: TERMS[k].term })
  }
  const region = (id: string) => brief.regions.find(r => r.id === id)?.name || ''
  const theatreIndex = useMemo(() => [...brief.theatres].sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
    .map(t => ({ hay: `${t.name} ${region(t.region)} ${(live?.theatres[t.id]?.countries || []).join(' ')} ${t.id}`.toLowerCase(), x: t })), [brief, live])
  const theatres = useMemo(() => search(theatreIndex, dq), [theatreIndex, dq])
  /* before typing: the bases that changed on radar; once typing: any base that matches, at most BASE_MAX */
  const baseIndex = useMemo(() => (live?.bases || []).map(b => ({ hay: `${b.name} base ${b.side} ${b.id}`.toLowerCase(), x: b })), [live])
  const bases = useMemo(() => dq ? search(baseIndex, dq, BASE_MAX) : baseIndex.map(i => i.x).filter(b => CHANGED.includes(b.state)).slice(0, 5), [baseIndex, dq])
  /* places (chokepoints and cities) and news reports: picking one opens its theatre and flies the map to it */
  type Place = { name: string; ll: [number, number]; theatre: string; kind: 'Chokepoint' | 'City' }
  const placeIndex = useMemo(() => [...(live?.chokepoints || []).map(c => ({ ...c, kind: 'Chokepoint' as const })), ...(live?.cities || []).map(c => ({ ...c, kind: 'City' as const }))]
    .map(x => ({ hay: `${x.name} ${x.kind}`.toLowerCase(), x: x as Place })), [live])
  const places = useMemo(() => dq.length >= 2 ? search(placeIndex, dq, 8) : [], [placeIndex, dq])
  const grades = useMemo(() => gradeAll(live?.incidents || []), [live])
  const repIndex = useMemo(() => (live?.incidents || []).filter(x => x.t && x.ll).map(x => ({ hay: `${x.t} ${x.loc || ''} ${x.src || ''}`.toLowerCase(), x })), [live])
  const reports = useMemo(() => dq.length >= 3 ? search(repIndex, dq, 6, (a, b) => (b.d || '').localeCompare(a.d || '')) : [], [repIndex, dq])
  const flyTo = (ll: [number, number], theatre: string | undefined, tab?: string) => {
    setOpen(false)
    if (theatre && brief.theatres.some(t => t.id === theatre)) go({ v: 'theatre', id: theatre, tab }); else go({ v: 'map' })
    setTimeout(() => focusOnMap({ kind: 'place', ll, zoom: 7 }), 350)
  }
  const termIndex = useMemo(() => TERM_ORDER.map(k => ({ hay: `${TERMS[k].term} glossary term`.toLowerCase(), x: k })), [])
  const terms = useMemo(() => dq ? search(termIndex, dq, 12) : [], [termIndex, dq])
  type Act = { v: string; on: () => void; node: React.ReactNode }
  const acts: Act[] = [
    { v: 'Watch home board map', on: () => run({ v: 'brief' }), node: <><Globe size={15} aria-hidden />Watch</> },
    { v: 'Signals all signals', on: () => run({ v: 'signals' }), node: <><Activity size={15} aria-hidden />Signals</> },
    { v: 'Ground bases fires heat chokepoints', on: () => run({ v: 'ground' }), node: <><GroundIcon />Ground<span className="ml-auto text-[12px] text-fg2">bases, heat and chokepoints</span></> },
    { v: 'Record track record model data health', on: () => run({ v: 'record' }), node: <><ClipboardCheck size={15} aria-hidden />Record<span className="ml-auto text-[12px] text-fg2">the model's test, data health</span></> },
    { v: 'Guide how to read glossary terms words meaning sources credits', on: () => run({ v: 'glossary' }), node: <><BookOpen size={15} aria-hidden />Guide<span className="ml-auto text-[12px] text-fg2">how to read it, terms, sources</span></> },
    { v: 'Wall mode spare screen full screen monitor', on: () => run({ v: 'wall' }), node: <><Monitor size={15} aria-hidden />Wall<span className="ml-auto text-[12px] text-fg2 max-[459px]:hidden">Watch for a spare screen</span></> },
    { v: 'Copy link to this view share', on: () => { setOpen(false); copyLink() }, node: <><Link2 size={15} aria-hidden />Copy link to this view</> },
    { v: 'Switch light or dark theme', on: () => { setOpen(false); toggleTheme() }, node: <><Sun size={15} aria-hidden />Switch light or dark</> },
    { v: 'Settings preferences', on: () => { setOpen(false); openSettings() }, node: <><SlidersHorizontal size={15} aria-hidden />Settings</> },
  ]
  const actHits = search(acts.map(a => ({ hay: a.v.toLowerCase(), x: a })), dq)
  /* the matching is ours, so the first item is selected here each time the results change: Enter opens the best match */
  const first = (actHits[0] && actHits[0].v) || (!typed && recent[0] && `recent ${recent[0].label} ${recent[0].k} ${recent[0].id}`) || (theatres[0] && `theatre ${theatres[0].id}`)
    || (places[0] && `place ${places[0].name}`) || (bases[0] && `base ${bases[0].id}`) || (sigHits[0] && `signal ${sigHits[0].id}`) || (reports[0] && `report ${reports[0].t}`) || (terms[0] && `term ${terms[0]}`) || ''
  const [sel, setSel] = useState('')
  useEffect(() => setSel(first), [first, dq])
  const pickRoute = (p: Pick): Route => p.k === 'theatre' ? { v: 'theatre', id: p.id } : p.k === 'base' ? { v: 'base', id: p.id } : p.k === 'signal' ? { v: 'signal', id: p.id } : { v: 'glossary', term: p.id }
  const item = 'flex min-h-11 cursor-pointer items-center gap-3 rounded-r2 px-2.5 py-2 text-[13.5px] text-fg2 data-[selected=true]:bg-s3 data-[selected=true]:text-fg'
  const side = 'num shrink-0 text-[12px] text-fg2'
  const grp = '[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:!text-fg2 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-3'
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-start justify-center bg-black/50 px-3 pt-[10vh] max-[599px]:pt-3" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={() => setOpen(false)}>
          <motion.div ref={box} role="dialog" aria-modal="true" aria-label="Search and go to" initial={{ y: -6, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: EASE }} onClick={e => e.stopPropagation()}
            className="w-[min(640px,calc(100vw-24px))] overflow-hidden rounded-r3 border border-line2 bg-s1 shadow-[var(--shadow)]">
            <Command label="Search WarWatch" loop shouldFilter={false} value={sel} onValueChange={setSel}>
              <div className="flex items-center gap-2.5 border-b border-line px-4">
                <Search size={16} className="shrink-0 text-fg2" aria-hidden />
                <Command.Input autoFocus value={q} onValueChange={setQ} placeholder="Go to a theatre, place, base, signal or report" className="h-12 min-w-0 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-fg2" />
                <kbd className="shrink-0 rounded-[4px] border border-line2 px-1.5 py-0.5 font-mono text-[10.5px] leading-none text-fg2">esc</kbd>
              </div>
              <Command.List className="scroll-thin max-h-[min(56vh,520px)] overflow-y-auto p-2 max-[599px]:max-h-[calc(100dvh-140px)]">
                {dq && !actHits.length && !theatres.length && !places.length && !bases.length && !sigHits.length && !reports.length && !terms.length && !(dq.length >= 2 && sigs.isPending) &&
                  <div className="px-3 py-7 text-center text-[13px] leading-[1.5] text-fg2" role="status">Nothing matches “{q.trim()}”.<br />Try a country, a base, a source such as NOTAM, or a word such as tripwire.</div>}
                {actHits.length > 0 && <Command.Group heading="Go to" className={grp}>
                  {actHits.map(a => <Command.Item key={a.v} value={a.v} onSelect={a.on} className={item}>{a.node}</Command.Item>)}
                </Command.Group>}
                {!typed && recent.length > 0 && <Command.Group heading="Recent" className={grp}>
                  {recent.map(p => <Command.Item key={'r' + p.k + p.id} value={`recent ${p.label} ${p.k} ${p.id}`} onSelect={() => p.k === 'term' ? openTerm(p.id as TermKey) : run(pickRoute(p), p)} className={item}><History size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{p.label}</span><span className="text-[12px] text-fg2">{({ theatre: 'Theatre', base: 'Base', signal: 'Signal', term: 'Term' })[p.k]}</span></Command.Item>)}
                </Command.Group>}
                {theatres.length > 0 && <Command.Group heading="Theatres" className={grp}>
                  {theatres.map(t => <Command.Item key={t.id} value={`theatre ${t.id}`} onSelect={() => run({ v: 'theatre', id: t.id }, { k: 'theatre', id: t.id, label: short(t.name) })} className={item}>
                    <Globe size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{short(t.name)}<span className="ml-2 text-[12px] text-fg2">{region(t.region)}</span></span>
                    <span className={side}>{levelWord(t.level)}{t.score != null ? `, reading ${wholeScore(t.score)}` : ''}</span></Command.Item>)}
                </Command.Group>}
                {places.length > 0 && <Command.Group heading="Places" className={grp}>
                  {places.map(p => <Command.Item key={p.kind + p.name} value={`place ${p.name}`} onSelect={() => flyTo(p.ll, p.theatre)} className={item}>
                    <MapPin size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{p.name}</span><span className="shrink-0 text-[12px] text-fg2">{p.kind}</span></Command.Item>)}
                </Command.Group>}
                {bases.length > 0 && <Command.Group heading={typed ? 'Bases' : 'Bases that changed on radar'} className={grp}>
                  {bases.map(b => <Command.Item key={b.id} value={`base ${b.id}`} onSelect={() => run({ v: 'base', id: b.id }, { k: 'base', id: b.id, label: b.name.split(',')[0] })} className={item}>
                    <Satellite size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{b.name}</span><span className="shrink-0 text-[12px] text-fg2 max-[459px]:hidden">{baseState(b.state)[0]}</span></Command.Item>)}
                </Command.Group>}
                {sigHits.length > 0 && <Command.Group heading="Signals" className={grp}>
                  {sigHits.map(s => <Command.Item key={s.id} value={`signal ${s.id}`} onSelect={() => run({ v: 'signal', id: s.id }, { k: 'signal', id: s.id, label: s.label })} className={item}>
                    <Activity size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{s.label}</span><span className="num shrink-0 font-mono text-[11.5px] text-fg2">{s.z == null ? 'not scored' : fmtZ(s.z)}</span></Command.Item>)}
                </Command.Group>}
                {dq.length >= 2 && sigs.isPending && <Skeleton lines={2} />}
                {reports.length > 0 && <Command.Group heading="Reports" className={grp}>
                  {reports.map((x, i) => <Command.Item key={i} value={`report ${x.t}`} onSelect={() => flyTo(x.ll, x.th, 'ground')} className={item}>
                    <Newspaper size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{(x.t || '').replace(/ - [^-]*$/, '')}</span><span className="shrink-0 text-[12px] text-fg2">{GRADE_WORD[grades.get(x) || 'single']}</span></Command.Item>)}
                </Command.Group>}
                {terms.length > 0 && <Command.Group heading="Terms" className={grp}>
                  {terms.map(k => <Command.Item key={k} value={`term ${k}`} onSelect={() => openTerm(k)} className={item}>
                    <BookOpen size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{TERMS[k].term}<span className="ml-2 text-[12px] text-fg2 max-[459px]:hidden">{TERMS[k].says.split(/[.:]/)[0]}</span></span></Command.Item>)}
                </Command.Group>}
              </Command.List>
              <div className="flex items-center gap-3 border-t border-line px-4 py-2 text-[11.5px] text-fg2 max-[599px]:hidden" aria-hidden>
                <span><kbd className="font-mono">↑</kbd> <kbd className="font-mono">↓</kbd> to move</span><span className="inline-flex items-center gap-1"><CornerDownLeft size={11} /> to open</span><span><kbd className="font-mono">esc</kbd> to close</span>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
