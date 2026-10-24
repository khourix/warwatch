import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { feature } from 'topojson-client'
import type { FeatureCollection } from 'geojson'
import coarse from 'world-atlas/countries-110m.json'
import { levelVar, type Brief, type LiveMap, type LonLat, type Route } from './data'

/* The globe: MapLibre with the Natural Earth countries as a GeoJSON source, so it needs no tile server. Theatres are
   coloured by level through feature state; labels are HTML laid over the map with a collision pass (highest level wins). */

maplibregl.setWorkerUrl(workerUrl)   // MapLibre 6 ships its worker as a separate module; Vite copies it next to the app
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

type Props = { brief: Brief; live?: LiveMap; route: Route; theme: string; padRight: number; padBottom: number; onPick: (r: Route) => void; flat?: boolean }

export function MapView({ brief, live, route, theme, padRight, padBottom, onPick, flat = false }: Props) {
  const box = useRef<HTMLDivElement>(null), ov = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const [ready, setReady] = useState(false)
  const sel = route.v === 'theatre' ? route.id : null
  const th = useMemo(() => Object.fromEntries(brief.theatres.map(t => [t.id, t])), [brief])
  const countriesOf = (id: string) => live?.theatres[id]?.countries || []
  const primary = useMemo(() => { const m: Record<string, string> = {}; if (live) for (const t of brief.theatres) { const c = live.theatres[t.id]?.countries?.[0]; if (c) m[c] = t.id } return m }, [brief, live])
  const pick = useRef(onPick); pick.current = onPick
  const primaryRef = useRef(primary); primaryRef.current = primary

  /* create once */
  useEffect(() => {
    const p = paints()
    const m = new maplibregl.Map({
      container: box.current!, attributionControl: false, renderWorldCopies: false, maxPitch: 0, dragRotate: false,
      center: HOME, zoom: worldZoom(box.current!.clientWidth - padRight, box.current!.clientHeight - padBottom), minZoom: 0.6, maxZoom: 9,
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
      setReady(true)
      import('world-atlas/countries-50m.json').then(fine => (m.getSource('countries') as maplibregl.GeoJSONSource)?.setData(toFC(fine.default)))
    })
    m.on('click', 'land', e => { const n = e.features?.[0]?.properties?.name; const t = n && primaryRef.current[n]; if (t) pick.current({ v: 'theatre', id: t }) })
    m.on('mousemove', 'land', e => { const n = e.features?.[0]?.properties?.name; m.getCanvas().style.cursor = n && primaryRef.current[n] ? 'pointer' : '' })
    m.on('mouseleave', 'land', () => { m.getCanvas().style.cursor = '' })
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [])

  /* theme */
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    const p = paints()
    m.setPaintProperty('ocean', 'background-color', p.ocean)
    m.setPaintProperty('land', 'fill-color', p.land as any)
    m.setPaintProperty('borders', 'line-color', p.border)
    m.setPaintProperty('watched', 'line-color', p.accent)
    m.setPaintProperty('selected', 'line-color', p.accent)
  }, [theme, ready])

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
    if (focus) {
      const v = live?.theatres[focus]?.view, c = th[focus]?.center
      if (v) m.fitBounds([v[0], v[1]], { padding, maxZoom: 6, duration: duration ?? 1100, essential: true })
      else if (c) m.flyTo({ center: c, zoom: 4, padding, duration, essential: true })
    } else {
      const w = m.getContainer().clientWidth - padRight, h = m.getContainer().clientHeight - padBottom
      m.flyTo({ center: HOME, zoom: worldZoom(w, h), padding: { top: 0, left: 0, bottom: padBottom, right: padRight }, duration: duration ?? 1200, essential: true })
    }
  }, [route, ready, padRight, padBottom, live])

  /* labels: positioned every frame the camera moves */
  useEffect(() => {
    const m = map.current; if (!m || !ready) return
    const place = () => {
      const els = Array.from(ov.current?.children || []) as HTMLElement[]
      const c = m.getCenter(), center: LonLat = [c.lng, c.lat], z = m.getZoom(), globe = !flat
      const placed: number[][] = [], W = m.getContainer().clientWidth - padRight
      els.map(el => ({ el, pr: el.dataset.id === sel ? 1e3 : +(el.dataset.prio || 0) })).sort((a, b) => b.pr - a.pr).forEach(({ el }) => {
        const ll: LonLat = [+el.dataset.lon!, +el.dataset.lat!], kind = el.dataset.kind!
        const minZ = kind === 'city' ? 4.2 : kind === 'choke' ? 3.2 : 0
        const show = (!globe || dist(ll, center) < 78) && z >= minZ && (kind !== 'theatre' || z < 6.5 || el.dataset.id === sel)
        if (!show) { el.style.opacity = '0'; el.style.pointerEvents = 'none'; return }
        const p = m.project(ll)
        const w = el.offsetWidth || 60, h = el.offsetHeight || 18
        const x0 = kind === 'city' ? p.x : p.x - w / 2, y0 = p.y - h / 2, r = [x0 - 3, y0 - 2, x0 + w + 3, y0 + h + 2]
        const cut = (r[0] < 0 || r[2] > W) && el.dataset.id !== sel      // a label running off the edge reads as broken; the panel lists it anyway
        if (cut || placed.some(q => r[0] < q[2] && r[2] > q[0] && r[1] < q[3] && r[3] > q[1])) { el.style.opacity = '0'; el.style.pointerEvents = 'none'; return }
        placed.push(r)
        el.style.opacity = '1'; el.style.pointerEvents = 'auto'
        el.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`
      })
    }
    place()
    m.on('move', place); m.on('resize', place)
    return () => { m.off('move', place); m.off('resize', place) }
  }, [ready, sel, brief, live, flat, padRight])

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
          <span key={'c' + i} data-kind="choke" data-prio={30} data-lon={c.ll[0]} data-lat={c.ll[1]} className="absolute left-0 top-0 -translate-x-1/2 whitespace-nowrap font-[family-name:var(--font-cond)] text-[11px] italic text-fg3 transition-opacity" style={{ opacity: 0 }}>{c.name}</span>
        ))}
        {(live?.cities || []).map((c, i) => (
          <span key={'ct' + i} data-kind="city" data-prio={10} data-lon={c.ll[0]} data-lat={c.ll[1]} className="absolute left-0 top-0 flex -translate-y-1/2 items-center gap-1 whitespace-nowrap font-[family-name:var(--font-cond)] text-[11.5px] text-fg2 transition-opacity" style={{ opacity: 0 }}>
            <i className="h-[3px] w-[3px] rounded-full bg-fg2" />{c.name}
          </span>
        ))}
      </div>
      <div className="absolute flex flex-col overflow-hidden rounded-xl border border-line bg-panel/80 shadow-[var(--shadow)] backdrop-blur-md" style={{ right: padRight + 16, bottom: padBottom + 16 }}>
        <button aria-label="Zoom in" onClick={() => zoom(1)} className="grid h-9 w-9 place-items-center text-fg2 hover:bg-hover hover:text-fg">+</button>
        <button aria-label="Zoom out" onClick={() => zoom(-1)} className="grid h-9 w-9 place-items-center border-t border-line text-fg2 hover:bg-hover hover:text-fg">−</button>
      </div>
    </div>
  )
}
