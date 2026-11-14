import { useEffect, useRef, useSyncExternalStore } from 'react'
import { short, levelWord, shortDate, parseGen, type Brief, type Level, type Route } from './data'

/* Following a theatre: the theatres a reader pins sit at the top of the board. The list, and whether to notify, are kept in this
   browser only ("ww-follow", "ww-notify"); with storage blocked they last this visit. Settings' Clear removes both.

   Notifications: only in a desktop browser while a WarWatch tab is open. There is no server, no push and no service worker, so a
   closed page cannot notify, and phones (Android Chrome needs a service worker, iOS home-screen apps notify only through push)
   cannot either: there the switch is off and says why. When newer data arrives during the visit (brief.json is fetched again
   every 10 minutes, also in a background tab), each followed theatre is compared with the data this tab saw before: one
   notification when its level rises to Watch or above, and one when a tripwire turns on there (lit now, not lit in the data
   before; one that stays lit is not sent again). The first data of a visit is only the starting point, never notified. Each
   event is noted in "ww-notified", read and written just before it is shown, so two open tabs or a reload never send it twice. */

const FOLLOW = 'ww-follow', NOTIFY = 'ww-notify', SENT = 'ww-notified'
const read = <T,>(k: string, fallback: T, ok: (x: any) => boolean): T => { try { const x = JSON.parse(localStorage.getItem(k) || 'null'); return ok(x) ? x : fallback } catch { return fallback } }
const write = (k: string, v: unknown) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* private mode: this visit only */ } }

/* failed: this browser refused to show a notification during this visit (the switch is then off and says so) */
type State = { ids: string[]; notify: boolean; asked: boolean; failed: boolean }
let state: State = {
  ids: read<string[]>(FOLLOW, [], x => Array.isArray(x) && x.every(i => typeof i === 'string')),
  notify: read<boolean>(NOTIFY, false, x => typeof x === 'boolean'),
  asked: false, failed: false,
}
state.asked = (() => { try { return localStorage.getItem(NOTIFY) != null } catch { return false } })()
const subs = new Set<() => void>()
const emit = () => subs.forEach(f => f())
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f) } }

export function useFollow() {
  const s = useSyncExternalStore(subscribe, () => state)
  return {
    ids: s.ids, notify: s.notify, failed: s.failed,
    has: (id: string) => s.ids.includes(id),
    toggle: (id: string) => {
      const on = !state.ids.includes(id)
      state = { ...state, ids: on ? [...state.ids, id] : state.ids.filter(x => x !== id) }; write(FOLLOW, state.ids); emit()
      /* the first follow of this browser offers the notify switch once */
      if (on && !state.asked) { state = { ...state, asked: true }; emit(); dispatchEvent(new CustomEvent('ww-followed', { detail: id })) }
    },
    setNotify: (b: boolean) => { state = { ...state, notify: b, asked: true, failed: b ? false : state.failed }; write(NOTIFY, b); emit() },
  }
}
/* Settings' Clear: forget the follows held for this visit too (storage may have refused them) */
export function forgetFollows() { state = { ids: [], notify: false, asked: false, failed: false }; emit() }
/* a notification the browser would not show: the switch goes off and says so */
function failed() { state = { ...state, notify: false, failed: true }; write(NOTIFY, false); emit() }

/* what the browser allows: 'unsupported' (no Notification API), 'phone' (a touch device with no hover: a page there cannot notify
   without a service worker or push, which WarWatch does not have), or the permission */
export type Permission = 'unsupported' | 'phone' | 'default' | 'granted' | 'denied'
const phone = () => { try { return matchMedia('(hover: none) and (pointer: coarse)').matches } catch { return false } }
export const permission = (): Permission => typeof window === 'undefined' || !('Notification' in window) || typeof Notification !== 'function' ? 'unsupported'
  : phone() ? 'phone' : Notification.permission as Permission
/* asked only from a click on the switch, never on load */
export async function askPermission(): Promise<Permission> {
  const p = permission()
  if (p === 'unsupported' || p === 'phone') return p
  try { return (await Notification.requestPermission()) as Permission } catch { return permission() }
}
export const WHERE = "Works in desktop browsers while WarWatch is open in a tab."
export const permissionLine = (p: Permission, fail = false) => fail ? 'This browser would not show a notification from the page, so this is off. Following still pins the theatre to the top of the board.'
  : p === 'phone' ? 'Phones do not let a page notify unless it runs in the background, so this is off here.'
  : p === 'unsupported' ? 'This browser cannot show notifications, so following only pins the theatre to the top of the board.'
  : p === 'denied' ? 'Notifications are blocked for WarWatch in this browser. Allow them in the site settings of the browser, then switch this on again.'
  : null

/* ---------------------------------------------------------------- the events between two data runs */
const RANK: Record<Level, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }
export type Alert = { key: string; theatre: string; title: string; body: string }
export function alerts(prev: Brief, next: Brief, follow: string[]): Alert[] {
  const out: Alert[] = []
  /* only data newer than the data before; the same run or an older one (a cached copy) is never compared */
  if (!(parseGen(next.generated).getTime() > parseGen(prev.generated).getTime())) return out
  const at = parseGen(next.generated), run = `${shortDate(next.generated.slice(0, 10))}, ${at.toISOString().slice(11, 16)} UTC`
  const before = new Map(prev.theatres.map(t => [t.id, t])), names = next.replay?.tripwires ?? {}
  for (const t of next.theatres) {
    if (!follow.includes(t.id)) continue
    const p = before.get(t.id), name = short(t.name)
    if (p && RANK[t.level] >= 1 && RANK[t.level] > RANK[p.level])
      out.push({ key: `level|${t.id}|${t.level}|${next.generated}`, theatre: t.id, title: `${name} is at ${t.level}`,
        body: `${name} rose from ${levelWord(p.level)} to ${t.level} in the WarWatch run of ${run}.` })
    /* a tripwire that turned on: lit now and not lit in the data before (tellsLit, by tripwire id); older data has no ids */
    if (!p || !Array.isArray(p.tellsLit) || !Array.isArray(t.tellsLit)) continue
    for (const id of t.tellsLit) {
      if (p.tellsLit.includes(id)) continue
      out.push({ key: `tell|${t.id}|${id}|${next.generated}`, theatre: t.id, title: `Tripwire lit on ${name}`,
        body: `${names[id] || id} turned on for ${name} in the WarWatch run of ${run}.` })
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
    const prev = last.current
    if (prev && !(parseGen(brief.generated).getTime() > parseGen(prev.generated).getTime())) return    // not newer: keep the old base
    last.current = brief
    if (!prev || !notify || !ids.length || permission() !== 'granted') return
    const list = alerts(prev, brief, ids)
    if (!list.length) return
    const deliver = () => {
      for (const a of list) {
        /* read and write the sent keys just before showing, so a second tab that got the same data finds this one's mark */
        const sent = read<string[]>(SENT, [], x => Array.isArray(x))
        if (sent.includes(a.key)) continue
        write(SENT, [...sent, a.key].slice(-300))
        try {
          const n = new Notification(a.title, { body: a.body, tag: a.key, icon: new URL('apple-touch-icon.png', document.baseURI).href })
          n.onclick = () => { try { window.focus() } catch { /* the browser decides */ } goRef.current({ v: 'theatre', id: a.theatre }); n.close() }
        } catch { failed(); return }      // the browser would not show it from a page: off, and the switch says so
      }
    }
    /* two tabs can get the same run at the same moment: a lock shared by the site's tabs lets one check and mark at a time */
    const locks = (navigator as Navigator & { locks?: { request: (n: string, f: () => void) => Promise<unknown> } }).locks
    if (locks) locks.request('ww-notified', deliver).catch(deliver); else deliver()
  }, [brief])
}
