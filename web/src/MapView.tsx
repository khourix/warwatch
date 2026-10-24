import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol, PMTiles } from 'pmtiles'
import { X, Flame, Plane, Ship, TriangleAlert, Satellite } from 'lucide-react'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { feature } from 'topojson-client'
import type { FeatureCollection } from 'geojson'
import coarse from 'world-atlas/countries-110m.json'
import { levelVar, asset, baseState, shortDate, type Brief, type LiveMap, type LonLat, type Route, type MapBase, type MapFire, type MapAircraft, type MapShip, type MapWarning } from './data'
import { baseWord, fireWord, fireColour } from './ground'

/* The globe: MapLibre with the Natural Earth countries as a GeoJSON source, so it needs no tile server. Theatres are
   coloured by level through feature state; labels are HTML laid over the map with a collision pass (highest level wins). */

maplibregl.setWorkerUrl(workerUrl)   // MapLibre 6 ships its worker as a separate module; Vite copies it next to the app
const pmtiles = new Protocol(); maplibregl.addProtocol('pmtiles', pmtiles.tile)
const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()
const toFC = (topo: any): FeatureCollection => { const fc = feature(topo, topo.objects.countries) as unknown as FeatureCollection; fc.features = fc.features.filter(f => f.properties?.name !== 'Antarctica'); return fc }
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches
export const HOME: LonLat = [42, 24]   // decision 3: the world view is a globe centred on the Middle East
const RANK: Record<string, number> = { Normal: 0, Watch: 1, Elevated: 2, Critical: 3 }

/* hex colour a mixed into b at weight w (0..1) */
function mix(a: string, b: string, w: number) {
  const p = (h: string) => { const x = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(x.slice(i, i + 2), 16)) }
  const A = p(a), B = p(b)
  return '#' + A.map((v, i) => Math.round(v * w + B[i] * (1 - w)).toString(16).padStart(2, '0')).join('')
}
function paints() {
  const land = css('--land'), land2 = css('--land-2')
  return {
    land: ['case',
      ['==', ['feature-state', 'lv'], 3], mix(css('--crit'), land, .55),
      ['==', ['feature-state', 'lv'], 2], mix(css('--elev'), land, .5),
      ['==', ['feature-state', 'lv'], 1], mix(css('--watch'), land, .42),
      ['boolean', ['feature-state', 'th'], false], land2, land],
    border: css('--border'), accent: css('--accent'), ocean: css('--ocean'),
  }
}

function worldZoom(w: number, h: number) {
  const R = Math.max(80, Math.min(w, h) * .43)   // globe radius in px, as in the prototype; never NaN on a zero-size first layout
  return Math.max(0, Math.log2(2 * Math.PI * R / 512))
}
const dist = (a: LonLat, b: LonLat) => {   // great-circle angle in degrees
  const r = Math.PI / 180, [l1, p1] = [a[0] * r, a[1] * r], [l2, p2] = [b[0] * r, b[1] * r]
  return Math.acos(Math.min(1, Math.sin(p1) * Math.sin(p2) + Math.cos(p1) * Math.cos(p2) * Math.cos(l1 - l2))) / r
}

type Props = { brief: Brief; live?: LiveMap; route: Route; theme: string; padRight: number; padBottom: number; onPick: (r: Route) => void; flat?: boolean; day?: string | null }
type Peek = { kind: 'base'; x: MapBase } | { kind: 'fire'; x: MapFire } | { kind: 'air'; x: MapAircraft } | { kind: 'ship'; x: MapShip } | { kind: 'warn'; x: MapWarning }

export function MapView({ brief, live, route, theme, padRight, padBottom, onPick, flat = false, day = null }: Props) {
  const box = useRef<HTMLDivElement>(null), ov = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const [ready, setReady] = useState(false)
  const sel = route.v === 'theatre' ? route.id : null
  const th = useMemo(() => Object.fromEntries(brief.theatres.map(t => [t.id, t])), [brief])
  const countriesOf = (id: string) => live?.theatres[id]?.countries || []
  const primary = useMemo(() => { const m: Record<string, string> = {}; if (live) for (const t of brief.theatres) { const c = live.theatres[t.id]?.countries?.[0]; if (c) m[c] = t.id } return m }, [brief, live])
  const pick = useRef(onPick); pick.current = onPick
  const [peek, setPeek] = useState<Peek | null>(null)
  const [basemap, setBasemap] = useState(false)
  const selBase = route.v === 'base' ? route.id : null
  const primaryRef = useRef(primary); primaryRef.current = primary

  /* create once */
  useEffect(() => {
    const p = paints()
    const m = new maplibregl.Map({
      container: box.current!, attributionControl: false, renderWorldCopies: false, maxPitch: 0, dragRotate: false,
      center: HOME, zoom: worldZoom(box.current!.clientWidth - padRight, box.current!.clientHeight - padBottom), minZoom: 0.6, maxZoom: 13,
      style: {
        version: 8, projection: { type: flat ? 'mercator' : 'globe' },
        sources: { countries: { type: 'geojson', data: toFC(coarse), promoteId: 'name' } },
        layers: [
          { id: 'ocean', type: 'background', paint: { 'background-color': p.ocean } },
          { id: 'land', type: 'fill', source: 'countries', paint: { 'fill-color': p.land as any } },
          { id: 'borders', type: 'line', source: 'countries', paint: { 'line-color': p.border, 'line-width': .6 } },
          { id: 'watched', type: 'line', source: 'countries', paint: { 'line-color': p.accent, 'line-width': 1, 'line-dasharray': [2, 2], 'line-opacity': ['case', ['boolean', ['feature-state', 'w'], false], .6, 0] } },
          { id: 'selected', type: 'line', source: 'countries', paint: { 'line-color': p.accent, 'line-width': 1.8, 'line-opacity': ['case', ['boolean', ['feature-state', 'sel'], false], 1, 0] } },
        ],
      },
    })
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Natural Earth' }), 'bottom-left')
    m.on('load', () => {
      addIcons(m)
      addLiveLayers(m)
      tryBasemap(m).then(ok => setBasemap(ok))
      setReady(true)
      import('world-atlas/countries-50m.json').then(fine => (m.getSource('countries') as maplibregl.GeoJSONSource)?.setData(toFC(fine.default)))
    })
    m.on('click', 'land', e => { const n = e.features?.[0]?.properties?.name; const t = n && primaryRef.current[n]; if (t) pick.current({ v: 'theatre', id: t }) })
    m.on('mousemove', 'land', e => { const n = e.features?.[0]?.properties?.name; m.getCanvas().style.cursor = n && primaryRef.current[n] ? 'pointer' : '' })
    m.on('mouseleave', 'land', () => { m.getCanvas().style.cursor = '' })
    for (const [layer, kind] of [['bases', 'base'], ['fires', 'fire'], ['aircraft', 'air'], ['ships', 'ship'], ['warnings', 'warn']] as const) {
      m.on('click', layer, e => { const f = e.features?.[0]; if (f) { e.preventDefault(); setPeek({ kind, x: JSON.parse(f.properties!.json) } as Peek) } })
      m.on('mouseenter', layer, () => { m.getCanvas().style.cursor = 'pointer' })
      m.on('mouseleave', layer, () => { m.getCanvas().style.cursor = '' })
    }
    m.on('click', e => { if (!e.defaultPrevented && !m.queryRenderedFeatures(e.point, { layers: ['bases', 'fires', 'aircraft', 'ships', 'warnings'] }).length) setPeek(null) })
    map.current = m
    if (new URLSearchParams(location.search).has('debug')) (window as any).__map = m   // for the browser checks
    return () => { m.remove(); map.current = null }
  }, [])

  /* theme: repaint when <html data-theme> actually changes (the switch can land inside a view transition, after this renders) */
  const [themeTick, setThemeTick] = useState(0)
  useEffect(() => {
    const o = new MutationObserver(() => setThemeTick(t => t + 1))
    o.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => o.disconnect()
  }, [])
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    const p = paints()
    m.setPaintProperty('ocean', 'background-color', p.ocean)
    m.setPaintProperty('land', 'fill-color', p.land as any)
    m.setPaintProperty('borders', 'line-color', p.border)
    m.setPaintProperty('watched', 'line-color', p.accent)
    m.setPaintProperty('selected', 'line-color', p.accent)
    paintLive(m)
    if (basemap) paintBasemap(m)
  }, [theme, themeTick, ready, basemap])

  /* live layers: fires, bases, aircraft, ships, warnings. A day picked on the 30-day strip shows that day's fires and base passes only. */
  useEffect(() => {
    const m = map.current; if (!m || !ready || !live) return
    const pt = (ll: LonLat, x: object, extra: object = {}) => ({ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: ll }, properties: { json: JSON.stringify(x), ...extra } })
    const fc = (f: any[]) => ({ type: 'FeatureCollection' as const, features: f })
    const set = (id: string, d: any) => (m.getSource(id) as maplibregl.GeoJSONSource | undefined)?.setData(d)
    set('fires', fc(live.fires.filter(f => !day || f.date === day).map(f => pt(f.ll, f, { mw: f.mw, c: f.class, hot: f.class === 'anom' || f.class === 'hot' ? 1 : 0 }))))
    set('bases', fc(live.bases.filter(b => !day || b.last === day).map(b => pt(b.ll, b, { id: b.id, st: b.state, hi: ['out', 'in', 'changed'].includes(b.state) ? 1 : 0 }))))
    set('aircraft', fc(day ? [] : [...live.aircraft, ...live.squawks].map(a => pt(a.ll, a, { trk: a.trk ?? 0, em: a.emergency || !!a.sq ? 1 : 0 }))))
    set('ships', fc(day ? [] : live.ships.map(x => pt(x.ll, x))))
    set('warnings', fc(day ? [] : live.warnings.map(x => pt(x.ll, x))))
  }, [live, ready, day])

  /* the open base is drawn larger */
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    m.setLayoutProperty('bases', 'icon-size', ['case', ['==', ['get', 'id'], selBase || ''], 1.5, ['==', ['get', 'hi'], 1], 1, .8])
    if (selBase) setPeek(null)
  }, [selBase, ready])

  /* flat or globe (Settings, PR 5) */
  useEffect(() => { const m = map.current; if (m && ready) m.setProjection({ type: flat ? 'mercator' : 'globe' }) }, [flat, ready])

  /* levels and the selected theatre, as feature state */
  useEffect(() => {
    const m = map.current; if (!m || !ready || !live) return
    m.removeFeatureState({ source: 'countries' })
    for (const t of brief.theatres) {
      const cs = countriesOf(t.id)
      cs.forEach((c, i) => {
        const prev = m.getFeatureState({ source: 'countries', id: c }) as any
        m.setFeatureState({ source: 'countries', id: c }, { th: true, lv: i === 0 ? Math.max(prev?.lv || 0, RANK[t.level] || 0) : prev?.lv || 0 })
      })
    }
    if (sel) countriesOf(sel).forEach((c, i) => m.setFeatureState({ source: 'countries', id: c }, i === 0 ? { sel: true } : { w: true }))
  }, [brief, live, sel, ready])

  /* camera */
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    const padding = { top: 60, bottom: padBottom + 40, left: 40, right: padRight + 40 }
    const duration = reduced() ? 0 : undefined
    const focus = route.v === 'theatre' ? route.id : route.v === 'signals' ? route.th : undefined   // Signals filtered to a theatre shows that theatre
    const b = route.v === 'base' ? live?.bases.find(x => x.id === route.id) : undefined
    if (b) m.flyTo({ center: b.ll, zoom: basemap ? 10.5 : 8, padding, duration: duration ?? 1400, essential: true })   // without the basemap's coastline, closer than 8 shows nothing
    else if (focus) {
      const v = live?.theatres[focus]?.view, c = th[focus]?.center
      if (v) m.fitBounds([v[0], v[1]], { padding, maxZoom: 6, duration: duration ?? 1100, essential: true })
      else if (c) m.flyTo({ center: c, zoom: 4, padding, duration, essential: true })
    } else if (route.v !== 'base') {
      const w = m.getContainer().clientWidth - padRight, h = m.getContainer().clientHeight - padBottom
      m.flyTo({ center: HOME, zoom: worldZoom(w, h), padding: { top: 0, left: 0, bottom: padBottom, right: padRight }, duration: duration ?? 1200, essential: true })
    }
  }, [route, ready, padRight, padBottom, live, route.v === 'base' && basemap])

  /* labels: positioned every frame the camera moves */
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    const place = () => {
      const els = Array.from(ov.current?.children || []) as HTMLElement[]
      const c = m.getCenter(), center: LonLat = [c.lng, c.lat], z = m.getZoom(), globe = !flat
      const placed: number[][] = [], W = m.getContainer().clientWidth - padRight, Hb = m.getContainer().clientHeight - (padBottom || 84)   // 84: the 30-day strip
      els.map(el => ({ el, pr: el.dataset.id === sel ? 1e3 : +(el.dataset.prio || 0) })).sort((a, b) => b.pr - a.pr).forEach(({ el }) => {
        const ll: LonLat = [+el.dataset.lon!, +el.dataset.lat!], kind = el.dataset.kind!
        const minZ = kind === 'city' ? 4.2 : kind === 'choke' ? 3.2 : 0
        const show = (!globe || dist(ll, center) < 78) && z >= minZ && (kind !== 'theatre' || z < 6.5 || el.dataset.id === sel)
        if (!show) { el.style.opacity = '0'; el.style.pointerEvents = 'none'; return }
        const p = m.project(ll)
        const w = el.offsetWidth || 60, h = el.offsetHeight || 18
        const x0 = kind === 'city' ? p.x : p.x - w / 2, y0 = p.y - h / 2, r = [x0 - 3, y0 - 2, x0 + w + 3, y0 + h + 2]
        const cut = (r[0] < 0 || r[2] > W || r[3] > Hb) && el.dataset.id !== sel      // a label running off the edge reads as broken; the panel lists it anyway
        if (cut || placed.some(q => r[0] < q[2] && r[2] > q[0] && r[1] < q[3] && r[3] > q[1])) { el.style.opacity = '0'; el.style.pointerEvents = 'none'; return }
        placed.push(r)
        el.style.opacity = '1'; el.style.pointerEvents = 'auto'
        el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`
      })
    }
    place()
    m.on('move', place); m.on('resize', place)
    return () => { m.off('move', place); m.off('resize', place) }
  }, [ready, sel, brief, live, flat, padRight, padBottom])

  const zoom = (d: number) => map.current?.easeTo({ zoom: map.current.getZoom() + d, duration: reduced() ? 0 : 320 })

  return (
    <div className="absolute inset-0 overflow-hidden select-none" style={{ background: 'radial-gradient(1200px 800px at 40% 40%, color-mix(in oklab, var(--accent) 6%, var(--bg)), var(--bg))' }}>
      <div ref={box} style={{ position: 'absolute', inset: 0 }} role="region" aria-label="Map of the watched theatres. Every theatre on it is also listed in the panel." />
      <div ref={ov} className="pointer-events-none absolute inset-0">
        {brief.theatres.filter(t => t.center).map(t => (
          <button key={t.id} data-kind="theatre" data-id={t.id} data-prio={100 + (RANK[t.level] || 0) * 20 + t.tellsOn * 4 + (t.spillover ? 0 : 2)} data-lon={t.center![0]} data-lat={t.center![1]}
            onClick={() => onPick({ v: 'theatre', id: t.id })} aria-label={`${t.name}, ${t.level === 'Normal' ? 'quiet' : t.level}`}
            className="absolute left-0 top-0 -translate-x-1/2 -translate-y-1/2 transition-opacity duration-300" style={{ opacity: 0 }}>
            <span className={`flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-[3px] font-[family-name:var(--font-cond)] text-[12px] font-medium backdrop-blur-md transition-colors ${sel === t.id ? 'border-accent bg-accent text-accentink' : 'border-line2 bg-[color-mix(in_oklab,var(--panel)_78%,transparent)] text-fg hover:border-accent'}`}>
              <span className="relative h-1.5 w-1.5 rounded-full" style={{ background: sel === t.id ? 'currentColor' : levelVar(t.level) }} />
              {t.name}
              {t.tellsOn > 0 && <span className="num rounded-full px-1 text-[10.5px] font-semibold" style={{ background: 'color-mix(in oklab, var(--watch) 22%, transparent)', color: sel === t.id ? 'inherit' : 'var(--watch)' }}>{t.tellsOn}</span>}
            </span>
          </button>
        ))}
        {(live?.chokepoints || []).map((c, i) => (
          <span key={'c' + i} data-kind="choke" data-prio={30} data-lon={c.ll[0]} data-lat={c.ll[1]} className="absolute left-0 top-0 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap font-[family-name:var(--font-cond)] text-[11px] italic text-fg3 transition-opacity" style={{ opacity: 0 }}>{c.name}</span>
        ))}
        {(live?.cities || []).map((c, i) => (
          <span key={'ct' + i} data-kind="city" data-prio={10} data-lon={c.ll[0]} data-lat={c.ll[1]} className="absolute left-0 top-0 flex -translate-y-1/2 items-center gap-1 whitespace-nowrap font-[family-name:var(--font-cond)] text-[11.5px] text-fg2 transition-opacity" style={{ opacity: 0 }}>
            <i className="h-[3px] w-[3px] rounded-full bg-fg2" />{c.name}
          </span>
        ))}
      </div>
      {peek && <PeekCard p={peek} onClose={() => setPeek(null)} onPick={r => { setPeek(null); onPick(r) }} brief={brief} style={{ left: 16, bottom: padBottom + (padBottom ? 16 : 96), maxWidth: `min(340px, calc(100% - ${padRight + 96}px))` }} />}
      <div className="absolute flex flex-col overflow-hidden rounded-xl border border-line bg-panel/80 shadow-[var(--shadow)] backdrop-blur-md" style={{ right: padRight + 16, bottom: padBottom + (padBottom ? 16 : 96) }}>
        <button aria-label="Zoom in" onClick={() => zoom(1)} className="grid h-9 w-9 place-items-center text-fg2 hover:bg-hover hover:text-fg">+</button>
        <button aria-label="Zoom out" onClick={() => zoom(-1)} className="grid h-9 w-9 place-items-center border-t border-line text-fg2 hover:bg-hover hover:text-fg">−</button>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- live layers */
/* Shapes drawn once on a canvas and registered as SDF icons, so one image takes any colour (and the theme can recolour it). */
function addIcons(m: maplibregl.Map) {
  const make = (name: string, size: number, draw: (c: CanvasRenderingContext2D, s: number) => void) => {
    const cv = document.createElement('canvas'); cv.width = cv.height = size
    const c = cv.getContext('2d')!; c.fillStyle = '#fff'; c.strokeStyle = '#fff'; draw(c, size)
    m.addImage(name, c.getImageData(0, 0, size, size), { sdf: true, pixelRatio: 2 })
  }
  make('diamond', 32, (c, s) => { c.lineWidth = 3.5; c.beginPath(); c.moveTo(s / 2, 4); c.lineTo(s - 4, s / 2); c.lineTo(s / 2, s - 4); c.lineTo(4, s / 2); c.closePath(); c.stroke() })
  make('diamond-fill', 32, (c, s) => { c.beginPath(); c.moveTo(s / 2, 3); c.lineTo(s - 3, s / 2); c.lineTo(s / 2, s - 3); c.lineTo(3, s / 2); c.closePath(); c.fill() })
  make('arrow', 32, (c, s) => { c.beginPath(); c.moveTo(s / 2, 3); c.lineTo(s - 7, s - 5); c.lineTo(s / 2, s - 10); c.lineTo(7, s - 5); c.closePath(); c.fill() })
  make('boat', 32, (c, s) => { c.beginPath(); c.moveTo(s / 2, 4); c.lineTo(s - 9, s / 2); c.lineTo(s - 9, s - 5); c.lineTo(9, s - 5); c.lineTo(9, s / 2); c.closePath(); c.fill() })
  make('warn', 32, (c, s) => { c.lineWidth = 3; c.beginPath(); c.moveTo(s / 2, 4); c.lineTo(s - 4, s - 5); c.lineTo(4, s - 5); c.closePath(); c.stroke() })
}
const EMPTY = { type: 'FeatureCollection' as const, features: [] }
function addLiveLayers(m: maplibregl.Map) {
  for (const id of ['fires', 'bases', 'ships', 'warnings']) m.addSource(id, { type: 'geojson', data: EMPTY })
  m.addSource('aircraft', { type: 'geojson', data: EMPTY, cluster: true, clusterMaxZoom: 4, clusterRadius: 28 })
  m.addLayer({ id: 'fires', type: 'circle', source: 'fires', paint: {} })
  m.addLayer({ id: 'warnings', type: 'symbol', source: 'warnings', minzoom: 3, layout: { 'icon-image': 'warn', 'icon-size': .8, 'icon-allow-overlap': true }, paint: {} })
  m.addLayer({ id: 'ships', type: 'symbol', source: 'ships', minzoom: 3, layout: { 'icon-image': 'boat', 'icon-size': .75, 'icon-allow-overlap': true }, paint: {} })
  m.addLayer({ id: 'aircraft-cluster', type: 'circle', source: 'aircraft', filter: ['has', 'point_count'], paint: {} })
  m.addLayer({ id: 'aircraft', type: 'symbol', source: 'aircraft', filter: ['!', ['has', 'point_count']], layout: { 'icon-image': 'arrow', 'icon-size': .7, 'icon-rotate': ['get', 'trk'], 'icon-rotation-alignment': 'map', 'icon-allow-overlap': true }, paint: {} })
  // changed bases show from the world view; the other 150 from zoom 3.5, so the globe is not a field of diamonds
  m.addLayer({ id: 'bases', type: 'symbol', source: 'bases', filter: ['any', ['==', ['get', 'hi'], 1], ['>=', ['zoom'], 3.5]],
    layout: { 'icon-image': ['case', ['==', ['get', 'hi'], 1], 'diamond-fill', 'diamond'], 'icon-size': ['case', ['==', ['get', 'hi'], 1], 1, .8], 'icon-allow-overlap': true, 'symbol-sort-key': ['-', 0, ['get', 'hi']] }, paint: {} })
  paintLive(m)
}
function paintLive(m: maplibregl.Map) {
  const elev = css('--elev'), watch = css('--watch'), fg3 = css('--fg-3'), fg2 = css('--fg-2'), accent = css('--accent'), panel = css('--panel')
  m.setPaintProperty('fires', 'circle-radius', ['interpolate', ['linear'], ['sqrt', ['get', 'mw']], 1, 2.5, 10, 5, 30, 9])
  m.setPaintProperty('fires', 'circle-color', ['case', ['==', ['get', 'hot'], 1], elev, ['==', ['get', 'c'], 'unex'], watch, fg3])
  m.setPaintProperty('fires', 'circle-opacity', ['case', ['==', ['get', 'hot'], 1], .95, .6])
  m.setPaintProperty('fires', 'circle-stroke-color', panel)
  m.setPaintProperty('fires', 'circle-stroke-width', 1)
  m.setPaintProperty('bases', 'icon-color', ['match', ['get', 'st'], ['out', 'in'], elev, 'changed', watch, fg2])
  m.setPaintProperty('aircraft', 'icon-color', ['case', ['==', ['get', 'em'], 1], elev, accent])
  m.setPaintProperty('aircraft-cluster', 'circle-color', accent)
  m.setPaintProperty('aircraft-cluster', 'circle-opacity', .35)
  m.setPaintProperty('aircraft-cluster', 'circle-radius', ['interpolate', ['linear'], ['get', 'point_count'], 2, 6, 50, 16])
  m.setPaintProperty('ships', 'icon-color', fg2)
  m.setPaintProperty('warnings', 'icon-color', watch)
}

/* ---------------------------------------------------------------- basemap (optional) */
/* basemap.pmtiles is cut monthly by the workflow from the Protomaps world build (OpenStreetMap, z0 to 6). When it is there,
   its water draws over the coarse Natural Earth coastline and its roads and towns show from zoom 6. When it is not, the map
   stays as it is. */
async function tryBasemap(m: maplibregl.Map) {
  const url = asset('basemap.pmtiles')
  try {
    const p = new PMTiles(url)
    const h = await p.getHeader()
    pmtiles.add(p)
    m.addSource('bm', { type: 'vector', url: 'pmtiles://' + url, attribution: '<a href="https://openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>, <a href="https://protomaps.com" target="_blank" rel="noreferrer">Protomaps</a>', maxzoom: h.maxZoom })
    m.addLayer({ id: 'bm-urban', type: 'fill', source: 'bm', 'source-layer': 'landuse', minzoom: 6, filter: ['in', ['get', 'kind'], ['literal', ['residential', 'industrial', 'commercial', 'military']]], paint: {} }, 'borders')
    m.addLayer({ id: 'bm-water', type: 'fill', source: 'bm', 'source-layer': 'water', paint: {} }, 'borders')
    m.addLayer({ id: 'bm-roads', type: 'line', source: 'bm', 'source-layer': 'roads', minzoom: 5, filter: ['in', ['get', 'kind'], ['literal', ['highway', 'major']]], paint: {} }, 'borders')
    paintBasemap(m)
    return true
  } catch {
    return false   // no basemap in this deploy (local dev, or the monthly cut failed): the Natural Earth map is complete on its own
  }
}
function paintBasemap(m: maplibregl.Map) {
  if (!m.getLayer('bm-water')) return
  m.setPaintProperty('bm-water', 'fill-color', css('--ocean'))
  m.setPaintProperty('bm-urban', 'fill-color', css('--land-2'))
  m.setPaintProperty('bm-urban', 'fill-opacity', .6)
  m.setPaintProperty('bm-roads', 'line-color', css('--border'))
  m.setPaintProperty('bm-roads', 'line-width', ['interpolate', ['linear'], ['zoom'], 5, .3, 10, 1.2])
}

/* ---------------------------------------------------------------- peek cards */
function PeekCard({ p, onClose, onPick, brief, style }: { p: Peek; onClose: () => void; onPick: (r: Route) => void; brief: Brief; style: React.CSSProperties }) {
  const name = (id?: string) => brief.theatres.find(t => t.id === id)?.name || ''
  const row = 'mt-1 text-[12.5px] leading-snug text-fg2'
  let icon, title: string, sub: string, body: React.ReactNode = null, action: [string, Route] | null = null
  if (p.kind === 'base') {
    const b = p.x, [, col] = baseState(b.state)
    icon = <Satellite size={15} style={{ color: col }} />; title = b.name; sub = `${baseWord(b.state, b.part)}${b.last ? ` · last pass ${shortDate(b.last)}` : ''}`
    body = <div className="mt-2 flex gap-3">{b.thumb && <img src={asset(b.thumb)} alt="" className="h-16 w-16 shrink-0 rounded-lg object-cover" />}<p className={row}>{b.why}</p></div>
    action = ['Open base', { v: 'base', id: b.id }]
  } else if (p.kind === 'fire') {
    const f = p.x
    icon = <Flame size={15} style={{ color: fireColour(f.class) }} />; title = f.site ? `Heat near ${f.site}` : fireWord(f.class); sub = `${Math.round(f.mw)} MW · ${shortDate(f.date)}${f.night ? ', night' : ''} · NASA VIIRS`
    body = <p className={row}>{f.why || fireWord(f.class)}</p>
    if (f.theatre) action = [`Open ${name(f.theatre)}`, { v: 'theatre', id: f.theatre, tab: 'ground' }]
  } else if (p.kind === 'air') {
    const a = p.x
    icon = <Plane size={15} className="text-accent" />; title = a.call || a.hex || 'Military aircraft'; sub = [a.t, a.o || a.ct].filter(Boolean).join(' · ')
    body = <p className={row}>{[a.alt != null && `${Math.round(a.alt / 100) * 100} ft`, a.gs != null && `${Math.round(a.gs)} kt`, a.sq && `squawk ${a.sq}`].filter(Boolean).join(' · ') || 'Seen on ADS-B at the last run.'}</p>
    if (a.th && name(a.th)) action = [`Open ${name(a.th)}`, { v: 'theatre', id: a.th, tab: 'ground' }]
  } else if (p.kind === 'ship') {
    const x = p.x
    icon = <Ship size={15} className="text-fg2" />; title = x.name; sub = [x.k, x.flag, x.loc].filter(Boolean).join(' · ')
    body = <p className={row}>{x.note || x.tx || (x.dest ? `Bound for ${x.dest}` : '')}</p>
    if (x.th && name(x.th)) action = [`Open ${name(x.th)}`, { v: 'theatre', id: x.th, tab: 'ground' }]
  } else {
    const w = p.x
    icon = <TriangleAlert size={15} style={{ color: 'var(--watch)' }} />; title = `Navigational warning ${w.id}`; sub = w.issued ? `Issued ${w.issued}` : 'NGA'
    body = <p className={`${row} line-clamp-5`}>{w.text}</p>
    if (w.theatre && name(w.theatre)) action = [`Open ${name(w.theatre)}`, { v: 'theatre', id: w.theatre, tab: 'ground' }]
  }
  return (
    <div role="dialog" aria-label={title} className="absolute z-10 w-[340px] rounded-xl border border-line2 bg-panel/95 p-3 shadow-[var(--shadow)] backdrop-blur-md" style={style}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5">{icon}</span>
        <div className="min-w-0 flex-1"><div className="truncate text-[13.5px] font-medium">{title}</div><div className="truncate text-[11.5px] text-fg3">{sub}</div></div>
        <button onClick={onClose} aria-label="Close" className="-mr-1 -mt-1 grid h-7 w-7 place-items-center rounded-md text-fg3 hover:bg-hover hover:text-fg"><X size={14} /></button>
      </div>
      {body}
      {action && <button onClick={() => onPick(action![1])} className="mt-2.5 rounded-lg bg-accent px-3 py-1.5 text-[12.5px] font-medium text-accentink">{action[0]}</button>}
    </div>
  )
}
