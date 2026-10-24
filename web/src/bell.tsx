import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { Bell, Satellite, Flame, ShieldAlert, FileText, Plane, Anchor } from 'lucide-react'
import { ago, daysBetween, parseGen, type Brief, type FeedItem, type LiveMap, type Route } from './data'
import { toRoute } from './views'

/* The bell (the old page had one): the week's changes from the Brief's feed, newest first, with live alerts on top
   (emergency squawks, incidents at sea). What arrived in the last 48 hours and has not been opened counts on the badge;
   opening the list marks it read in this browser. The Brief itself starts with the theatres. */

type Kind = FeedItem['kind'] | 'air' | 'sea'
type Note = { id: string; kind: Kind; date: string; theatre: string; title: string; detail: string; to: Route; live?: boolean }
const KIND: Record<Kind, [typeof Bell, string, string]> = {
  tell: [ShieldAlert, 'var(--watch)', 'Tells'], base: [Satellite, 'var(--elev)', 'Bases'], fire: [Flame, 'var(--elev)', 'Fires'], official: [FileText, 'var(--fg-3)', 'Official'],
  air: [Plane, 'var(--crit)', 'Live'], sea: [Anchor, 'var(--elev)', 'Live'],
}
const TABS = ['All', 'Live', 'Tells', 'Bases', 'Fires', 'Official'] as const
const KEY = 'ww-read'
const load = (): Set<string> => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')) } catch { return new Set() } }
const save = (s: Set<string>) => { try { localStorage.setItem(KEY, JSON.stringify([...s].slice(-600))) } catch { /* private mode: nothing kept */ } }

function notes(brief: Brief, live?: LiveMap): Note[] {
  const now = parseGen(brief.generated)
  const out: Note[] = []
  for (const a of live?.squawks || []) out.push({ id: `sq:${a.hex || a.call}:${a.sq}`, kind: 'air', date: brief.generated.slice(0, 10), theatre: a.th || '', live: true,
    title: `Emergency squawk ${a.sq}${a.call ? `: ${a.call}` : ''}`, detail: [a.t, a.o || a.ct].filter(Boolean).join(' · ') || 'Seen on ADS-B at the last run', to: a.th ? { v: 'theatre', id: a.th, tab: 'ground' } : { v: 'map' } })
  for (const x of live?.incidents || []) if (x.d && daysBetween(now, x.d) <= 7) out.push({ id: `inc:${(x.t || '').slice(0, 60)}`, kind: 'sea', date: x.d.slice(0, 10), theatre: x.th || '',
    title: x.t || 'Incident at sea', detail: [x.src, x.loc].filter(Boolean).join(' · '), to: x.th ? { v: 'theatre', id: x.th, tab: 'ground' } : { v: 'map' } })
  for (const f of brief.feed) if (daysBetween(now, f.date) <= 7) out.push({ id: `${f.date.slice(0, 10)}|${f.theatre}|${f.kind}|${f.title}`, kind: f.kind, date: f.date, theatre: f.theatre, title: f.title, detail: f.detail, to: toRoute(f.to) })
  return out.sort((a, b) => Number(!!b.live) - Number(!!a.live) || b.date.localeCompare(a.date))
}

export function NotificationBell({ brief, live, go, phone = false }: { brief: Brief; live?: LiveMap; go: (r: Route) => void; phone?: boolean }) {
  const now = parseGen(brief.generated)
  const all = useMemo(() => notes(brief, live), [brief, live])
  const [read, setRead] = useState(load)
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<(typeof TABS)[number]>('All')
  const box = useRef<HTMLDivElement>(null)
  const fresh = (n: Note) => n.live || daysBetween(now, n.date) <= 1
  const unread = all.filter(n => fresh(n) && !read.has(n.id)).length
  const markAll = () => { const s = new Set(read); all.forEach(n => s.add(n.id)); setRead(s); save(s) }
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false) } }
    const c = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    addEventListener('keydown', k, true); addEventListener('pointerdown', c)
    return () => { removeEventListener('keydown', k, true); removeEventListener('pointerdown', c) }
  }, [open])
  const tabs = TABS.filter(t => t === 'All' || all.some(n => KIND[n.kind][2] === t))
  const list = all.filter(n => tab === 'All' || KIND[n.kind][2] === tab)
  const name = (id: string) => brief.theatres.find(t => t.id === id)?.name || ''
  const groups: [string, Note[]][] = [['Last 48 hours', list.filter(fresh)], ['Earlier this week', list.filter(n => !fresh(n))]]
  const btn = phone ? 'grid h-9 w-9 place-items-center rounded-full border border-line bg-panel/80 backdrop-blur' : 'grid h-8 w-8 place-items-center rounded-full border border-line bg-panel/80 text-fg2 backdrop-blur-md hover:text-fg'
  return (
    <div ref={box} className={phone ? '' : 'pointer-events-auto relative'}>
      <button onClick={() => setOpen(o => !o)} aria-expanded={open} aria-label={unread ? `Notifications, ${unread} new` : 'Notifications'} className={`${btn} relative`}>
        <Bell size={phone ? 16 : 15} />
        {unread > 0 && <span className="num absolute -right-1 -top-1 grid h-[17px] min-w-[17px] place-items-center rounded-full bg-accent px-1 text-[10px] font-semibold leading-none text-accentink">{unread > 99 ? '99+' : unread}</span>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div role="dialog" aria-label="Notifications" initial={{ opacity: 0, y: -6, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: .16, ease: [.22, 1, .36, 1] }}
            className={`z-40 flex flex-col overflow-hidden rounded-2xl border border-line2 bg-panel shadow-[var(--shadow)] ${phone ? 'fixed inset-x-2 top-[60px] max-h-[72vh]' : 'absolute right-0 top-10 max-h-[min(640px,calc(100vh-90px))] w-[420px]'}`}>
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-4 py-3">
              <div><div className="text-[14px] font-medium">Notifications</div><div className="text-[11.5px] text-fg3">This week, newest first. Live alerts on top.</div></div>
              {unread > 0 ? <button onClick={markAll} className="shrink-0 text-[12px] text-accent hover:underline">Mark all as read</button> : <span className="shrink-0 text-[12px] text-fg3">All read</span>}
            </div>
            <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-line px-3 py-2 text-[12px]">
              {tabs.map(t => <button key={t} onClick={() => setTab(t)} aria-pressed={tab === t} className={`shrink-0 rounded-full px-2.5 py-1 ${tab === t ? 'bg-hover text-fg' : 'text-fg3 hover:text-fg2'}`}>
                {t} <span className="num text-fg3">{t === 'All' ? all.length : all.filter(n => KIND[n.kind][2] === t).length}</span></button>)}
            </div>
            <div className="scroll-thin min-h-0 flex-1 overflow-y-auto pb-2">
              {list.length === 0 && <p className="px-4 py-6 text-[13px] text-fg3">Nothing new this week: no timing tell, base change, unusual fire, official step or live alert.</p>}
              {groups.map(([g, L]) => L.length > 0 && <div key={g}>
                <div className="eyebrow px-4 pb-1 pt-3">{g}</div>
                <ul className="px-2">
                  {L.map(n => { const [I, tone] = KIND[n.kind], isNew = fresh(n) && !read.has(n.id); return (
                    <li key={n.id}>
                      <button onClick={() => { const s = new Set(read); s.add(n.id); setRead(s); save(s); setOpen(false); go(n.to) }} className="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left hover:bg-hover">
                        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border border-line" style={{ color: tone }}><I size={14} /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-[13px] leading-snug text-fg">{isNew && <i className="mr-1.5 inline-block h-1.5 w-1.5 -translate-y-px rounded-full bg-accent align-middle" aria-label="new" />}{name(n.theatre) && <b className="font-medium">{name(n.theatre)} · </b>}{n.title}</span>
                          <span className="block text-[11.5px] text-fg3">{n.detail}</span>
                        </span>
                        <span className="num shrink-0 pt-0.5 text-[11px] text-fg3">{n.live ? 'Now' : ago(now, n.date)}</span>
                      </button>
                    </li>) })}
                </ul>
              </div>)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
