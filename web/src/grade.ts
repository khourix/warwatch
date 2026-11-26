import type { MapIncident } from './data'

/* How much weight a news report carries, from who published it and whether others said the same thing.
   Official: an authority that answers for it (UKMTO, a navy, a ministry), even when another outlet passed it on.
   Corroborated: two or more different outlets placed it at the same place on the same day.
   Claim: a state outlet of a party to the fighting, reporting on it.
   One source: one outlet, not yet repeated by another.
   This is about the source only. WarWatch checks none of them, and none enters the reading. */
export type Grade = 'official' | 'corroborated' | 'claim' | 'single'
export const GRADE_WORD: Record<Grade, string> = { official: 'Official', corroborated: 'Corroborated', claim: 'Claim', single: 'One source' }
export const GRADE_SAYS: Record<Grade, string> = {
  official: 'From an authority that answers for it, such as UKMTO.',
  corroborated: 'Two or more different outlets reported it at this place on this day.',
  claim: 'From state media of a party to the fighting. Read it as that side\'s claim.',
  single: 'One outlet so far. Not repeated by another yet.',
}
const OFFICIAL = /^(UKMTO|JMIC|MARAD|CENTCOM|NATO|IDF|Ministry|MoD|Navy)\b/i
const STATE = /\b(Mehr|Tehran Times|Press ?TV|IRNA|Tasnim|Fars|ISNA|IRIB|Al[- ]Masirah|Saba|SANA|RIA|TASS|Sputnik|RT\b|Xinhua|Global Times|CGTN|KCNA|Yonhap)/i

const outlet = (src = '') => src.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '').replace(/\s*\(.*\)$/, '').trim().toLowerCase()
const key = (x: MapIncident) => `${(x.d || '').slice(0, 10)}|${(x.loc || '').toLowerCase()}`

/* grade every report in one pass, so corroboration sees all of them */
export function gradeAll(list: MapIncident[]): Map<MapIncident, Grade> {
  const outlets = new Map<string, Set<string>>()
  for (const x of list) { if (!x.loc) continue; const k = key(x); if (!outlets.has(k)) outlets.set(k, new Set()); outlets.get(k)!.add(outlet(x.src)) }
  const out = new Map<MapIncident, Grade>()
  for (const x of list) {
    const s = x.src || ''
    out.set(x, OFFICIAL.test(s) ? 'official' : x.loc && (outlets.get(key(x))?.size || 0) >= 2 ? 'corroborated' : STATE.test(s) ? 'claim' : 'single')
  }
  return out
}

/* the same chip everywhere a report appears: one outline weight, no fill, no warning colour, so it reads as a label and not an alarm */
export const gradeClass = (g: Grade) => `inline-flex h-[18px] shrink-0 items-center rounded-[4px] border px-1.5 text-[10.5px] font-medium leading-none ${g === 'official' || g === 'corroborated' ? 'border-fg3 text-fg' : 'border-dashed border-line2 text-fg2'}`
