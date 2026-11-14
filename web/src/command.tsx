import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Command } from 'cmdk'
import { Globe, Activity, ClipboardCheck, Sun, SlidersHorizontal, Search, Satellite, BookOpen, Link2, History, CornerDownLeft, Monitor } from 'lucide-react'
import { useSignals, short, baseState, fmtZ, levelWord, wholeScore, type Brief, type LiveMap, type Route } from './data'
import { TERMS, ORDER as TERM_ORDER, type TermKey } from './glossary'
import { useDialogFocus } from './settings'
import { Skeleton } from './ui'

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
/* "crisiswatch south china" finds "CrisisWatch rating, South China Sea region": every word somewhere in the name */
const allWords = (a: string, q: string) => { const w = q.split(/\s+/).filter(Boolean); return w.length > 1 && w.every(x => a.includes(x)) }

export default function CommandMenu({ open, setOpen, go, toggleTheme, openSettings, copyLink, brief, live }: {
  open: boolean; setOpen: (b: boolean) => void; go: (r: Route) => void; toggleTheme: () => void; openSettings: () => void; copyLink: () => void; brief: Brief; live?: LiveMap }) {
  const sigs = useSignals(open)
  const [q, setQ] = useState('')
  const [recent, setRecent] = useState<Pick[]>(loadRecent)
  const box = useRef<HTMLDivElement>(null)
  useDialogFocus(open, box)
  useEffect(() => { if (open) { setQ(''); setRecent(loadRecent()) } }, [open])
  const typed = q.trim().length > 0
  /* every signal (921) can be found by its name, source or id; searched only from two letters, with the query deferred so typing
     stays quick, and at most SIG_MAX shown, best first */
  const dq = useDeferredValue(q.trim().toLowerCase())
  const sigHits = useMemo(() => {
    if (dq.length < 2 || !sigs.data) return []
    const rank = (s: { label: string; sub: string; id: string }) => { const a = `${s.label} ${s.sub} ${s.id}`.toLowerCase(); return a.startsWith(dq) ? 3 : a.includes(' ' + dq) || a.includes('_' + dq) ? 2 : a.includes(dq) || allWords(a, dq) ? 1 : 0 }
    return sigs.data.signals.map(s => [rank(s), s] as const).filter(x => x[0] > 0).sort((a, b) => b[0] - a[0] || Math.abs(b[1].z ?? 0) - Math.abs(a[1].z ?? 0)).slice(0, SIG_MAX).map(x => x[1])
  }, [dq, sigs.data])
  const run = (r: Route, pick?: Pick) => { if (pick) saveRecent(pick); setOpen(false); go(r) }
  const openTerm = (k: TermKey) => {
    run({ v: 'glossary', term: k }, { k: 'term', id: k, label: TERMS[k].term })
  }
  const region = (id: string) => brief.regions.find(r => r.id === id)?.name || ''
  const theatres = useMemo(() => [...brief.theatres].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)), [brief])
  /* before typing: the bases that changed on radar; once typing: every base */
  const bases = useMemo(() => (live?.bases || []).filter(b => typed || CHANGED.includes(b.state)).slice(0, typed ? undefined : 5), [live, typed])
  const pickRoute = (p: Pick): Route => p.k === 'theatre' ? { v: 'theatre', id: p.id } : p.k === 'base' ? { v: 'base', id: p.id } : p.k === 'signal' ? { v: 'signal', id: p.id } : { v: 'glossary', term: p.id }
  const item = 'flex min-h-11 cursor-pointer items-center gap-3 rounded-r2 px-2.5 py-2 text-[13.5px] text-fg2 data-[selected=true]:bg-s3 data-[selected=true]:text-fg'
  const side = 'num shrink-0 text-[12px] text-fg2'
  const grp = '[&_[cmdk-group-heading]]:eyebrow [&_[cmdk-group-heading]]:!text-fg2 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-3'
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-start justify-center bg-black/40 px-3 pt-[10vh] backdrop-blur-[2px] max-[599px]:pt-3" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={() => setOpen(false)}>
          <motion.div ref={box} role="dialog" aria-modal="true" aria-label="Search and go to" initial={{ y: -6, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .18, ease: EASE }} onClick={e => e.stopPropagation()}
            className="w-[min(640px,calc(100vw-24px))] overflow-hidden rounded-r3 border border-line2 bg-s1 shadow-[var(--shadow)]">
            <Command label="Search WarWatch" loop filter={(v, s) => { const a = v.toLowerCase(), b = s.toLowerCase().trim(); if (!b) return 1; if (a.startsWith(b)) return 1; if (a.includes(' ' + b)) return .9; return a.includes(b) ? .2 : allWords(a, b) ? .1 : 0 }}>
              <div className="flex items-center gap-2.5 border-b border-line px-4">
                <Search size={16} className="shrink-0 text-fg2" aria-hidden />
                <Command.Input autoFocus value={q} onValueChange={setQ} placeholder="Go to a theatre, base, signal or term" className="h-12 min-w-0 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-fg2" />
                <kbd className="shrink-0 rounded-[4px] border border-line2 px-1.5 py-0.5 font-mono text-[10.5px] leading-none text-fg2">esc</kbd>
              </div>
              <Command.List className="scroll-thin max-h-[min(56vh,520px)] overflow-y-auto p-2 max-[599px]:max-h-[calc(100dvh-140px)]">
                <Command.Empty className="px-3 py-7 text-center text-[13px] leading-[1.5] text-fg2">Nothing matches “{q.trim()}”.<br />Try a country, a base, a source such as NOTAM, or a word such as tripwire.</Command.Empty>
                <Command.Group heading="Go to" className={grp}>
                  <Command.Item value="Watch home board map" onSelect={() => run({ v: 'brief' })} className={item}><Globe size={15} aria-hidden />Watch</Command.Item>
                  <Command.Item value="Signals all signals" onSelect={() => run({ v: 'signals' })} className={item}><Activity size={15} aria-hidden />Signals</Command.Item>
                  <Command.Item value="Ground bases fires heat chokepoints" onSelect={() => run({ v: 'ground' })} className={item}><GroundIcon />Ground<span className="ml-auto text-[12px] text-fg2">bases, heat and chokepoints</span></Command.Item>
                  <Command.Item value="Record track record model data health" onSelect={() => run({ v: 'record' })} className={item}><ClipboardCheck size={15} aria-hidden />Record<span className="ml-auto text-[12px] text-fg2">the model's test, data health</span></Command.Item>
                  <Command.Item value="Glossary terms words meaning" onSelect={() => run({ v: 'glossary' })} className={item}><BookOpen size={15} aria-hidden />Glossary</Command.Item>
                  <Command.Item value="Wall mode spare screen full screen monitor" onSelect={() => run({ v: 'wall' })} className={item}><Monitor size={15} aria-hidden />Wall<span className="ml-auto text-[12px] text-fg2 max-[459px]:hidden">Watch for a spare screen</span></Command.Item>
                  <Command.Item value="Copy link to this view share" onSelect={() => { setOpen(false); copyLink() }} className={item}><Link2 size={15} aria-hidden />Copy link to this view</Command.Item>
                  <Command.Item value="Switch light or dark theme" onSelect={() => { setOpen(false); toggleTheme() }} className={item}><Sun size={15} aria-hidden />Switch light or dark</Command.Item>
                  <Command.Item value="Settings preferences" onSelect={() => { setOpen(false); openSettings() }} className={item}><SlidersHorizontal size={15} aria-hidden />Settings</Command.Item>
                </Command.Group>
                {!typed && recent.length > 0 && <Command.Group heading="Recent" className={grp}>
                  {recent.map(p => <Command.Item key={'r' + p.k + p.id} value={`recent ${p.label} ${p.k} ${p.id}`} onSelect={() => p.k === 'term' ? openTerm(p.id as TermKey) : run(pickRoute(p), p)} className={item}><History size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{p.label}</span><span className="text-[12px] text-fg2">{({ theatre: 'Theatre', base: 'Base', signal: 'Signal', term: 'Term' })[p.k]}</span></Command.Item>)}
                </Command.Group>}
                <Command.Group heading="Theatres" className={grp}>
                  {theatres.map(t => <Command.Item key={t.id} value={`${t.name} ${region(t.region)} ${(live?.theatres[t.id]?.countries || []).join(' ')} ${t.id}`} onSelect={() => run({ v: 'theatre', id: t.id }, { k: 'theatre', id: t.id, label: short(t.name) })} className={item}>
                    <Globe size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{short(t.name)}<span className="ml-2 text-[12px] text-fg2">{region(t.region)}</span></span>
                    <span className={side}>{levelWord(t.level)}{t.score != null ? `, readings ${wholeScore(t.score)}` : ''}</span></Command.Item>)}
                </Command.Group>
                {bases.length > 0 && <Command.Group heading={typed ? 'Bases' : 'Bases that changed on radar'} className={grp}>
                  {bases.map(b => <Command.Item key={b.id} value={`${b.name} base ${b.side} ${b.id}`} onSelect={() => run({ v: 'base', id: b.id }, { k: 'base', id: b.id, label: b.name.split(',')[0] })} className={item}>
                    <Satellite size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{b.name}</span><span className="shrink-0 text-[12px] text-fg2 max-[459px]:hidden">{baseState(b.state)[0]}</span></Command.Item>)}
                </Command.Group>}
                {sigHits.length > 0 && <Command.Group heading="Signals" className={grp}>
                  {sigHits.map(s => <Command.Item key={s.id} value={`${s.label} ${s.sub} ${s.id}`} onSelect={() => run({ v: 'signal', id: s.id }, { k: 'signal', id: s.id, label: s.label })} className={item}>
                    <Activity size={15} aria-hidden /><span className="min-w-0 flex-1 truncate">{s.label}</span><span className="num shrink-0 font-mono text-[11.5px] text-fg2">{s.z == null ? 'not scored' : fmtZ(s.z)}</span></Command.Item>)}
                </Command.Group>}
                {typed && sigs.isPending && <Skeleton lines={2} />}
                {typed && <Command.Group heading="Glossary" className={grp}>
                  {TERM_ORDER.map(k => <Command.Item key={k} value={`${TERMS[k].term} glossary term`} onSelect={() => openTerm(k)} className={item}>
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
