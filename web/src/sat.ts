import { asset, type Bounds, type LonLat, type MapFire, type BaseFile } from './data'

/* Satellite pictures the map can lay on the ground, and the outside viewers that show more. A picture covers `bounds`
   (west, south, east, north), so MapLibre can draw it in place under the live layers. */

export type SatImage = { key: string; label: string; url: string; bounds: Bounds; date: string; caption: string }

const day = (d: string, k: number) => new Date(Date.parse(d.slice(0, 10) + 'T00:00:00Z') + k * 864e5).toISOString().slice(0, 10)
const f3 = (x: number) => x.toFixed(3)

/* the VIIRS pass behind a fire: NASA GIBS (free, no key) draws that day's image with every fire the satellites saw on it */
const GIBS_HALF = .12
export const gibsBounds = ([lon, lat]: LonLat): Bounds => [lon - GIBS_HALF, lat - GIBS_HALF, lon + GIBS_HALF, lat + GIBS_HALF]
export const gibsUrl = ([lon, lat]: LonLat, d: string) => 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0'
  + '&LAYERS=VIIRS_SNPP_CorrectedReflectance_TrueColor,VIIRS_SNPP_Thermal_Anomalies_375m_All,VIIRS_NOAA20_Thermal_Anomalies_375m_All,VIIRS_NOAA21_Thermal_Anomalies_375m_All'
  + `&STYLES=&CRS=EPSG:4326&BBOX=${f3(lat - GIBS_HALF)},${f3(lon - GIBS_HALF)},${f3(lat + GIBS_HALF)},${f3(lon + GIBS_HALF)}&WIDTH=640&HEIGHT=640&FORMAT=image/jpeg&TIME=${d.slice(0, 10)}`
/* Copernicus Browser on Sentinel-2, ten days either side; layer '6-SWIR' shows burn scars */
export const copernicusUrl = ([lon, lat]: LonLat, d: string, layer = '1_TRUE_COLOR', zoom = 14) => `https://browser.dataspace.copernicus.eu/?zoom=${zoom}&lat=${f3(lat)}&lng=${f3(lon)}`
  + `&themeId=DEFAULT-THEME&datasetId=S2_L2A_CDAS&layerId=${layer}&fromTime=${day(d, -10)}T00%3A00%3A00.000Z&toTime=${day(d, 10)}T23%3A59%3A59.999Z&dateMode=TIME%20RANGE`
export const worldviewUrl = ([lon, lat]: LonLat, d: string) => `https://worldview.earthdata.nasa.gov/?v=${f3(lon - .15)},${f3(lat - .1)},${f3(lon + .15)},${f3(lat + .1)}`
  + `&l=VIIRS_SNPP_Thermal_Anomalies_375m_All,VIIRS_NOAA20_Thermal_Anomalies_375m_All,VIIRS_NOAA21_Thermal_Anomalies_375m_All,VIIRS_SNPP_CorrectedReflectance_TrueColor&t=${d.slice(0, 10)}-T00%3A00%3A00Z`

/* A fire: the Sentinel-2 close-ups when the imagery review has them (2.5 km across), then that day's VIIRS pass (26 km) */
export function fireImages(f: MapFire): SatImage[] {
  const out: SatImage[] = [], im = f.images
  if (im?.bb) {
    if (im.a) out.push({ key: 'a', label: 'After', url: asset(im.a), bounds: im.bb, date: im.ad, caption: `Sentinel-2 after the fire, ${im.ad}` })
    if (im.b) out.push({ key: 'b', label: 'Before', url: asset(im.b), bounds: im.bb, date: im.bd, caption: `Sentinel-2 before the fire, ${im.bd}` })
    if (im.s) out.push({ key: 's', label: 'Infrared', url: asset(im.s), bounds: im.bb, date: im.ad, caption: `Sentinel-2 infrared after the fire, ${im.ad}: burn scars dark red-brown, live fire bright orange` })
  }
  out.push({ key: 'viirs', label: 'VIIRS', url: gibsUrl(f.ll, f.date), bounds: gibsBounds(f.ll), date: f.date, caption: `NASA VIIRS, ${f.date}: red and yellow dots are every fire seen that day` })
  return out
}

/* A base: the whole-site optical and radar chips (latest and earlier pass), all over the same window */
export function baseImages(b: BaseFile): SatImage[] {
  const bb = b.bounds, im = b.images, out: SatImage[] = []
  if (!bb) return out
  for (const [key, label, p, what] of [['optical', 'Optical', im.optical, 'Sentinel-2 optical'], ['opticalBefore', 'Optical before', im.opticalBefore, 'Sentinel-2 optical, earlier'],
    ['radar', 'Radar', im.radar, 'Sentinel-1 radar'], ['radarBefore', 'Radar before', im.radarBefore, 'Sentinel-1 radar, earlier']] as const)
    if (p) out.push({ key, label, url: asset(p.src), bounds: bb, date: p.date, caption: `${what}, ${p.date}` })
  return out
}

/* Lists outside the map ask it to show something: a fire row in a theatre's "On the ground" tab */
export type Focus = { kind: 'fire'; x: MapFire }
export const focusOnMap = (f: Focus) => dispatchEvent(new CustomEvent<Focus>('ww-focus', { detail: f }))
