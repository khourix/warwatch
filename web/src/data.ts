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
export type Tell = { id: string; name: string; on: boolean; date: string | null; says: string; cases: string; record: TellRecord | null }
/* a tripwire's past: fired `episodes` times since `first`, `hits` of them followed by an event; it fired before `caught` of `events` past events */
export type TellRecord = { hits?: number; episodes?: number; caught?: number; events?: number; first?: string; last?: string; theatres?: number }
/* military aircraft broadcasting over a theatre, about every half hour for 48 hours: [time, count] */
export type AirKey = 'mil' | 'fighter' | 'isr' | 'lift' | 'tanker'
export type Air48 = Partial<Record<AirKey, [string, number | null][]>>
export type GroupDetail = { z: number | null; fast: boolean; history: (number | null)[]; top: { id: string; label: string; z: number }[] }
export type Theatre = {
  generated: string; id: string; name: string; region: string; level: Level; score: number | null; standingRisk: number | null
  signals: { scored: number; total: number; strong: number }
  chance: { p: number | null; lo: number | null; hi: number | null; usual: number | null; change: [number, number] | null }
  confidence: string; context: string | null; contextChecked: string | null; spillover: boolean; parents: string[]
  center: LonLat | null; view: [LonLat, LonLat] | null; countries: string[]
  tells: Tell[]; groups: Record<Group, GroupDetail>; official: { name: string; id: string; date: string; value: string }[]
  history: [string, number | null, number | null, string][]; items: { date: string; kind: string; text: string; signal: string }[]
  events: { date: string; kind: string; text: string }[]
  aircraft48h?: Air48 | null
}
export type Signal = { id: string; label: string; group: Group; sub: string; theatre: string; z: number | null; status: string; stale: string; last: string; lagging: boolean; kind: string; why: string; url: string; event: string | null; untested?: boolean; spark: (number | null)[] }
export type Signals = { generated: string; groups: Record<Group, string>; signals: Signal[] }
/* west, south, east, north: the ground a satellite chip covers, so the map can lay it in place */
export type Bounds = [number, number, number, number]
export type MapBase = { id: string; name: string; kind: string; side: string; theatres: string[]; state: string; z: number | null; last: string; ll: LonLat; why: string; radar: number[]; thumb: string; part: string; bounds?: Bounds | null }
/* the Sentinel-2 check of an unusual fire (firereview.py): before (b), after (a) and short-wave infrared (s) chips, their dates, and the verdict */
export type FireImages = { b: string; a: string; s: string; bd: string; ad: string; v: string; bb?: Bounds }
export type MapFire = { ll: LonLat; mw: number; date: string; time: string; class: string; score: number; why: string; site: string; theatre: string; night: boolean; images?: FireImages | null }
export type MapAircraft = { ll: LonLat; call: string; class: string; t?: string; d?: string; r?: string; rt?: string; trk?: number; hex?: string; th?: string; o?: string; ct?: string; alt?: number; gs?: number; sq?: string; emergency: boolean }
export type MapShip = { ll: LonLat; name: string; k?: string; loc?: string; g?: string; d?: string; tx?: string; u?: string; flag?: string; dest?: string; spd?: number; note?: string; th?: string; trail?: LonLat[] }
/* Added October 2026 (docs/FLIGHTS.md, docs/SHIPS.md): theatre airports and diversions from the flight archive (a day behind),
   dark-ship radar cells and loitering ships from Global Fishing Watch (about five days behind). Optional in the file. */
export type MapAirport = { ll: LonLat; icao: string; name: string; theatre: string; date: string; departures: number; usual: number; divertedAway: number; divertedIn: number; turnbacks: number; holds: number; bizjets: number; bizjetsOut: number }
export type MapDiversion = { ll: LonLat; kind: 'diversion' | 'turnback'; call: string; type: string; from: string; planned: string; landed: string; time: number; date: string; theatre: string }
export type MapDark = { ll: LonLat; count: number; date: string; theatre: string }
export type MapLoiter = { ll: LonLat; name: string; flag: string; type: string; hours: number; start: string; theatre: string }
export type MapWarning = { ll: LonLat; id: string; text: string; issued: string; theatre: string }
export type MapIncident = { ll: LonLat; t?: string; d?: string; src?: string; u?: string; loc?: string; th?: string; tx?: string }
export type Pic = { src: string; date: string } | null
export type BasePart = { part: string; what: string; where: string; state: string; z: number | null; dates: string; note: string; tested: boolean; now: number | null; usual: number | null; low: number | null; high: number | null
  history: [string, number, number | null, number | null, number | null][]; marks: { date: string; before: string; objects: number; new: number | null; gone: number | null } | null; images: { marked: Pic; before: Pic } }
export type BaseFile = { generated: string; id: string; name: string; type: string; side: string; theatres: string[]; state: string; z: number | null; last: string; previous: string; ll: LonLat
  radar: number[]; why: string; about: string; note: string; mainPart: string; bounds?: Bounds | null; images: { radar: Pic; radarBefore: Pic; optical: Pic; opticalBefore: Pic }; parts: BasePart[] }
export type LiveMap = {
  generated: string; theatres: Record<string, { center: LonLat | null; view: [LonLat, LonLat] | null; countries: string[] }>
  bases: MapBase[]; fires: MapFire[]; aircraft: MapAircraft[]; squawks: MapAircraft[]; ships: MapShip[]; warnings: MapWarning[]; incidents: MapIncident[]; cities: { ll: LonLat; name: string; theatre: string }[]; chokepoints: { ll: LonLat; name: string; theatre: string }[]
  airports?: MapAirport[]; diversions?: MapDiversion[]; darkShips?: MapDark[]; loitering?: MapLoiter[]
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
export const useBase = (id: string, on = true) => useQuery({ queryKey: ['base', id], queryFn: () => get<BaseFile>(`bases/${id}.json`), enabled: on && !!id })
export type SeriesFile = { generated: string; id: string; points: [string, number | null][]; zHistory: [string, number | null][] }
export const useSeries = (id: string) => useQuery({ queryKey: ['series', id], queryFn: () => get<SeriesFile>(`signals/series/${id}.json`) })
export const useRecord = () => useQuery({ queryKey: ['record'], queryFn: () => get<RecordFile>('record.json') })

/* Images and tiles sit at the site root: img/bases/…, basemap.pmtiles */
export const asset = (src: string) => new URL(src, ROOT).href

/* Base states as basewatch.py writes them */
export const BASE_STATE: Record<string, [string, string]> = {
  out: ['Fewer than usual', 'var(--z3-text)'], in: ['More than usual', 'var(--z3-text)'], changed: ['One pass differed', 'var(--z2-text)'],
  normal: ['Usual on the latest pass', 'var(--fg3)'], optical: ['Optical images only', 'var(--fg3)'], nodata: ['No recent pass', 'var(--fg3)'],
}
export const baseState = (s: string) => BASE_STATE[s] || [s, 'var(--fg3)']

/* an aircraft in an emergency: flagged so by the source, or squawking hijack (7500), radio failure (7600) or emergency (7700) */
export const emergency = (a: MapAircraft) => a.emergency || ['7500', '7600', '7700'].includes(a.sq || '')
/* heat follows the fire score everywhere (map, lists, cards): orange from 70, faint orange from 40, grey below */
export const HEAT = { faint: 40, strong: 70 }
export const heatColour = (score: number) => score >= HEAT.strong ? 'var(--z3)' : score >= HEAT.faint ? 'color-mix(in oklab, var(--z3) 45%, var(--fg3))' : 'var(--fg3)'

/* Words and colours (text colours: the level word and base state are read as text) */
export const LEVELS: Level[] = ['Normal', 'Watch', 'Elevated', 'Critical']
export const levelVar = (l: string) => l === 'Critical' ? 'var(--crit)' : l === 'Elevated' ? 'var(--z3-text)' : l === 'Watch' ? 'var(--z2-text)' : 'var(--fg3)'
export const levelWord = (l: string) => l === 'Normal' ? 'Quiet' : l
/* "South Asia (India-Pakistan)" reads "South Asia" on the board, the map and in sentences */
export const short = (name: string) => name.replace(/\s*\(.*\)/, '')
/* a signal group's cell on the board: below 1 SD plain, then three steps of warmth */
export const groupTone = (z: number | null | undefined) => z == null || z < 1 ? 'var(--z0)' : z < 2 ? 'var(--z1)' : z < 3 ? 'var(--z2)' : 'var(--z3)'
/* feed details written before the rename still say "Timing tell" */
export const feedDetail = (d: string) => d.replace(/^Timing tell/, 'Tripwire')
export const zColor = (z: number | null | undefined) => z == null ? 'transparent' : Math.abs(z) >= 3 ? 'var(--z3)' : Math.abs(z) >= 2 ? 'var(--z2)' : Math.abs(z) >= 1 ? 'color-mix(in oklab, var(--z2) 38%, transparent)' : 'color-mix(in oklab, var(--fg3) 22%, transparent)'
/* the 0 to 100 reading as a whole number; just under a line it stays under it (49.6 reads 49, 89.7 reads 89), so a number never reads as reaching a line it has not */
export const wholeScore = (s: number) => s < 50 ? Math.min(49, Math.round(s)) : s < 90 ? Math.min(89, Math.round(s)) : Math.round(s)
export const fmtZ = (z: number | null | undefined) => z == null ? 'n/a' : (z > 0 ? '+' : z < 0 ? '−' : '') + Math.abs(z).toFixed(1)
export const parseGen = (g: string) => new Date(g.replace(' UTC', 'Z').replace(' ', 'T'))
export const shortDate = (d: string) => { const x = new Date(d + (d.length === 7 ? '-01' : '') + 'T00:00Z'); return x.toLocaleDateString('en-GB', { day: d.length === 7 ? undefined : 'numeric', month: 'short', timeZone: 'UTC' }).replace('Sept', 'Sep') }
export const daysBetween = (now: Date, d: string) => Math.round((now.getTime() - new Date(d.slice(0, 10) + 'T12:00Z').getTime()) / 864e5)
export const ago = (now: Date, d: string) => { const n = daysBetween(now, d); return n <= 0 ? 'Today' : n === 1 ? 'Yesterday' : n < 7 ? `${n} days ago` : shortDate(d.slice(0, 10)) }

/* Tripwires by their short names (the feed and the prototype's), falling back to the name the data carries */
const WIRE: Record<string, string> = { departure: 'Embassy drawdown', leave: 'Advisories raised', airlines: 'Airliners thin out', tankers: 'Tankers forward', airspace: 'Airspace closed',
  sea: 'Sea firing warnings', wave: 'Strike waves', bases: 'Bases emptying', diverted: 'Flights diverted', bizjets: 'Bizjets fly out', dark: 'Ships go dark', civil: 'Civil defence' }
export const wireName = (x: { id: string; name: string }) => WIRE[x.id] || x.name
const NUM = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve']
export const countWord = (n: number) => NUM[n] ?? String(n)

/* The theatre's summary, from its data. The line of 50 is named only while the model is off and the reading is under it
   (then it sets the level); a reading under 50 never prints as 50 (wholeScore). Otherwise the sentence gives the reading alone. */
export function summary(t: Theatre, modelActive: boolean): string {
  const s = t.score
  let a: string
  if (s == null) a = 'There is no unusual-readings number for this theatre today.'
  else if (!modelActive && s < 50) { const gap = 50 - wholeScore(s); a = `Unusual readings stand at ${wholeScore(s)} of 100, ${gap < 10 ? `${gap} ${gap === 1 ? 'point' : 'points'} below Watch` : 'far below Watch'}.` }
  else a = `Unusual readings stand at ${wholeScore(s)} of 100.`
  const on = t.tells.filter(x => x.on)
  const b = on.length ? ` ${countWord(on.length)} ${on.length === 1 ? 'tripwire' : 'tripwires'} fired this week: ${on.map(x => wireName(x).toLowerCase()).join(', ')}.` : ' No tripwire has fired this week.'
  const top = GROUPS.map(g => [g, t.groups[g]?.z ?? 0] as const).sort((x, y) => y[1] - x[1])[0]
  const c = top && top[1] >= 2 ? ` ${top[0]} carries the most pressure.` : ''
  return a + b + c
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

/* The model's three checks (record.tsx lists them) in one plain sentence, from brief.model.gates: which it has passed and which not */
export function gatesSentence(g: Gates | null, active: boolean): string {
  if (!g) return active ? 'It sets the level.' : 'Its checks have not been run yet, so it does not set the level.'
  const checks: [boolean, string][] = [[g.auc_lo_above_half, 'ranks past theatre-months better than a coin flip'], [g.bss_positive, "beats each theatre's usual rate"], [g.beats_shuffled, 'beats the same signals with their timing shuffled']]
  const yes = checks.filter(c => c[0]).map(c => c[1]), no = checks.filter(c => !c[0]).map(c => c[1])
  const list = (a: string[]) => a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]
  const passed = !no.length ? `It passes all three of its checks: it ${list(yes)}` : !yes.length ? `It has passed none of its three checks: it has not shown that it ${list(no)}` : `It ${list(yes)}, but it has not shown that it ${list(no)}`
  return active ? `${passed}. It sets the level.` : `${passed}, so it stays here and does not set the level.`
}
