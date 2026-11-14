import { useEffect, useRef, useSyncExternalStore } from 'react'
import { short, levelWord, shortDate, parseGen, type Brief, type Level, type Route } from './data'
import { feedKey } from './since'

/* Following a theatre: the theatres a reader pins sit at the top of the board. The list, and whether to notify, are kept in this
   browser only ("ww-follow", "ww-notify"); with storage blocked they last this visit. Settings' Clear removes both.

   Notifications: only while a WarWatch tab is open (or the app is open from a phone's home screen). There is no server and no
   push, so a closed page cannot notify. When fresh data arrives during the visit (brief.json is fetched again every 10 minutes,
   also in a background tab), each followed theatre is compared with the data this tab saw before: one notification when its level
   rises to Watch or above, and one for each tripwire that newly fired there. The first data of a visit is only the starting point,
   never notified. Each event is noted in "ww-notified", so two open tabs or a reload never send it twice. */

const FOLLOW = 'ww-follow', NOTIFY = 'ww-notify', SENT = 'ww-notified'
const read = <T,>(k: string, fallback: T, ok: (x: any) => boolean): T => { try { const x = JSON.parse(localStorage.getItem(k) || 'null'); return ok(x) ? x : fallback } catch { return fallback } }
const write = (k: string, v: unknown) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* private mode: this visit only */ } }

type State = { ids: string[]; notify: boolean; asked: boolean }
let state: State = {
  ids: read<string[]>(FOLLOW, [], x => Array.isArray(x) && x.every(i => typeof i === 'string')),
  notify: read<boolean>(NOTIFY, false, x => typeof x === 'boolean'),
  asked: false,
}
state.asked = (() => { try { return localStorage.getItem(NOTIFY) != null } catch { return false } })()
const subs = new Set<() => void>()
const emit = () => subs.forEach(f => f())
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f) } }

export function useFollow() {
  const s = useSyncExternalStore(subscribe, () => state)
  return {
    ids: s.ids, notify: s.notify,
    has: (id: string) => s.ids.includes(id),
    toggle: (id: string) => {
      const on = !state.ids.includes(id)
      state = { ...state, ids: on ? [...state.ids, id] : state.ids.filter(x => x !== id) }; write(FOLLOW, state.ids); emit()
      /* the first follow of this browser offers the notify switch once */
      if (on && !state.asked) { state = { ...state, asked: true }; emit(); dispatchEvent(new CustomEvent('ww-followed', { detail: id })) }
    },
    setNotify: (b: boolean) => { state = { ...state, notify: b, asked: true }; write(NOTIFY, b); emit() },
  }
}
/* Settings' Clear: forget the follows held for this visit too (storage may have refused them) */
export function forgetFollows() { state = { ids: [], notify: false, asked: false }; emit() }

/* what the browser allows: 'unsupported' (no Notification API), or the permission */
export type Permission = 'unsupported' | 'default' | 'granted' | 'denied'
export const permission = (): Permission => typeof window === 'undefined' || !('Notification' in window) ? 'unsupported' : Notification.permission as Permission
/* asked only from a click on the switch, never on load */
export async function askPermission(): Promise<Permission> {
  if (permission() === 'unsupported') return 'unsupported'
  try { return (await Notification.requestPermission()) as Permission } catch { return permission() }
}
export const permissionLine = (p: Permission) => p === 'unsupported' ? 'This browser cannot show notifications, so following only pins the theatre to the top of the board.'
  : p === 'denied' ? 'Notifications are blocked for WarWatch in this browser. Allow them in the site settings of the browser, then switch this on again.'
  : null

/* ---------------------------------------------------------------- the events between two data runs */
const RANK: Record<Level, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }
export type Alert = { key: string; theatre: string; title: string; body: string }
export function alerts(prev: Brief, next: Brief, follow: string[]): Alert[] {
  const out: Alert[] = []
  const at = parseGen(next.generated), run = `${shortDate(next.generated.slice(0, 10))}, ${at.toISOString().slice(11, 16)} UTC`
  const before = new Map(prev.theatres.map(t => [t.id, t])), seen = new Set(prev.feed.map(feedKey))
  for (const t of next.theatres) {
    if (!follow.includes(t.id)) continue
    const p = before.get(t.id), name = short(t.name)
    if (p && RANK[t.level] >= 1 && RANK[t.level] > RANK[p.level])
      out.push({ key: `level|${t.id}|${t.level}|${next.generated}`, theatre: t.id, title: `${name} is at ${t.level}`,
        body: `${name} rose from ${levelWord(p.level)} to ${t.level} in the WarWatch run of ${run}.` })
    for (const f of next.feed) {
      if (f.kind !== 'tell' || f.theatre !== t.id || seen.has(feedKey(f))) continue
      out.push({ key: `tell|${feedKey(f)}`, theatre: t.id, title: `Tripwire on ${name}: ${f.title}`,
        body: `The ${f.title} tripwire fired on ${name} on ${shortDate(f.date.slice(0, 10))}. Seen in the WarWatch run of ${run}.` })
    }
  }
  return out
}

/* Watches the brief while the app is open. Never on the first data of the visit, never for an event already sent. */
export function useNotifier(brief: Brief, go: (r: Route) => void) {
  const { ids, notify } = useFollow()
  const last = useRef<Brief | null>(null)
  const goRef = useRef(go); goRef.current = go
  useEffect(() => {
    const prev = last.current; last.current = brief
    if (!prev || prev.generated === brief.generated || !notify || !ids.length || permission() !== 'granted') return
    const sent = new Set(read<string[]>(SENT, [], x => Array.isArray(x)))
    for (const a of alerts(prev, brief, ids)) {
      if (sent.has(a.key)) continue
      sent.add(a.key)
      try {
        const n = new Notification(a.title, { body: a.body, tag: a.key, icon: new URL('apple-touch-icon.png', document.baseURI).href })
        n.onclick = () => { try { window.focus() } catch { /* the browser decides */ } goRef.current({ v: 'theatre', id: a.theatre }); n.close() }
      } catch { /* some browsers allow notifications only from a service worker: nothing is shown, nothing breaks */ }
    }
    write(SENT, [...sent].slice(-300))
  }, [brief])
}
