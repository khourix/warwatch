/* The map's layers: which marks it draws. The choice is kept in this browser and, when it differs from the usual set, in the
   address (?l=bases.fires), so a copied link reopens the map as it was. Kept apart from MapView so the shell can hold the choice
   before the map library has loaded. */

export type Layer = 'bases' | 'fires' | 'aircraft' | 'ships' | 'incidents' | 'dark' | 'airports' | 'warnings'
/* key, name, the map layers it switches, what it shows. Aircraft carry the diverted and turned-back flights, and dark ships the
   loitering carrier vessels (both from Global Fishing Watch). Airports and sea warnings start hidden, as approved. */
export const LAYERS: [Layer, string, string[], string][] = [
  ['bases', 'Bases', ['bases', 'bases-halo'], 'Bases watched on satellite radar'],
  ['fires', 'Heat', ['fires'], 'Fires and heat from NASA VIIRS: orange when unusual, faint when somewhat unusual, grey otherwise'],
  ['aircraft', 'Aircraft', ['aircraft', 'aircraft-cluster', 'diversions'], 'Military aircraft broadcasting their position, pointing along their track, and flights diverted or turned back'],
  ['ships', 'Warships', ['ships', 'ship-trails'], 'Warships, from the weekly fleet tracker'],
  ['incidents', 'Reports', ['incidents'], 'Incidents reported in the news, unverified'],
  ['dark', 'Dark ships', ['dark', 'loitering'], 'Ships seen on radar with no AIS, and carrier vessels loitering at sea'],
  ['airports', 'Airports', ['airports'], 'Theatre airports, ringed when departures fell or flights were diverted away'],
  ['warnings', 'Sea warnings', ['warnings'], 'Navigational warnings at sea'],
]
/* the panel groups the layers by what they are, so the list reads as places, then what happened, then what moved, then notices */
export const LAYER_GROUPS: [string, Layer[]][] = [['Sites', ['bases', 'airports']], ['Activity', ['fires', 'incidents']], ['Movement', ['aircraft', 'ships', 'dark']], ['Warnings', ['warnings']]]
export type Layers = Record<Layer, boolean>
const KEYS = LAYERS.map(l => l[0])
export const DEFAULT_LAYERS: Layers = { bases: true, fires: true, aircraft: true, ships: true, incidents: true, dark: true, airports: false, warnings: false }
const KEY = 'ww-layers'

export function loadLayers(): Layers {
  try { return { ...DEFAULT_LAYERS, ...JSON.parse(localStorage.getItem(KEY) || '{}') } } catch { return { ...DEFAULT_LAYERS } }
}
export function saveLayers(l: Layers) {
  try { localStorage.setItem(KEY, JSON.stringify(l)) } catch { /* private mode: the choice lasts this visit */ }
}
/* the address form: the layers that are on, in a fixed order, joined by dots; "none" when every one is off */
export const layersParam = (l: Layers) => KEYS.filter(k => l[k]).join('.') || 'none'
export const isDefault = (l: Layers) => KEYS.every(k => l[k] === DEFAULT_LAYERS[k])
export function parseLayers(s: string | null): Layers | null {
  if (s == null) return null
  if (s === 'none') return Object.fromEntries(KEYS.map(k => [k, false])) as Layers
  const on = s.split('.').filter(k => (KEYS as string[]).includes(k))
  return on.length ? Object.fromEntries(KEYS.map(k => [k, on.includes(k)])) as Layers : null
}
