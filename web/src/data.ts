import { useQuery } from '@tanstack/react-query'

/* The data contract (warwatch/contract.py, schema warwatch/v1). Positions are [lon, lat]. */
export type Level = 'Normal' | 'Watch' | 'Elevated' | 'Critical'
export type LonLat = [number, number]
export type Route = { v: 'brief' } | { v: 'theatre'; id: string; tab?: string } | { v: 'base'; id: string } | { v: 'signal'; id: string } | { v: 'signals'; th?: string } | { v: 'record' } | { v: 'map' }
export type FeedItem = { date: string; kind: 'tell' | 'base' | 'fire' | 'official'; theatre: string; title: string; detail: string; to: { view: string; id: string; tab?: string } }
export type BriefTheatre = {
  id: string; name: string; region: string; level: Level; score: number | null; standingRisk: number | null; tellsOn: number; tellsTotal: number; strong: number
  context: string | null; contextChecked: string | null; spillover: boolean; parents: string[]; center: LonLat | null; groups: Record<Group, number | null>
}
export type Brief = {
  generated: string; demo: boolean; eventsThrough: string; headline: string
  counts: { tells: number; bases: number; theatres: number; signals: number; strong: number }
  global: { level: Level; score: number | null; lead: string }
  regions: { id: string; name: string; theatres: string[]; level: Level; lead: string }[]
  theatres: BriefTheatre[]; feed: FeedItem[]
  model: { version: string; fitted: string; active: boolean; gates: Gates | null }
}
export type Gates = { bss: number; auc: number; auc_lo: number; auc_hi: number; shuffle_p_auc: number; bss_positive: boolean; auc_lo_above_half: boolean; beats_shuffled: boolean; pass: boolean }
export type Tell = { id: string; name: string; on: boolean; date: string | null; says: string; cases: string; record: { hits?: number; episodes?: number; caught?: number; events?: number } | null }
export type GroupDetail = { z: number | null; fast: boolean; history: number[]; top: { id: string; label: string; z: number }[] }
export type Theatre = {
  generated: string; id: string; name: string; region: string; level: Level; score: number | null; standingRisk: number | null
  signals: { scored: number; total: number; strong: number }
  chance: { p: number | null; lo: number | null; hi: number | null; usual: number | null; change: [number, number] | null }
  confidence: string; context: string | null; contextChecked: string | null; spillover: boolean; parents: string[]
  center: LonLat | null; view: [LonLat, LonLat] | null; countries: string[]
  tells: Tell[]; groups: Record<Group, GroupDetail>; official: { name: string; id: string; date: string; value: string }[]
  history: [string, number, number, string][]; items: { date: string; kind: string; text: string; signal: string }[]
  events: { date: string; kind: string; text: string }[]
}
export type Signal = { id: string; label: string; group: Group; sub: string; theatre: string; z: number | null; status: string; stale: string; last: string; lagging: boolean; kind: string; why: string; url: string; event: string | null; spark: (number | null)[] }
export type Signals = { generated: string; groups: Record<Group, string>; signals: Signal[] }
export type MapBase = { id: string; name: string; kind: string; side: string; theatres: string[]; state: string; z: number | null; last: string; ll: LonLat; why: string; radar: number[]; thumb: string; part: string }
export type MapFire = { ll: LonLat; mw: number; date: string; time: string; class: string; score: number; why: string; site: string; theatre: string; night: boolean }
export type MapAircraft = { ll: LonLat; call: string; class: string; t?: string; trk?: number; hex?: string; th?: string; o?: string; ct?: string; alt?: number; gs?: number; sq?: string; emergency: boolean }
export type MapShip = { ll: LonLat; name: string; k?: string; loc?: string; g?: string; d?: string; tx?: string; u?: string; flag?: string; dest?: string; spd?: number; note?: string; th?: string }
export type MapWarning = { ll: LonLat; id: string; text: string; issued: string; theatre: string }
export type MapIncident = { ll: LonLat; t?: string; d?: string; src?: string; u?: string; loc?: string; th?: string; tx?: string }
export type Pic = { src: string; date: string } | null
export type BasePart = { part: string; what: string; where: string; state: string; z: number | null; dates: string; note: string; tested: boolean; now: number | null; usual: number | null; low: number | null; high: number | null
  history: [string, number, number | null, number | null, number | null][]; marks: { date: string; before: string; objects: number; new: number | null; gone: number | null } | null; images: { marked: Pic; before: Pic } }
export type BaseFile = { generated: string; id: string; name: string; type: string; side: string; theatres: string[]; state: string; z: number | null; last: string; previous: string; ll: LonLat
  radar: number[]; why: string; about: string; note: string; mainPart: string; images: { radar: Pic; radarBefore: Pic; optical: Pic; opticalBefore: Pic }; parts: BasePart[] }
export type LiveMap = {
  generated: string; theatres: Record<string, { center: LonLat | null; view: [LonLat, LonLat] | null; countries: string[] }>
  bases: MapBase[]; fires: MapFire[]; aircraft: MapAircraft[]; squawks: MapAircraft[]; ships: MapShip[]; warnings: MapWarning[]; incidents: MapIncident[]; cities: { ll: LonLat; name: string; theatre: string }[]; chokepoints: { ll: LonLat; name: string; theatre: string }[]
}
export type Forward = { k: string; name: string; first: string; logged: number; days: number; need: number; through: string; ready: boolean; pass: boolean }
export type RecordFile = { generated: string; forward: Forward[] | null; model: { v: string; fitted: string; active: boolean; gates: Gates } | null; health: { statuses: Record<string, number>; errors: unknown[]; unavailable: { n: string; w: string }[]; updates: { s: string; e: string; l: string }[] } }

export const GROUPS = ['Logistics', 'Markets', 'People', 'News', 'Physical'] as const
export type Group = (typeof GROUPS)[number]
export const GROUP_HINT: Record<Group, string> = {
  Logistics: 'Contracts, tenders, trade. Moves months ahead, arrives late.',
  Markets: 'Defence stocks, oil, shipping, prediction markets. Moves days ahead.',
  People: 'Advisories, evacuations, sirens, flights cancelled. Days to hours.',
  News: 'Warning language and military-posture events. Hours to days.',
  Physical: 'Aircraft, ships, fires, bases, jamming. Hours.',
}

/* The app is served from the site root (/warwatch/). Every page the build writes (/warwatch/iran/, the 404 page) carries
   <base href> pointing there, so data, images and routes resolve from the root at any path. Without one (dev), the root is /. */
export const ROOT = document.querySelector('base') ? document.baseURI : new URL('/', location.href).href
const DATA = new URL('data/v1/', ROOT).href
async function get<T>(rel: string): Promise<T> {
  const r = await fetch(DATA + rel, { cache: 'no-cache' })
  if (!r.ok) throw new Error(`${rel}: HTTP ${r.status}`)
  return r.json()
}
export const useBrief = () => useQuery({ queryKey: ['brief'], queryFn: () => get<Brief>('brief.json'), refetchInterval: 10 * 60_000 })
export const useTheatre = (id: string) => useQuery({ queryKey: ['theatre', id], queryFn: () => get<Theatre>(`theatres/${id}.json`) })
export const useSignals = (on = true) => useQuery({ queryKey: ['signals'], queryFn: () => get<Signals>('signals/index.json'), enabled: on })
export const useLiveMap = () => useQuery({ queryKey: ['map'], queryFn: () => get<LiveMap>('map/live.json') })
export const useBase = (id: string) => useQuery({ queryKey: ['base', id], queryFn: () => get<BaseFile>(`bases/${id}.json`) })
export type SeriesFile = { generated: string; id: string; points: [string, number | null][]; zHistory: [string, number | null][] }
export const useSeries = (id: string) => useQuery({ queryKey: ['series', id], queryFn: () => get<SeriesFile>(`signals/series/${id}.json`) })
export const useRecord = () => useQuery({ queryKey: ['record'], queryFn: () => get<RecordFile>('record.json') })

/* Images and tiles sit at the site root: img/bases/…, basemap.pmtiles */
export const asset = (src: string) => new URL(src, ROOT).href

/* Base states as basewatch.py writes them */
export const BASE_STATE: Record<string, [string, string]> = {
  out: ['Fewer than usual', 'var(--elev)'], in: ['More than usual', 'var(--elev)'], changed: ['One pass differed', 'var(--watch)'],
  normal: ['Usual on the latest pass', 'var(--fg-3)'], optical: ['Optical images only', 'var(--fg-3)'], nodata: ['No recent pass', 'var(--fg-3)'],
}
export const baseState = (s: string) => BASE_STATE[s] || [s, 'var(--fg-3)']

/* Words and colours */
export const LEVELS: Level[] = ['Normal', 'Watch', 'Elevated', 'Critical']
export const levelVar = (l: string) => l === 'Critical' ? 'var(--crit)' : l === 'Elevated' ? 'var(--elev)' : l === 'Watch' ? 'var(--watch)' : 'var(--fg-3)'
export const levelWord = (l: string) => l === 'Normal' ? 'Quiet' : l
export const zColor = (z: number | null | undefined) => z == null ? 'transparent' : Math.abs(z) >= 3 ? 'var(--elev)' : Math.abs(z) >= 2 ? 'var(--watch)' : Math.abs(z) >= 1 ? 'color-mix(in oklab, var(--watch) 38%, transparent)' : 'color-mix(in oklab, var(--fg-3) 22%, transparent)'
export const fmtZ = (z: number | null | undefined) => z == null ? 'n/a' : (z > 0 ? '+' : z < 0 ? '−' : '') + Math.abs(z).toFixed(1)
export const parseGen = (g: string) => new Date(g.replace(' UTC', 'Z').replace(' ', 'T'))
export const shortDate = (d: string) => { const x = new Date(d + (d.length === 7 ? '-01' : '') + 'T00:00Z'); return x.toLocaleDateString('en-GB', { day: d.length === 7 ? undefined : 'numeric', month: 'short', timeZone: 'UTC' }) }
export const daysBetween = (now: Date, d: string) => Math.round((now.getTime() - new Date(d.slice(0, 10) + 'T12:00Z').getTime()) / 864e5)
export const ago = (now: Date, d: string) => { const n = daysBetween(now, d); return n <= 0 ? 'Today' : n === 1 ? 'Yesterday' : n < 7 ? `${n} days ago` : shortDate(d.slice(0, 10)) }

/* One plain sentence per theatre, built from its levels and tells (the Brief's headline comes from the build, share.py). */
export function summary(t: Theatre): string {
  const strong = GROUPS.filter(g => (t.groups[g]?.z ?? 0) >= 2).map(g => g.toLowerCase())
  const parts = [t.level === 'Normal'
    ? (strong.length ? `Quiet overall, with ${strong.join(' and ')} readings above their usual range.` : 'Quiet. No signal group is far from its usual range.')
    : `${t.level}: ${strong.length ? strong.join(' and ') + ' readings are well above usual' : 'several readings are above usual'}.`]
  const on = t.tells.filter(x => x.on)
  parts.push(on.length ? `${on.length === 1 ? 'One timing tell' : on.length + ' timing tells'} fired this week: ${on.map(x => /^[A-Z][a-z]/.test(x.name) ? x.name[0].toLowerCase() + x.name.slice(1) : x.name).join('; ')}.` : 'No timing tell fired this week.')
  return parts.join(' ')
}

/* Routes are real paths under the root, so each theatre can carry its own share card: /warwatch/iran/, /warwatch/iran/ground/,
   /warwatch/base/<id>/, /warwatch/signal/<id>/, /warwatch/signals/, /warwatch/record/, /warwatch/map/. */
const VIEWS = ['base', 'signal', 'signals', 'record', 'map']
export function parsePath(rel: string): Route {
  const p = rel.split(/[?#]/)[0].split('/').filter(x => x && x !== 'index.html').map(decodeURIComponent)
  if (p[0] === 'base' && p[1]) return { v: 'base', id: p[1] }
  if (p[0] === 'signal' && p[1]) return { v: 'signal', id: p[1] }
  if (p[0] === 'signals') return { v: 'signals', th: p[1] }
  if (p[0] === 'record') return { v: 'record' }
  if (p[0] === 'map') return { v: 'map' }
  if (p[0] && !VIEWS.includes(p[0])) return { v: 'theatre', id: p[0], tab: p[1] }
  return { v: 'brief' }
}
export const routePath = (r: Route) => r.v === 'brief' ? '' : r.v === 'theatre' ? `${r.id}/${r.tab && r.tab !== 'now' ? r.tab + '/' : ''}`
  : r.v === 'base' || r.v === 'signal' ? `${r.v}/${encodeURIComponent(r.id)}/` : r.v === 'signals' ? `signals/${r.th ? r.th + '/' : ''}` : `${r.v}/`
export const routeHref = (r: Route) => new URL(routePath(r), ROOT).href
export function currentRoute(): Route {
  const root = new URL(ROOT).pathname, path = location.pathname
  return parsePath(path.startsWith(root) ? path.slice(root.length) : '')
}

/* Links from before the switch-over still work: the preview's #/theatre/iran/now and the old page's #iran/signals, #signals?q=…, #record */
export function legacyHash(h: string): Route | null {
  const raw = decodeURIComponent(h.replace(/^#/, ''))
  if (!raw) return null
  if (raw.startsWith('/')) {
    const p = raw.split('/').filter(Boolean)
    return p[0] === 'theatre' && p[1] ? { v: 'theatre', id: p[1], tab: p[2] } : parsePath(p.join('/'))
  }
  const [a, b] = raw.split('?')[0].split('/')
  if (a === 'overview' || a === 'region') return { v: 'brief' }
  if (a === 'signals') return { v: 'signals' }
  if (a === 'activity' || a === 'assets') return { v: 'map' }
  if (a === 'record' || a === 'settings' || a === 'system') return { v: 'record' }
  if (/^[a-z_]+$/.test(a)) return { v: 'theatre', id: a, tab: b === 'signals' || b === 'markets' ? 'signals' : b === 'history' || b === 'alerts' ? 'history' : undefined }
  return null
}
