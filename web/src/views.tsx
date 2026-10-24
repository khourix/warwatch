import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import NumberFlow from '@number-flow/react'
import { ArrowLeft, ChevronRight, Satellite, Flame, ShieldAlert, FileText, Check, Info } from 'lucide-react'
import { GROUPS, GROUP_HINT, useTheatre, useSignals, summary, levelVar, fmtZ, shortDate, ago, parseGen, type Brief, type LiveMap, type Route, type Signal, type FeedItem } from './data'
import { GroundTab } from './ground'
import { usePrefs, fmtTime } from './settings'
import { LevelChip, TellDots, Spark, Strip, Section, Tabs, Skeleton, Failed, listAnim } from './ui'

type Go = (r: Route) => void
const KIND: Record<FeedItem['kind'], [typeof ShieldAlert, string]> = { tell: [ShieldAlert, 'var(--watch)'], base: [Satellite, 'var(--elev)'], fire: [Flame, 'var(--elev)'], official: [FileText, 'var(--fg-3)'] }
export const toRoute = (to: FeedItem['to']): Route => to.view === 'theatre' && to.id ? { v: 'theatre', id: to.id, tab: to.tab } : to.view === 'base' && to.id ? { v: 'base', id: to.id } : { v: 'brief' }

function Header({ back, crumbs, go }: { back?: Route; crumbs: [string, Route?][]; go: Go }) {
  return (
    <div className="flex items-center gap-2 px-5 pt-4 text-[12.5px] text-fg3">
      {back && <button onClick={() => go(back)} aria-label="Back" className="-ml-1.5 grid h-7 w-7 place-items-center rounded-md hover:bg-hover hover:text-fg"><ArrowLeft size={15} /></button>}
      {crumbs.map(([t, r], i) => <span key={i} className="flex items-center gap-2">{i > 0 && <ChevronRight size={12} className="opacity-50" />}{r ? <button onClick={() => go(r)} className="hover:text-fg">{t}</button> : <span className="text-fg2">{t}</span>}</span>)}
    </div>
  )
}

/* ---------------------------------------------------------------- Brief */
export function BriefView({ brief, go }: { brief: Brief; go: Go }) {
  const now = parseGen(brief.generated)
  const { prefs } = usePrefs()
  const name = (id: string) => brief.theatres.find(t => t.id === id)?.name || id
  const week = brief.feed.filter(f => (now.getTime() - new Date(f.date.slice(0, 10) + 'T12:00Z').getTime()) / 864e5 <= 7.5)
  const byId = Object.fromEntries(brief.theatres.map(t => [t.id, t]))
  return (
    <div>
      <div className="px-5 pb-4 pt-5">
        <div className="eyebrow mb-2 flex items-center gap-2"><span className="relative h-1.5 w-1.5 rounded-full bg-accent text-accent live-dot" />Brief · {now.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: prefs.tz === 'utc' ? 'UTC' : undefined })}, {fmtTime(now, prefs.tz)}{brief.demo && <span className="rounded bg-crit/20 px-1 text-crit">demo data</span>}</div>
        <p className="font-[family-name:var(--font-serif)] text-[21px] leading-[1.32] tracking-[-0.005em] text-fg [text-wrap:pretty]">{brief.headline}</p>
        <div className="mt-4 grid grid-cols-3 overflow-hidden rounded-xl border border-line">
          {([[brief.counts.tells, 'timing tells', 'fired this week', 'var(--watch)'], [brief.counts.bases, 'bases changed', 'on satellite radar', 'var(--elev)'], [brief.counts.strong, 'strong readings', '3 SD or more', 'var(--fg)']] as const).map(([n, a, b, c], i) => (
            <div key={i} className={`px-3 py-2.5 ${i ? 'border-l border-line' : ''}`}>
              <div className="num text-[22px] font-medium leading-none" style={{ color: n ? c : 'var(--fg)' }}><NumberFlow value={n} /></div>
              <div className="mt-1.5 text-[12px] leading-tight text-fg2">{a}<br /><span className="text-fg3">{b}</span></div>
            </div>
          ))}
        </div>
      </div>
      <Section title="Since last week" aside={`${week.length} items`}>
        {week.length === 0 && <p className="text-[13px] text-fg3">Nothing new this week: no timing tell, base change, unusual fire or CrisisWatch alert.</p>}
        <ul className="-mx-2">
          {week.map((f, i) => { const [I, tone] = KIND[f.kind]; return (
            <motion.li key={i} {...listAnim(i)}>
              <button onClick={() => go(toRoute(f.to))} className="group flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left hover:bg-hover">
                <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border border-line" style={{ color: tone }}><I size={14} /></span>
                <span className="min-w-0 flex-1"><span className="block text-[13.5px] leading-snug text-fg"><b className="font-medium">{name(f.theatre)}</b> · {f.title}</span><span className="block text-[12px] text-fg3">{f.detail}</span></span>
                <span className="num shrink-0 pt-0.5 text-[11.5px] text-fg3">{ago(now, f.date)}</span>
              </button>
            </motion.li>) })}
        </ul>
      </Section>
      <Section title="Theatres" aside={<span className="flex items-center gap-3"><span>Tells</span><span>Groups, slow to fast</span></span>}>
        {brief.regions.map(r => (
          <div key={r.id} className="mb-3 last:mb-0">
            <div className="mb-1 text-[12px] font-medium text-fg3">{r.name}</div>
            {r.theatres.map((id, i) => { const t = byId[id]; if (!t) return null; return (
              <motion.button key={id} {...listAnim(i)} onClick={() => go({ v: 'theatre', id })} className="-mx-2 flex w-[calc(100%+16px)] items-center gap-3 rounded-lg px-2 py-[7px] text-left hover:bg-hover">
                <i className="h-2 w-2 shrink-0 rounded-full" style={{ background: levelVar(t.level) }} />
                <span className="min-w-0 flex-1 truncate text-[13.5px]">{t.name}{t.spillover && <span className="ml-1.5 text-[11.5px] text-fg3">spillover</span>}{t.context && <span className="ml-1.5 text-[11.5px] text-fg3">· {t.context.toLowerCase()}</span>}</span>
                <TellDots on={t.tellsOn} n={t.tellsTotal} />
                <span className="flex gap-[2px]">{GROUPS.map(g => <i key={g} title={`${g} ${fmtZ(t.groups[g])} SD`} className="h-4 w-3 rounded-[2px]" style={{ background: t.groups[g] == null ? 'var(--line)' : zBg(t.groups[g]) }} />)}</span>
              </motion.button>) })}
          </div>
        ))}
      </Section>
      <div className="mx-5 mb-6 mt-2 flex gap-3 rounded-xl border border-line bg-raised px-3.5 py-3 text-[12.5px] leading-relaxed text-fg2">
        <Info size={15} className="mt-0.5 shrink-0 text-fg3" />
        <span>Colours show how unusual the readings are, not a forecast. The 30-day model runs in shadow until it passes all three of its checks. <button onClick={() => go({ v: 'record' })} className="text-accent hover:underline">See the record</button></span>
      </div>
    </div>
  )
}
const zBg = (z: number | null) => z == null ? 'var(--line)' : Math.abs(z) >= 3 ? 'var(--elev)' : Math.abs(z) >= 2 ? 'var(--watch)' : Math.abs(z) >= 1 ? 'color-mix(in oklab, var(--watch) 38%, transparent)' : 'color-mix(in oklab, var(--fg-3) 22%, transparent)'

/* ---------------------------------------------------------------- Theatre */
export function TheatreView({ id, tab, brief, live, go }: { id: string; tab?: string; brief: Brief; live?: LiveMap; go: Go }) {
  const q = useTheatre(id)
  const [sub, setSub] = useState(tab || 'now')
  useEffect(() => { if (tab) setSub(tab) }, [tab])
  const [open, setOpen] = useState<string | null>(null)
  const sigQ = useSignals(sub === 'signals')
  const sigs = useMemo(() => (sigQ.data?.signals || []).filter(s => s.theatre === id && s.z != null).sort((a, b) => Math.abs(b.z!) - Math.abs(a.z!)), [sigQ.data, id])
  const name = (x: string) => brief.theatres.find(t => t.id === x)?.name || x
  if (q.isPending) return <><Header back={{ v: 'brief' }} crumbs={[['Brief', { v: 'brief' }], [name(id)]]} go={go} /><Skeleton lines={6} /></>
  if (q.isError) return <><Header back={{ v: 'brief' }} crumbs={[['Brief', { v: 'brief' }], [name(id)]]} go={go} /><Failed what={name(id)} error={q.error} /></>
  const t = q.data
  return (
    <div>
      <Header back={{ v: 'brief' }} crumbs={[['Brief', { v: 'brief' }], [t.region], [t.name]]} go={go} />
      <div className="px-5 pb-4 pt-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-[28px] font-semibold leading-none tracking-[-0.02em]">{t.name}</h1>
          <LevelChip level={t.level} size="lg" />
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 text-[12.5px] text-fg3">
          {t.context && <span className="text-fg2" title={`Set by hand, checked ${t.contextChecked}. Context only: it does not change the level.`}>{t.context}</span>}
          {t.spillover && <span>Spillover from {t.parents.map(name).join(', ')}</span>}
          <span>{t.countries.slice(0, 4).join(', ')}{t.countries.length > 4 ? '…' : ''}</span>
        </div>
        <p className="mt-3 font-[family-name:var(--font-serif)] text-[17px] leading-[1.42] text-fg [text-wrap:pretty]">{summary(t)}</p>
        <dl className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-line bg-[var(--line)]">
          {([['Timing tells', <><NumberFlow value={t.tells.filter(x => x.on).length} /><span className="text-fg3">/{t.tells.length}</span></>, 'this week', t.tells.some(x => x.on) ? 'var(--watch)' : undefined],
            ['Strong readings', <NumberFlow value={t.signals.strong} />, `of ${t.signals.scored} scored`, t.signals.strong >= 5 ? 'var(--elev)' : undefined],
            ['Standing risk', t.standingRisk == null ? <span className="text-fg3">n/a</span> : <><NumberFlow value={t.standingRisk} format={{ maximumFractionDigits: 2, minimumFractionDigits: 2 }} />×</>, 'usual · in shadow', undefined]] as const).map(([a, b, c, col], i) => (
            <div key={i} className="bg-panel px-3 py-2.5">
              <dt className="text-[11.5px] text-fg3">{a}</dt>
              <dd className="num mt-1 text-[20px] font-medium leading-none" style={{ color: col }}>{b}</dd>
              <dd className="mt-1 text-[11.5px] text-fg3">{c}</dd>
            </div>
          ))}
        </dl>
      </div>
      <Tabs id="th" value={sub} onChange={setSub} tabs={[['now', 'Now'], ['ground', 'On the ground', live ? live.bases.filter(b => b.theatres.includes(id)).length + live.fires.filter(f => f.theatre === id).length : undefined], ['signals', 'Signals', t.signals.scored], ['history', 'History', t.events.length]]} />
      <AnimatePresence mode="wait">
        <motion.div key={sub} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
          {sub === 'now' && <>
            <Section title="Build-up ladder" aside="60 days · SD now">
              <div className="space-y-1">
                {GROUPS.map(g => { const d = t.groups[g]; return (
                  <div key={g}>
                    <button onClick={() => setOpen(open === g ? null : g)} aria-expanded={open === g} className="-mx-2 grid w-[calc(100%+16px)] grid-cols-[84px_1fr_44px] items-center gap-3 rounded-md px-2 py-1.5 text-left hover:bg-hover" title={GROUP_HINT[g]}>
                      <span className="flex items-center gap-1.5 text-[13px]"><ChevronRight size={12} className={`text-fg3 transition-transform ${open === g ? 'rotate-90' : ''}`} />{g}</span>
                      <Strip h={d?.history || []} />
                      <span className="num text-right text-[12.5px]" style={{ color: (d?.z ?? 0) >= 2 ? 'var(--elev)' : 'var(--fg-2)' }}>{fmtZ(d?.z)}</span>
                    </button>
                    <AnimatePresence>{open === g && (
                      <motion.ul initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: .24, ease: [.22, 1, .36, 1] }} className="overflow-hidden pl-6">
                        <li className="py-1 text-[12px] text-fg3">{GROUP_HINT[g]}</li>
                        {(d?.top || []).map(s => <li key={s.id} className="flex justify-between gap-3 py-1 text-[12.5px] text-fg2"><span className="truncate">{s.label}</span><span className="num" style={{ color: Math.abs(s.z) >= 2 ? 'var(--watch)' : undefined }}>{fmtZ(s.z)}</span></li>)}
                      </motion.ul>)}</AnimatePresence>
                  </div>) })}
              </div>
              <p className="mt-3 text-[12px] leading-relaxed text-fg3">Groups run from slowest (contracts move months ahead) to fastest (aircraft move hours ahead). A theatre climbing the ladder lights up from the top.</p>
            </Section>
            <Section title="Timing tells, last 7 days" aside={`${t.tells.filter(x => x.on).length} of ${t.tells.length} seen`}>
              <ul className="space-y-2.5">
                {t.tells.map((x, i) => (
                  <motion.li key={i} {...listAnim(i)} className="flex gap-3" title={x.says}>
                    <span className="mt-[3px] grid h-4 w-4 shrink-0 place-items-center rounded-full border" style={{ borderColor: x.on ? 'var(--watch)' : 'var(--line-2)', background: x.on ? 'var(--watch)' : 'transparent' }}>{x.on && <Check size={10} strokeWidth={3} className="text-[var(--bg)]" />}</span>
                    <span className="min-w-0 flex-1"><span className={`block text-[13px] ${x.on ? 'text-fg' : 'text-fg2'}`}>{x.name}</span><span className="block text-[11.5px] text-fg3">{x.record?.events ? `Fired before ${x.record.caught} of ${x.record.events} past events` : 'No history to test it on yet'}</span></span>
                    <span className="num shrink-0 text-[11.5px]" style={{ color: x.on ? 'var(--watch)' : 'var(--fg-3)' }}>{x.on && x.date ? shortDate(x.date) : 'not seen'}</span>
                  </motion.li>
                ))}
              </ul>
            </Section>
            {t.official.length > 0 && <Section title="Official signals">
              {t.official.map((o, i) => <div key={i} className="flex justify-between gap-4 py-1.5 text-[12.5px]"><span className="text-fg2">{o.name}</span><span className="text-right text-fg">{o.value}</span></div>)}
            </Section>}
          </>}
          {sub === 'ground' && <GroundTab id={id} live={live} brief={brief} go={go} />}
          {sub === 'signals' && <Section title="Signals, most unusual first" aside={<button onClick={() => go({ v: 'signals', th: t.id })} className="text-accent hover:underline">Open in Signals</button>}>
            {sigQ.isPending ? <Skeleton lines={8} /> : sigs.slice(0, 30).map((s, i) => <SignalRow key={s.id} s={s} i={i} go={go} />)}
          </Section>}
          {sub === 'history' && <Section title="Past events in this theatre" aside={`Complete to ${shortDate(brief.eventsThrough)}`}>
            {t.events.length === 0 && <p className="text-[13px] text-fg3">No labelled event in this theatre since 2018.</p>}
            <ol className="relative ml-1 border-l border-line pl-4">
              {[...t.events].reverse().map((e, i) => (
                <motion.li key={i} {...listAnim(i)} className="relative pb-3">
                  <i className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full border-2 border-[var(--panel)]" style={{ background: e.kind === 'onset' || e.kind === 'strike' ? 'var(--event)' : 'var(--fg-3)' }} />
                  <div className="num text-[11.5px] text-fg3">{new Date(e.date + 'T00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })} · {e.kind}</div>
                  <div className="text-[13px] leading-snug text-fg">{e.text}</div>
                </motion.li>
              ))}
            </ol>
          </Section>}
        </motion.div>
      </AnimatePresence>
      <div className="mx-5 my-5 flex items-center justify-between rounded-xl border border-line px-3.5 py-2.5 text-[12px] text-fg3">
        <span>How sure: <b className="font-medium text-fg2">{t.signals.scored} of {t.signals.total}</b> signals scored · confidence {t.confidence?.toLowerCase() || 'n/a'}</span>
        <button onClick={() => go({ v: 'record' })} className="text-accent hover:underline">Record</button>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- Signals */
function SignalRow({ s, i, go }: { s: Signal; i: number; go: Go }) {
  const z = s.z ?? 0
  return (
    <motion.button {...listAnim(i)} onClick={() => go({ v: 'signal', id: s.id })} className="-mx-2 grid w-[calc(100%+16px)] grid-cols-[1fr_auto_52px] items-center gap-3 rounded-md border-b border-line px-2 py-2 text-left last:border-0 hover:bg-hover">
      <div className="min-w-0"><div className="truncate text-[13px] text-fg" title={s.label}>{s.label}</div><div className="truncate text-[11.5px] text-fg3">{s.group} · {s.sub} · {s.lagging ? 'confirms' : 'leads'}{s.stale ? ' · last good copy' : ''}</div></div>
      <Spark v={s.spark} w={76} h={22} stroke={Math.abs(z) >= 2 ? 'var(--watch)' : 'var(--fg-3)'} fill={false} />
      <span className="num text-right text-[12.5px]" style={{ color: Math.abs(z) >= 3 ? 'var(--elev)' : Math.abs(z) >= 2 ? 'var(--watch)' : 'var(--fg-2)' }}>{fmtZ(s.z)}</span>
    </motion.button>
  )
}
