import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Protocol, PMTiles } from 'pmtiles'
import { X, Flame, Plane, Ship, TriangleAlert, Satellite, ExternalLink, ImageIcon, Maximize2 } from 'lucide-react'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { feature } from 'topojson-client'
import type { FeatureCollection } from 'geojson'
import coarse from 'world-atlas/countries-110m.json'
import { levelVar, asset, baseState, shortDate, useBase, type Brief, type LiveMap, type LonLat, type Route, type MapBase, type MapFire, type MapAircraft, type MapShip, type MapWarning } from './data'
import { fireImages, baseImages, copernicusUrl, worldviewUrl, type SatImage, type Focus } from './sat'
import { baseWord, fireWord, fireColour } from './ground'
import { reducedMotion as reduced } from './settings'

/* The globe: MapLibre with the Natural Earth countries as a GeoJSON source, so it needs no tile server. Theatres are
   coloured by level through feature state; labels are HTML laid over the map with a collision pass (highest level wins). */

maplibregl.setWorkerUrl(workerUrl)   // MapLibre 6 ships its worker as a separate module; Vite copies it next to the app
const pmtiles = new Protocol(); maplibregl.addProtocol('pmtiles', pmtiles.tile)
const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()
/* world-atlas rings jump from 180° to -180° (Russia, Fiji), which the flat map draws as a line across the world: carry them on past 180° instead */
const unwrap = (ring: number[][]) => { let k = 0; return ring.map((c, i) => { if (i) { const d = c[0] - ring[i - 1][0]; if (d > 180) k -= 360; else if (d < -180) k += 360 } return [c[0] + k, c[1]] }) }
const toFC = (topo: any): FeatureCollection => {
  const fc = feature(topo, topo.objects.countries) as unknown as FeatureCollection
  fc.features = fc.features.filter(f => f.properties?.name !== 'Antarctica')
  for (const f of fc.features as any[]) {
    const g = f.geometry; if (!g) continue
    if (g.type === 'Polygon') g.coordinates = g.coordinates.map(unwrap)
    else if (g.type === 'MultiPolygon') g.coordinates = g.coordinates.map((p: number[][][]) => p.map(unwrap))
  }
  return fc
}
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

type Props = { brief: Brief; live?: LiveMap; route: Route; theme: string; padRight: number; padBottom: number; onPick: (r: Route) => void; flat?: boolean; day?: string | null; labels?: number }
type Peek = { kind: 'base'; x: MapBase } | { kind: 'fire'; x: MapFire } | { kind: 'air'; x: MapAircraft } | { kind: 'ship'; x: MapShip } | { kind: 'warn'; x: MapWarning }
const PICKABLE = ['aircraft-cluster', 'bases', 'fires', 'aircraft', 'ships', 'warnings'] as const
const PEEK_KIND: Record<string, Peek['kind']> = { bases: 'base', fires: 'fire', aircraft: 'air', ships: 'ship', warnings: 'warn' }
const BONUS: Record<string, number> = { bases: 4, fires: 3, 'aircraft-cluster': 0 }   // px: on a tie, a base or a fire wins over a passing aircraft
const coarsePointer = () => matchMedia('(pointer: coarse)').matches

export function MapView({ brief, live, route, theme, padRight, padBottom, onPick, flat = false, day = null, labels = 1 }: Props) {
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
  const peekRef = useRef(peek); peekRef.current = peek
  const selRef = useRef(sel); selRef.current = sel
  const nameRef = useRef((id: string) => th[id]?.name || id); nameRef.current = (id: string) => th[id]?.name || id
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)
  const wide = padBottom === 0

  /* satellite pictures laid on the map: the open fire's (Sentinel-2 close-ups, that day's VIIRS pass) or the open base's */
  const baseQ = useBase(selBase || '', !!selBase)
  const fire = peek?.kind === 'fire' ? peek.x : null
  const focusKey = fire ? `fire:${fire.ll.join()}:${fire.time || fire.date}` : selBase ? `base:${selBase}` : ''
  const imgs = useMemo<SatImage[]>(() => fire ? fireImages(fire) : selBase && baseQ.data ? baseImages(baseQ.data) : [], [focusKey, baseQ.data])
  const [imgKey, setImgKey] = useState('')        // '' the first picture, 'off' none
  useEffect(() => setImgKey(''), [focusKey])
  const shown = imgKey === 'off' ? null : imgs.find(i => i.key === imgKey) || imgs[0] || null
  const [big, setBig] = useState<SatImage | null>(null)
  /* the card sits bottom left; on a phone, just above the lowered sheet (the shell lowers it when a card opens) */
  const card = useRef<HTMLDivElement>(null)
  const cardBottom = wide ? 96 : 208
  useEffect(() => { if (peek && !wide) dispatchEvent(new Event('ww-peek')) }, [peek])

  /* create once */
  useEffect(() => {
    const p = paints()
    const m = new maplibregl.Map({
      container: box.current!, attributionControl: false, renderWorldCopies: false, maxPitch: 0, dragRotate: false,
      center: HOME, zoom: worldZoom(box.current!.clientWidth - padRight, box.current!.clientHeight - padBottom), minZoom: 0.6, maxZoom: 16,   // 16: a base's or a fire's satellite picture fills the screen
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
    /* One click handler, so the country under a dot never wins: the nearest base, fire, aircraft, ship or warning within a few
       pixels (more on touch) opens; a base opens its page. Only an empty click on a theatre's country, from the world view
       (zoom under 5), moves to that theatre; an empty click with a card open just closes the card. */
    const near = (pt: maplibregl.Point) => {
      const r = coarsePointer() ? 16 : 9
      const layers = PICKABLE.filter(l => m.getLayer(l))
      let best: maplibregl.MapGeoJSONFeature | null = null, bd = Infinity
      for (const f of m.queryRenderedFeatures([[pt.x - r, pt.y - r], [pt.x + r, pt.y + r]], { layers: [...layers] })) {
        const q = m.project((f.geometry as GeoJSON.Point).coordinates as [number, number]), d = Math.hypot(q.x - pt.x, q.y - pt.y) - (BONUS[f.layer.id] || 0)
        if (d < bd) { bd = d; best = f }
      }
      return best
    }
    const landTheatre = (pt: maplibregl.Point) => {
      if (m.getZoom() >= 5) return null
      const n = m.queryRenderedFeatures(pt, { layers: ['land'] })[0]?.properties?.name
      const t = n && primaryRef.current[n]
      return t && t !== selRef.current ? t : null
    }
    m.on('click', e => {
      const f = near(e.point)
      if (f) {
        const id = f.layer.id, c = (f.geometry as GeoJSON.Point).coordinates as [number, number]
        if (id === 'aircraft-cluster') {
          (m.getSource('aircraft') as maplibregl.GeoJSONSource).getClusterExpansionZoom(f.properties!.cluster_id).then(z => m.easeTo({ center: c, zoom: z + .2, duration: reduced() ? 0 : 500 }))
          return
        }
        const x = JSON.parse(f.properties!.json)
        if (id === 'bases') { setPeek(null); pick.current({ v: 'base', id: x.id }); return }
        setPeek({ kind: PEEK_KIND[id], x } as Peek)
        return
      }
      if (peekRef.current) { setPeek(null); return }
      const t = landTheatre(e.point)
      if (t) pick.current({ v: 'theatre', id: t })
    })
    /* hover, with a mouse: a pointer and a one-line label for what a click would open */
    let raf = 0
    m.on('mousemove', e => {
      if (coarsePointer()) return
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const f = near(e.point)
        let text = ''
        if (f) {
          const id = f.layer.id
          if (id === 'aircraft-cluster') text = `${f.properties!.point_count} aircraft · click to zoom in`
          else { const x = JSON.parse(f.properties!.json); text = id === 'bases' ? `${x.name.split(',')[0]} · ${baseWord(x.state, x.part)}` : id === 'fires' ? `${x.site ? 'Heat near ' + x.site : fireWord(x.class)} · ${Math.round(x.mw)} MW · ${shortDate(x.date)}`
            : id === 'aircraft' ? [x.call || x.hex || 'Military aircraft', x.t].filter(Boolean).join(' · ') : id === 'ships' ? x.name : `Navigational warning ${x.id}` }
        } else if (!peekRef.current) {
          const t = landTheatre(e.point)
          if (t) text = `Open ${nameRef.current(t)}`
        }
        m.getCanvas().style.cursor = text ? 'pointer' : ''
        setTip(text ? { x: e.point.x, y: e.point.y, text } : null)
      })
    })
    m.on('mouseout', () => { cancelAnimationFrame(raf); setTip(null); m.getCanvas().style.cursor = '' })
    m.on('movestart', () => setTip(null))
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

  /* the picture on the ground, under the live layers, with a thin outline of what it covers */
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    const edge = m.getSource('drape-edge') as maplibregl.GeoJSONSource | undefined
    if (!shown) {
      if (m.getLayer('drape')) m.setLayoutProperty('drape', 'visibility', 'none')
      edge?.setData(EMPTY)
      return
    }
    const [w, s, e, n] = shown.bounds, coordinates: [[number, number], [number, number], [number, number], [number, number]] = [[w, n], [e, n], [e, s], [w, s]]
    const src = m.getSource('drape') as maplibregl.ImageSource | undefined
    if (src) src.updateImage({ url: shown.url, coordinates })
    else {
      m.addSource('drape', { type: 'image', url: shown.url, coordinates })
      m.addLayer({ id: 'drape', type: 'raster', source: 'drape', paint: { 'raster-fade-duration': 200 } }, 'drape-edge')
    }
    m.setLayoutProperty('drape', 'visibility', 'visible')
    edge?.setData({ type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[...coordinates, coordinates[0]]] } }] })
  }, [shown?.url, ready])

  /* a fire opened (on the map or from a list): fly to its first picture */
  useEffect(() => {
    const m = map.current; if (!m || !ready || !fire) return
    const b = fireImages(fire)[0].bounds
    const padding = wide ? { top: 80, bottom: 110, left: 400, right: padRight + 70 } : { top: 116, bottom: cardBottom + (card.current?.offsetHeight || 260) + 12, left: 24, right: 24 }
    m.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding, maxZoom: 15, duration: reduced() ? 0 : 1200, essential: true })
  }, [focusKey, ready])

  /* lists outside the map (a theatre's fires) open a fire here */
  useEffect(() => {
    const f = (e: Event) => { const d = (e as CustomEvent<Focus>).detail; if (d?.kind === 'fire') setPeek({ kind: 'fire', x: d.x }) }
    addEventListener('ww-focus', f); return () => removeEventListener('ww-focus', f)
  }, [])

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
    const padding = { top: 80, bottom: padBottom + (wide ? 100 : 40), left: 40, right: padRight + 40 }   // 100: clear of the 30-day strip
    const duration = reduced() ? 0 : undefined
    const focus = route.v === 'theatre' ? route.id : route.v === 'signals' ? route.th : undefined   // Signals filtered to a theatre shows that theatre
    const b = route.v === 'base' ? live?.bases.find(x => x.id === route.id) : undefined
    if (b?.bounds && b.thumb) m.fitBounds([[b.bounds[0], b.bounds[1]], [b.bounds[2], b.bounds[3]]], { padding, maxZoom: 15, duration: duration ?? 1400, essential: true })   // its satellite picture fills the view
    else if (b) m.flyTo({ center: b.ll, zoom: basemap ? 10.5 : 8, padding, duration: duration ?? 1400, essential: true })   // without the basemap's coastline, closer than 8 shows nothing
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
        el.style.opacity = '1'; el.style.pointerEvents = kind === 'theatre' ? 'auto' : 'none'   // city and strait names never take a click meant for the dot under them
        el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`
      })
    }
    place()
    m.on('move', place); m.on('resize', place)
    return () => { m.off('move', place); m.off('resize', place) }
  }, [ready, sel, brief, live, flat, padRight, padBottom, labels])

  const zoom = (d: number) => map.current?.easeTo({ zoom: map.current.getZoom() + d, duration: reduced() ? 0 : 320 })

  return (
    <div className="absolute inset-0 overflow-hidden select-none" style={{ background: 'radial-gradient(1200px 800px at 40% 40%, color-mix(in oklab, var(--accent) 6%, var(--bg)), var(--bg))' }}>
      <div ref={box} style={{ position: 'absolute', inset: 0 }} role="region" aria-label="Map of the watched theatres. Every theatre on it is also listed in the panel." />
      <div ref={ov} className="pointer-events-none absolute inset-0" style={{ ['--lbl' as string]: labels }}>
        {brief.theatres.filter(t => t.center).map(t => (
          <button key={t.id} data-kind="theatre" data-id={t.id} data-prio={100 + (RANK[t.level] || 0) * 20 + t.tellsOn * 4 + (t.spillover ? 0 : 2)} data-lon={t.center![0]} data-lat={t.center![1]}
            onClick={() => onPick({ v: 'theatre', id: t.id })} aria-label={`${t.name}, ${t.level === 'Normal' ? 'quiet' : t.level}`}
            className="absolute left-0 top-0 -translate-x-1/2 -translate-y-1/2 transition-opacity duration-300" style={{ opacity: 0 }}>
            <span className={`flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-[3px] font-[family-name:var(--font-cond)] text-[calc(12px*var(--lbl))] font-medium backdrop-blur-md transition-colors ${sel === t.id ? 'border-accent bg-accent text-accentink' : 'border-line2 bg-[color-mix(in_oklab,var(--panel)_78%,transparent)] text-fg hover:border-accent'}`}>
              <span className="relative h-1.5 w-1.5 rounded-full" style={{ background: sel === t.id ? 'currentColor' : levelVar(t.level) }} />
              {t.name}
              {t.tellsOn > 0 && <span className="num rounded-full px-1 text-[10.5px] font-semibold" style={{ background: 'color-mix(in oklab, var(--watch) 22%, transparent)', color: sel === t.id ? 'inherit' : 'var(--watch)' }}>{t.tellsOn}</span>}
            </span>
          </button>
        ))}
        {(live?.chokepoints || []).map((c, i) => (
          <span key={'c' + i} data-kind="choke" data-prio={30} data-lon={c.ll[0]} data-lat={c.ll[1]} className="absolute left-0 top-0 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap font-[family-name:var(--font-cond)] text-[calc(11px*var(--lbl))] italic text-fg3 transition-opacity" style={{ opacity: 0 }}>{c.name}</span>
        ))}
        {(live?.cities || []).map((c, i) => (
          <span key={'ct' + i} data-kind="city" data-prio={10} data-lon={c.ll[0]} data-lat={c.ll[1]} className="absolute left-0 top-0 flex -translate-y-1/2 items-center gap-1 whitespace-nowrap font-[family-name:var(--font-cond)] text-[calc(11.5px*var(--lbl))] text-fg2 transition-opacity" style={{ opacity: 0 }}>
            <i className="h-[3px] w-[3px] rounded-full bg-fg2" />{c.name}
          </span>
        ))}
      </div>
      {tip && <div className="pointer-events-none absolute z-10 max-w-[280px] truncate rounded-md border border-line2 bg-panel/95 px-2 py-1 text-[12px] text-fg shadow-[var(--shadow)]" style={{ left: tip.x + 14, top: tip.y + 14 }}>{tip.text}</div>}
      {imgs.length > 0 && <div role="group" aria-label="Satellite picture on the map" className="absolute z-10 flex max-w-[calc(100%-32px)] items-center gap-0.5 overflow-x-auto rounded-xl border border-line bg-panel/90 p-1 text-[12px] shadow-[var(--shadow)] backdrop-blur-md" style={{ left: 16, top: wide ? 76 : 66, maxWidth: `calc(100% - ${padRight + 32}px)` }}>
        <ImageIcon size={14} className="mx-1.5 shrink-0 text-fg3" />
        {imgs.map(i => <button key={i.key} aria-pressed={shown?.key === i.key} onClick={() => setImgKey(i.key)} title={i.caption} className={`shrink-0 whitespace-nowrap rounded-lg px-2 py-1 ${shown?.key === i.key ? 'bg-accent text-accentink' : 'text-fg2 hover:bg-hover hover:text-fg'}`}>{i.label}</button>)}
        <button aria-pressed={!shown} onClick={() => setImgKey('off')} className={`shrink-0 rounded-lg px-2 py-1 ${!shown ? 'bg-hover text-fg' : 'text-fg3 hover:bg-hover hover:text-fg'}`}>Off</button>
        {shown && <span className="num shrink-0 whitespace-nowrap px-1.5 text-fg3">{shortDate(shown.date)}</span>}
      </div>}
      {peek && <PeekCard p={peek} cardRef={card} onClose={() => setPeek(null)} onPick={r => { setPeek(null); onPick(r) }} brief={brief} shown={shown} onShow={setImgKey} onEnlarge={setBig}
        style={{ left: wide ? 16 : 8, bottom: cardBottom, maxWidth: wide ? `min(360px, calc(100% - ${padRight + 32}px))` : 'calc(100% - 16px)', maxHeight: `calc(100% - ${cardBottom + (wide ? 130 : 116)}px)` }} />}
      {big && <Lightbox img={big} onClose={() => setBig(null)} />}
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
  for (const id of ['fires', 'bases', 'ships', 'warnings', 'drape-edge']) m.addSource(id, { type: 'geojson', data: EMPTY })
  m.addLayer({ id: 'drape-edge', type: 'line', source: 'drape-edge', paint: { 'line-width': 1, 'line-dasharray': [3, 2] } })
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
  m.setPaintProperty('drape-edge', 'line-color', accent)
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
function PeekCard({ p, cardRef, onClose, onPick, brief, style, shown, onShow, onEnlarge }: { p: Peek; cardRef: React.RefObject<HTMLDivElement | null>; onClose: () => void; onPick: (r: Route) => void; brief: Brief
  style: React.CSSProperties; shown: SatImage | null; onShow: (key: string) => void; onEnlarge: (i: SatImage) => void }) {
  const name = (id?: string) => brief.theatres.find(t => t.id === id)?.name || ''
  const row = 'mt-1 text-[12.5px] leading-snug text-fg2'
  let icon, title: string, sub: string, body: React.ReactNode = null, action: [string, Route] | null = null
  if (p.kind === 'base') {
    const b = p.x, [, col] = baseState(b.state)
    icon = <Satellite size={15} style={{ color: col }} />; title = b.name; sub = `${baseWord(b.state, b.part)}${b.last ? ` · last pass ${shortDate(b.last)}` : ''}`
    body = <div className="mt-2 flex gap-3">{b.thumb && <img src={asset(b.thumb)} alt="" className="h-16 w-16 shrink-0 rounded-lg object-cover" />}<p className={row}>{b.why}</p></div>
    action = ['Open base', { v: 'base', id: b.id }]
  } else if (p.kind === 'fire') {
    const f = p.x, imgs = fireImages(f), v = f.images?.v
    icon = <Flame size={15} style={{ color: fireColour(f.class) }} />; title = f.site ? `Heat near ${f.site}` : fireWord(f.class); sub = `${Math.round(f.mw)} MW · ${shortDate(f.date)}${f.time ? ' ' + f.time.slice(11, 16) + ' UTC' : ''}${f.night ? ', night' : ''} · NASA VIIRS`
    const link = 'inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-[11.5px] text-fg2 hover:bg-hover hover:text-fg'
    body = <>
      <p className={`${row} line-clamp-3`}>{f.why || fireWord(f.class)}</p>
      <div className="mt-2.5 text-[11.5px] text-fg3">{f.images ? `Sentinel-2 close-up${v === 'scar' ? ': burn scar seen' : v === 'none' ? ': no burn scar seen' : ''}, and that day's VIIRS pass` : 'That day\'s satellite pass'}</div>
      <div className="mt-1 grid grid-cols-4 gap-1.5">
        {imgs.map(i => <SatThumb key={i.key} i={i} on={shown?.key === i.key} onShow={() => shown?.key === i.key ? onEnlarge(i) : onShow(i.key)} ring={i.key === 'viirs' ? 6 : 12} />)}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <a className={link} href={copernicusUrl(f.ll, f.date)} target="_blank" rel="noreferrer">Sentinel-2 <ExternalLink size={11} /></a>
        <a className={link} href={copernicusUrl(f.ll, f.date, '6-SWIR')} target="_blank" rel="noreferrer">Infrared <ExternalLink size={11} /></a>
        <a className={link} href={worldviewUrl(f.ll, f.date)} target="_blank" rel="noreferrer">NASA Worldview <ExternalLink size={11} /></a>
      </div>
      <p className="mt-1.5 text-[10.5px] leading-snug text-fg3">Tap a picture to lay it on the map, again to enlarge. {f.images ? 'Close-ups 2.5 km across; ' : ''}VIIRS 26 km across, NASA GIBS.{f.images ? ' Contains modified Copernicus Sentinel data.' : ''}</p>
    </>
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
    <div ref={cardRef} role="dialog" aria-label={title} className="scroll-thin absolute z-10 w-[360px] overflow-y-auto rounded-xl border border-line2 bg-panel/95 p-3 shadow-[var(--shadow)] backdrop-blur-md" style={style}>
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

/* a picture in a card: the one on the map is ringed; tapping it again opens it full size */
function SatThumb({ i, on, onShow, ring }: { i: SatImage; on: boolean; onShow: () => void; ring: number }) {
  const [bad, setBad] = useState(false)
  return (
    <button onClick={onShow} title={on ? `${i.caption}. Tap again to enlarge` : i.caption} aria-pressed={on} className={`group relative overflow-hidden rounded-lg border text-left ${on ? 'border-accent ring-1 ring-accent' : 'border-line hover:border-line2'}`}>
      <span className="relative block aspect-square bg-raised">
        {bad ? <span className="grid h-full place-items-center px-1 text-center text-[10px] text-fg3">No image</span>
          : <img src={i.url} alt={i.caption} loading="lazy" onError={() => setBad(true)} className="h-full w-full object-cover" />}
        {!bad && <span className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/80 shadow-[0_0_0_1px_rgba(0,0,0,.35)]" style={{ width: `${ring * 2}%`, height: `${ring * 2}%` }} />}
        {on && <Maximize2 size={11} className="absolute right-1 top-1 text-white drop-shadow" />}
      </span>
      <span className="block truncate px-1 py-0.5 text-[10.5px] text-fg2">{i.label}</span>
    </button>
  )
}

function Lightbox({ img, onClose }: { img: SatImage; onClose: () => void }) {
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }; addEventListener('keydown', k, true); return () => removeEventListener('keydown', k, true) }, [onClose])
  return (
    <div role="dialog" aria-label={img.caption} onClick={onClose} className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4 backdrop-blur-[2px]">
      <figure onClick={e => e.stopPropagation()} className="relative max-h-full max-w-[min(92vw,900px)]">
        <img src={img.url} alt={img.caption} className="max-h-[80vh] w-auto rounded-lg" />
        <figcaption className="mt-2 text-center text-[12.5px] text-white/85">{img.caption}</figcaption>
        <button onClick={onClose} aria-label="Close" className="absolute -right-2 -top-2 grid h-8 w-8 place-items-center rounded-full bg-white text-black shadow"><X size={15} /></button>
      </figure>
    </div>
  )
}
