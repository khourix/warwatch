import { useMemo, useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { Check, CircleDashed } from 'lucide-react'
import { useRecord, useTheatre, useSignals, gatesSentence, gatesPassed, wireName, short, shortDate, parseGen, groupTone, stepFixed, GROUPS,
  type Brief, type Route, type Forward, type PastEvent, type RecordFile } from './data'
import { Skeleton, Failed, Lnk, Explain, listAnim } from './ui'
import { Crumbs, recordLine } from './views'
import { usePrefs, fmtTime } from './settings'
import { StatusBar, statusRows } from './health'

/* Record: how WarWatch knows what it shows and how it has done. The 30-day model's checks and its forward log, shown as a test in
   progress; past events and what the tripwires and readings did before them; the tripwire record; data health; the method and
   each source's notes. Every number here is read from brief.json and record.json; nothing is worked out beyond counting. */

type Go = (r: Route) => void
const card = 'rounded-r3 border border-line bg-s1'

export function RecordView({ brief, go }: { brief: Brief; go: Go }) {
  const rq = useRecord()
  return (
    <div className="pb-6">
      <Crumbs back={{ v: 'brief' }} items={[['Watch', { v: 'brief' }], ['Record']]} go={go} />
      <div className="px-5 pb-2 pt-2">
        <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em]">Record</h1>
        <p className="mt-2.5 max-w-[680px] font-serif text-[17px] leading-[1.42] text-fg [text-wrap:pretty]">How WarWatch knows what it shows, and how it has done: what came before past events, the record of each tripwire, the test the 30-day model is still sitting, and how the data is holding up today.</p>
        <p className="mt-2 text-[12px] text-fg2">Every term is in the <Lnk to={{ v: 'glossary' }} go={go} className="lnk">glossary</Lnk>.</p>
      </div>
      <ModelTest brief={brief} rec={rq.data} pending={rq.isPending} failed={rq.isError} />
      {rq.isPending ? <Skeleton lines={8} /> : rq.isError ? <Failed what="the record" error={rq.error} /> : <>
        <Past brief={brief} past={rq.data.past} go={go} />
        <TripwireRecord brief={brief} />
        <Health brief={brief} rec={rq.data} go={go} />
        <Method brief={brief} rec={rq.data} />
      </>}
    </div>
  )
}

/* a section of the page: an h2 and a short line under it */
function Part({ id, title, lede, children, aside }: { id: string; title: ReactNode; lede?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section aria-labelledby={id} className="px-5 pt-7">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id={id} className="text-[19px] font-semibold tracking-[-0.02em] text-fg">{title}</h2>{aside && <span className="text-[12px] text-fg2">{aside}</span>}
      </div>
      {lede && <p className="-mt-1 mb-3.5 max-w-[680px] text-[13px] leading-[1.5] text-fg2">{lede}</p>}
      {children}
    </section>
  )
}

/* ---------------------------------------------------------------- the 30-day chance, as a test */
/* One check on a line: the axis, the threshold it must clear (a tick, labelled), the range (a band) and the value (a dot). Ink and
   grey only: the model has not passed, so nothing here carries a warning colour. */
function GateLine({ lo, hi, v, band, at, label, fmt, name }: { lo: number; hi: number; v: number; band?: [number, number]; at: number; label: string; fmt: (x: number) => string; name: string }) {
  const X = (x: number) => Math.max(0, Math.min(1, (x - lo) / (hi - lo))) * 100
  return (
    <div role="img" aria-label={name} className="mt-4">
      <div className="relative h-[34px]">
        <span className="absolute inset-x-0 top-[22px] h-px bg-line2" />
        <span className="absolute top-[12px] h-[21px] w-px bg-fg2" style={{ left: `${X(at)}%` }} />
        <span className="absolute top-0 whitespace-nowrap font-mono text-[10.5px] leading-none text-fg2" style={{ left: `${X(at)}%`, transform: X(at) > 70 ? 'translateX(-100%)' : X(at) < 15 ? 'none' : 'translateX(-50%)' }}>{label}</span>
        {band && <motion.span className="absolute top-[19px] h-[7px] rounded-full bg-[color-mix(in_oklab,var(--fg3)_45%,transparent)]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: .2 }} style={{ left: `${X(band[0])}%`, width: `${X(band[1]) - X(band[0])}%` }} />}
        <span className="absolute top-[17px] h-[11px] w-[11px] -translate-x-1/2 rounded-full border-2 border-s1 bg-fg" style={{ left: `${X(v)}%` }} />
      </div>
      <div className="flex justify-between font-mono text-[10.5px] text-fg2" aria-hidden><span>{fmt(lo)}</span><span>{fmt(hi)}</span></div>
    </div>
  )
}

const signed = (x: number, n = 3) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(n)}`
const in100 = (p: number) => Math.round(p * 100)

function ModelTest({ brief, rec, pending, failed }: { brief: Brief; rec?: RecordFile; pending: boolean; failed: boolean }) {
  const g = brief.model.gates, active = brief.model.active
  const n = g ? gatesPassed(g) : 0
  const checks: { ok: boolean; title: string; text: string; line: ReactNode }[] = g ? [
    { ok: g.auc_lo_above_half, title: 'Ranks past theatre-months better than a coin flip',
      text: `In testing on past theatre-months it scores an AUC of ${g.auc.toFixed(3)}, with a 95% range of ${g.auc_lo.toFixed(3)} to ${g.auc_hi.toFixed(3)}. The whole range must sit above 0.5, a coin toss.`,
      line: <GateLine name={`AUC ${g.auc.toFixed(3)}, range ${g.auc_lo.toFixed(3)} to ${g.auc_hi.toFixed(3)}, against a coin toss at 0.5`} lo={.4} hi={.8} v={g.auc} band={[g.auc_lo, g.auc_hi]} at={.5} label="coin toss 0.5" fmt={x => x.toFixed(1)} /> },
    { ok: g.bss_positive, title: "Beats each theatre's usual rate",
      text: `Brier skill ${signed(g.bss)}. Above zero means its chances came closer to what happened than always quoting each theatre's long-run rate.`,
      line: <GateLine name={`Brier skill ${signed(g.bss)}, against zero`} lo={Math.min(-.02, g.bss - .005)} hi={Math.max(.02, g.bss + .005)} v={g.bss} at={0} label="usual rate 0" fmt={x => signed(x, 2)} /> },
    { ok: g.beats_shuffled, title: 'Beats the same signals with their timing shuffled',
      text: `With each theatre's chances shifted in time, an AUC this good or better turned up ${in100(g.shuffle_p_auc)} times in 100. It must be under 5 in 100.${g.shuffle_p_bss != null ? ` For Brier skill it was ${in100(g.shuffle_p_bss)} in 100; the check reads the AUC.` : ''}`,
      line: <GateLine name={`${in100(g.shuffle_p_auc)} in 100, against a limit of 5 in 100`} lo={0} hi={Math.max(.5, g.shuffle_p_auc + .05)} v={g.shuffle_p_auc} at={.05} label="must be under 0.05" fmt={x => x.toFixed(1)} /> },
  ] : []
  const fw = (rec?.forward || []).filter(f => !f.err)
  return (
    <Part id="rec-model" title={active ? 'The 30-day chance, in use and still scored' : 'The 30-day chance, a test in progress'}
      lede={active ? 'The 30-day model passed its three checks at its last refit, so it sets the levels. Its forecasts are also written down before anything happens and scored as they mature.'
        : `WarWatch has a model that gives each theatre a chance of a qualifying event in the next 30 days. ${g ? 'It has not passed its own checks' : 'Its checks have not been run yet'}, so the app does not use it: no level, colour or headline comes from it. Here is where the test stands.`}>
      {!g ? <p className={`${card} px-4 py-3 text-[13px] text-fg2`}>{gatesSentence(null, active)} No check results are in this data run.</p> : <>
        <div className={`${card} flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3`}>
          <span className="inline-flex shrink-0 items-center rounded-full border border-line2 px-2.5 py-[3px] text-[12px] font-medium text-fg">{active ? 'In use' : 'Not in use'}</span>
          <p className="min-w-[220px] flex-1 text-[13px] leading-[1.45] text-fg"><span className="num">{n} of 3</span> checks passed. {gatesSentence(g, active)}</p>
          <p className="w-full text-[11.5px] text-fg2">Model {brief.model.version}, refitted {shortDate(brief.model.fitted)}. It is refitted and checked again every month.</p>
        </div>
        <ul className="mt-3 grid gap-3 lg:grid-cols-3">
          {checks.map((c, i) => (
            <motion.li key={i} {...listAnim(i)} className={`${card} px-4 pb-3 pt-3.5`}>
              <div className="flex items-center gap-2 text-[12px] font-medium text-fg">
                <span className="grid h-5 w-5 place-items-center rounded-full border border-line2" aria-hidden>{c.ok ? <Check size={12} strokeWidth={2.6} /> : <CircleDashed size={12} strokeWidth={2} />}</span>
                {c.ok ? 'Passed' : 'Not yet'}
              </div>
              <h3 className="mt-2 text-[14px] font-medium leading-[1.3] text-fg">{c.title}</h3>
              <p className="mt-1 text-[12.5px] leading-[1.45] text-fg2">{c.text}</p>
              {c.line}
            </motion.li>))}
        </ul>
      </>}
      <div className={`${card} mt-3 px-4 py-3.5`}>
        <h3 className="text-[14px] font-medium text-fg"><Explain k="forward">The forward log</Explain></h3>
        <p className="mt-1 max-w-[680px] text-[12.5px] leading-[1.45] text-fg2">Every day each forecast is written to a log before its outcome is known, and each line carries a fingerprint of the one before, so it cannot be changed afterwards. A forecast counts once 30 days have passed and the event list has caught up{fw[0] ? `, so a target gets its first scored report after ${fw[0].need} counted days${fw[0].read ? ` and the one read that can switch it on, fixed in advance, after ${fw[0].read}` : ''}` : ''}.</p>
        {pending ? <Skeleton lines={3} /> : !fw.length ? <p className="mt-2 text-[12.5px] text-fg2">{failed ? 'The forward log could not be loaded; the error is below.' : 'The forward log is not in this data run.'}</p>
          : <ul className="mt-1">{fw.map(f => <ForwardRow key={f.k} f={f} />)}</ul>}
      </div>
    </Part>
  )
}

const targetName = (f: Forward) => f.name.replace(" (the page's model)", '').replace(' (hidden)', '')
function ForwardRow({ f }: { f: Forward }) {
  const read = f.read || f.need, pct = (x: number) => Math.min(100, x / read * 100)
  const role = f.k === 'main' ? "the app's model" : 'a second model, kept off the page'
  return (
    <li className="border-t border-line py-3 first:border-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-[13px] text-fg">{targetName(f)}<span className="text-fg2">, {role}</span></span>
        <span className="num text-[12.5px] text-fg">{f.days} of {f.need} days</span>
      </div>
      <div className="relative mt-2 h-1.5 rounded-full bg-z0" role="img" aria-label={`${f.days} counted days. The first report comes at ${f.need}${f.read ? `, the deciding read at ${f.read}` : ''}.`}>
        <motion.i className="absolute inset-y-0 left-0 rounded-full bg-fg2" initial={{ width: 0 }} animate={{ width: `${f.days ? Math.max(1, pct(f.days)) : 0}%` }} transition={{ duration: .22, ease: [.2, .8, .2, 1] }} />
        {f.read && f.read > f.need && <i className="absolute -inset-y-1 w-px bg-fg3" style={{ left: `${pct(f.need)}%` }} />}
      </div>
      {f.read && f.read > f.need && <div className="relative mt-1 h-3 font-mono text-[10px] text-fg2" aria-hidden><span className="absolute -translate-x-1/2" style={{ left: `${pct(f.need)}%` }}>{f.need}</span><span className="absolute right-0">{f.read}</span></div>}
      <p className="mt-1.5 text-[11.5px] leading-[1.45] text-fg2">
        {f.logged} {f.logged === 1 ? 'day' : 'days'} of forecasts logged{f.first ? ` since ${shortDate(f.first)}` : ''}; outcomes known to {shortDate(f.through)}.{' '}
        {f.days === 0 ? 'None has been counted yet, because the outcomes are not known 30 days past any of them.' : ''}
        {f.chain === false ? ' The log\'s chain is broken, so its record cannot be trusted until it is checked.' : ''}
        {f.ready && f.pass ? ' It has passed the deciding read.' : f.ready ? (f.final ? ' It has not passed the deciding read.' : ' The interim numbers are in the report; they cannot switch it on.') : ''}
      </p>
    </li>
  )
}

/* ---------------------------------------------------------------- past events */
function Past({ brief, past, go }: { brief: Brief; past?: PastEvent[]; go: Go }) {
  const [all, setAll] = useState(false)
  const name = (id: string) => short(brief.theatres.find(t => t.id === id)?.name || id)
  const list = past || []
  const shown = all ? list : list.slice(0, 8)
  return (
    <Part id="rec-past" title="Before past events" aside={brief.eventsThrough ? `Event list complete to ${shortDate(brief.eventsThrough)}` : undefined}
      lede={<>The newest events WarWatch is tested on, and what came before each in that theatre: the <Explain k="tripwire">tripwires</Explain> that started firing in the 7 days before, and each <Explain k="group">signal group</Explain>'s highest reading that week.</>}>
      {!past ? <p className={`${card} px-4 py-3 text-[13px] text-fg2`}>This list is not in this data run.</p>
        : !list.length ? <p className={`${card} px-4 py-3 text-[13px] text-fg2`}>No labelled event is in this data run.</p>
        : <ol className={`${card} px-4`}>{shown.map((e, i) => <PastRow key={i} e={e} name={name(e.theatre)} go={go} />)}</ol>}
      {list.length > 8 && <button onClick={() => setAll(!all)} className="lnk mt-2.5 text-[12.5px]">{all ? 'Show the newest 8' : `Show all ${list.length}`}</button>}
      {list.length > 0 && <p className="mt-2.5 max-w-[680px] text-[11.5px] leading-[1.45] text-fg2">Group readings are rebuilt from each signal's own score history, with today's grouping, and are kept for 60 days, so older events show the tripwires alone. A tripwire counts when its replay on the stored history covers that date.</p>}
    </Part>
  )
}
function PastRow({ e, name, go }: { e: PastEvent; name: string; go: Go }) {
  const w = e.tripwires, st = w.started.map(x => wireName(x).toLowerCase())
  const wires = !w.watched ? 'No tripwire record covers this date here.'
    : !st.length ? `None of the ${w.watched} tripwires watched here started in the ${e.window} days before.`
    : `${st.length} of the ${w.watched} tripwires watched here started in the ${e.window} days before: ${st.join(', ')}.`
  const held = GROUPS.filter(g => e.groups[g] != null)
  const top = held.length ? held.reduce((a, b) => (e.groups[b]! > e.groups[a]! ? b : a)) : null
  return (
    <li className="grid grid-cols-[56px_minmax(0,1fr)] gap-3 border-t border-line py-3 first:border-0 max-[420px]:grid-cols-1 max-[420px]:gap-1">
      <span className="num font-mono text-[11.5px] leading-[1.6] text-fg2">{shortDate(e.date)}{e.date.slice(0, 4) !== String(new Date().getUTCFullYear()) ? ` ${e.date.slice(0, 4)}` : ''}</span>
      <div className="min-w-0">
        <p className="text-[13px] leading-[1.4] text-fg"><Lnk to={{ v: 'theatre', id: e.theatre }} go={go} className="font-medium hover:underline hover:decoration-line2 hover:underline-offset-[3px]">{name}</Lnk> · {e.text}</p>
        <p className="mt-1 text-[12px] leading-[1.45] text-fg2">{wires}</p>
        {top ? <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="grid w-[86px] grid-cols-5 gap-0.5" aria-hidden title={GROUPS.map(g => `${g} ${e.groups[g] == null ? 'no reading' : stepFixed(e.groups[g]!)}`).join(' · ')}>
            {GROUPS.map(g => <i key={g} className="h-3 rounded-[2px]" style={{ background: groupTone(e.groups[g]) }} />)}</span>
          <span className="text-[12px] text-fg2">Highest that week: {top} <span className="num text-fg">{stepFixed(e.groups[top]!)}</span> SD<span className="sr-only">. {GROUPS.map(g => `${g} ${e.groups[g] == null ? 'no reading' : stepFixed(e.groups[g]!)}`).join(', ')}.</span></span>
        </div> : null}
      </div>
    </li>
  )
}

/* ---------------------------------------------------------------- tripwire record */
/* the record is summed over every theatre a rule was replayed on (tells.py), the same in every theatre file: read it from one */
function TripwireRecord({ brief }: { brief: Brief }) {
  const q = useTheatre(brief.theatres[0]?.id || '')
  const tells = q.data?.tells || []
  const eps = tells.reduce((n, x) => n + (x.record?.episodes || 0), 0), hits = tells.reduce((n, x) => n + (x.record?.hits || 0), 0)
  return (
    <Part id="rec-wires" title="The tripwire record" lede={<>Each <Explain k="tripwire">tripwire</Explain> replayed on the stored history of every theatre it watches. Most firings were not followed by an event: a lit tripwire is a reason to look closer, not a forecast.</>}>
      {q.isPending ? <Skeleton lines={5} /> : q.isError ? <Failed what="the tripwire record" error={q.error} /> : (
        <div className={`${card} px-4`}>
          <ul>{tells.map(x => (
            <li key={x.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 border-t border-line py-2.5 first:border-0 max-[520px]:grid-cols-1">
              <span className="min-w-0"><b className="block text-[13px] font-medium text-fg">{wireName(x)}</b><span className="block text-[12px] leading-[1.4] text-fg2">{recordLine(x)}</span></span>
              <span className="num text-[12px] text-fg2 max-[520px]:mt-0.5">{x.record?.events ? <>Before <span className="text-fg">{x.record.caught ?? 0}</span> of {x.record.events} past events</> : 'No events in its span'}</span>
            </li>))}
          </ul>
          {eps > 0 && <p className="border-t border-line py-2.5 text-[12px] text-fg2"><span className="num text-fg">{hits}</span> of <span className="num">{eps}</span> firings, across all of them, were followed by an event within 7 days.</p>}
        </div>)}
    </Part>
  )
}

/* ---------------------------------------------------------------- data health */
/* a source problem as the pipeline wrote it ("source: why"); contract.failing_sources does the same for the brief */
export const splitError = (e: unknown) => { const s = typeof e === 'string' ? e : JSON.stringify(e); const i = s.indexOf(': '); return i < 0 ? { source: '', why: s } : { source: s.slice(0, i), why: s.slice(i + 2).replace(/\s*<[^(]*/, ' ').trim() } }

function Health({ brief, rec, go }: { brief: Brief; rec: RecordFile; go: Go }) {
  const st = rec.health.statuses, total = Object.values(st).reduce((a, b) => a + b, 0), { prefs } = usePrefs()
  const sources = brief.health?.sources ?? rec.health.errors.map(splitError)
  const sq = useSignals()
  const stale = useMemo(() => (sq.data?.signals || []).filter(s => s.stale), [sq.data])
  return (
    <Part id="rec-health" title="Data health" aside={<>As of the run at <span className="num">{fmtTime(parseGen(brief.generated), prefs.tz)}</span></>}>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className={`${card} px-4 py-3.5`}>
          <h3 className="text-[14px] font-medium text-fg"><span className="num">{st.ok || 0}</span> of <span className="num">{total}</span> signals are scoring</h3>
          <div className="mt-3"><StatusBar st={st} /></div>
          <dl className="mt-2">{statusRows(st).map(([k, label, n]) => <div key={k} className="flex justify-between gap-3 border-t border-line py-1.5 text-[12.5px] first:border-0"><dt className="text-fg2">{label}</dt><dd className="num text-fg">{n}</dd></div>)}</dl>
          {stale.length > 0 && <p className="mt-1.5 text-[11.5px] leading-[1.45] text-fg2">{stale.length} {stale.length === 1 ? 'signal shows' : 'signals show'} the last good copy and {stale.length === 1 ? 'is' : 'are'} kept out of the score. <Lnk to={{ v: 'signals' }} go={go} className="lnk">Open Signals</Lnk></p>}
        </div>
        <div className={`${card} px-4 py-3.5`}>
          <h3 className="text-[14px] font-medium text-fg">{sources.length ? `${sources.length} ${sources.length === 1 ? 'source' : 'sources'} reported a problem this run` : 'No source reported a problem this run'}</h3>
          {sources.length > 0 && <ul className="mt-2">{sources.map((s, i) => <li key={i} className="border-t border-line py-2 text-[12.5px] leading-[1.45] first:border-0"><b className="font-medium text-fg">{s.source || 'Unnamed source'}</b><span className="block text-fg2">{s.why}</span></li>)}</ul>}
          <p className="mt-2 text-[11.5px] text-fg2">The next run tries every source again.</p>
        </div>
      </div>
      {rec.health.unavailable.length > 0 && <div className={`${card} mt-3 px-4 py-3.5`}>
        <h3 className="text-[14px] font-medium text-fg">What WarWatch cannot see</h3>
        <ul className="mt-1">{rec.health.unavailable.map((u, i) => <li key={i} className="border-t border-line py-2.5 first:border-0"><b className="block text-[13px] font-medium text-fg">{u.n}</b><span className="mt-0.5 block text-[12.5px] leading-[1.5] text-fg2">{u.w}</span></li>)}</ul>
      </div>}
    </Part>
  )
}

/* ---------------------------------------------------------------- method */
function Method({ brief, rec }: { brief: Brief; rec: RecordFile }) {
  const steps: [ReactNode, ReactNode][] = [
    ['Each signal is scored against its own history', <>Daily data: the latest 7-day average against the 7-day averages of the previous year, leaving out the last 30 days so a slow build-up does not hide itself (the last 90 days when there is less than 120 days of history). Monthly data: the previous 36 months, with the usual seasonal pattern removed. The distance is in <Explain k="sd">SD</Explain>, capped at 5, and only movement in the warning direction counts.</>],
    ['One event counts once', 'Signals that move together (recent changes correlated above 0.8) are averaged into one. Late data, published weeks or months after the fact, counts at a quarter, because the aim is early warning.'],
    ['Signals roll up into five groups', <>Each <Explain k="group">group</Explain> combines its strongest signals with an ordered weighted average, so the strongest evidence weighs most.</>],
    ['Groups combine into one number per theatre', <><Explain k="unusual">Unusual readings</Explain> run from 0 to 100. <Explain k="lines">Watch</Explain> starts at 50 and Critical at 90; the level shown is Quiet below Watch. It says how unusual today is, and is not a chance of war.</>],
    ['Tripwires are separate', <>Fixed yes or no rules over 7 days on costly, hard to reverse steps. They never set a level or enter the model.</>],
    ['Bases on satellite radar', <>Sentinel-1 radar passes every few days at 10 m. WarWatch counts <Explain k="bright">bright objects</Explain> on each base and compares the count with that base's own usual range. One pass far outside it marks the base as changed.</>],
    ['Context lines', 'Lines such as "War under way" are set by hand and checked monthly. They say what the baseline is; they never change a level.'],
  ]
  return (
    <Part id="rec-method" title="How it works" lede={`The 30-day model is version ${brief.model.version}, fitted ${shortDate(brief.model.fitted)}. The full method is in METHODOLOGY.md and MODEL.md.`}>
      <div className="grid gap-3 lg:grid-cols-2">
        <ol className={`${card} px-4 py-1`}>
          {steps.map(([a, b], i) => <li key={i} className="grid grid-cols-[18px_minmax(0,1fr)] gap-2 border-t border-line py-2.5 first:border-0">
            <span className="num font-mono text-[11.5px] leading-[1.6] text-fg2">{i + 1}</span>
            <span><b className="block text-[13px] font-medium text-fg">{a}</b><span className="mt-0.5 block text-[12.5px] leading-[1.5] text-fg2">{b}</span></span></li>)}
        </ol>
        <div className={`${card} px-4 py-1`}>
          <h3 className="pb-1 pt-2.5 text-[14px] font-medium text-fg">Sources and when they update</h3>
          <ul>{rec.health.updates.map((u, i) => <li key={i} className="border-t border-line py-2.5">
            <div className="flex flex-wrap justify-between gap-x-3 text-[12.5px]"><b className="font-medium text-fg">{u.s}</b><span className="text-fg2">{u.e}</span></div>
            <p className="mt-0.5 text-[12px] leading-[1.45] text-fg2">{u.l}</p></li>)}
          </ul>
        </div>
      </div>
      <p className="mt-3 text-[12.5px] text-fg2">Read further: <a className="lnk" href="https://github.com/khourix/warwatch/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">METHODOLOGY.md</a>, <a className="lnk" href="https://github.com/khourix/warwatch/blob/main/docs/MODEL.md" target="_blank" rel="noreferrer">MODEL.md</a> and <a className="lnk" href="https://github.com/khourix/warwatch/blob/main/docs/BACKTEST_SUMMARY.md" target="_blank" rel="noreferrer">the backtest in plain words</a>.</p>
    </Part>
  )
}

