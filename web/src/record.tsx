import { useState } from 'react'
import { motion } from 'motion/react'
import { ArrowLeft, ChevronRight, Check, X } from 'lucide-react'
import { useRecord, useSignals, shortDate, type Brief, type Route } from './data'
import { Section, Tabs, Skeleton, Failed, listAnim } from './ui'

/* Record: why to trust the page (the model's three checks and the forecasts logged before the fact), then data health,
   sources and schedule, the method as a short article, and the data WarWatch cannot get. */

type Go = (r: Route) => void

export function RecordView({ brief, go }: { brief: Brief; go: Go }) {
  const rq = useRecord()
  const [tab, setTab] = useState('record')
  const st = rq.data?.health.statuses || {}
  const bad = (st.error || 0) + (rq.data?.health.errors.length || 0)
  return (
    <div>
      <div className="flex items-center gap-2 px-5 pt-4 text-[12.5px] text-fg3">
        <button onClick={() => go({ v: 'brief' })} aria-label="Back" className="-ml-1.5 grid h-7 w-7 place-items-center rounded-md hover:bg-hover hover:text-fg"><ArrowLeft size={15} /></button>
        <button onClick={() => go({ v: 'brief' })} className="hover:text-fg">Brief</button><ChevronRight size={12} className="opacity-50" /><span className="text-fg2">Record</span>
      </div>
      <div className="px-5 pb-3 pt-3">
        <h1 className="text-[24px] font-semibold tracking-[-0.02em]">Track record</h1>
        <p className="mt-2 font-[family-name:var(--font-serif)] text-[16.5px] leading-[1.45]">Every day WarWatch logs its chance for every theatre before anything happens, in a hash-chained record that nobody can edit later. Until the model passes all three checks, it runs in shadow.</p>
      </div>
      <Tabs id="rec" value={tab} onChange={setTab} tabs={[['record', 'Record'], ['health', 'Data health', bad || undefined], ['method', 'How it works'], ['sources', 'Sources'], ['gaps', 'Gaps', rq.data?.health.unavailable.length]]} />
      {rq.isPending ? <Skeleton lines={8} /> : rq.isError ? <Failed what="the record" error={rq.error} /> : <>
        {tab === 'record' && <Model brief={brief} forward={rq.data.forward || []} />}
        {tab === 'health' && <Health rec={rq.data} go={go} />}
        {tab === 'method' && <Method brief={brief} />}
        {tab === 'sources' && <Section title="Sources and schedule" aside={`${rq.data.health.updates.length} sources`}>
          {rq.data.health.updates.map((u, i) => <div key={i} className="border-b border-line py-2.5 last:border-0"><div className="flex justify-between gap-3 text-[13px]"><b className="font-medium">{u.s}</b><span className="shrink-0 text-fg3">{u.e}</span></div><p className="mt-0.5 text-[12px] leading-relaxed text-fg3">{u.l}</p></div>)}
        </Section>}
        {tab === 'gaps' && <Section title="Data we cannot get">
          {rq.data.health.unavailable.map((u, i) => <div key={i} className="py-2.5"><h3 className="text-[13.5px] font-medium">{u.n}</h3><p className="mt-1 text-[12.5px] leading-relaxed text-fg2">{u.w}</p></div>)}
        </Section>}
      </>}
      <div className="mx-5 mb-6 mt-2 rounded-xl border border-line bg-raised px-3.5 py-3 text-[12.5px] leading-relaxed text-fg2">Events are complete to {shortDate(brief.eventsThrough)}. Forecasts after that date are scored once the event list catches up.</div>
    </div>
  )
}

function Model({ brief, forward }: { brief: Brief; forward: NonNullable<import('./data').RecordFile['forward']> }) {
  const g = brief.model.gates
  const rows: [string, string, boolean][] = g ? [
    ['Ranks past theatre-months better than a coin flip', `AUC ${g.auc.toFixed(2)} (${g.auc_lo.toFixed(2)} to ${g.auc_hi.toFixed(2)})`, g.auc_lo_above_half],
    ["Beats each theatre's usual rate", `Brier skill ${g.bss >= 0 ? '+' : ''}${g.bss.toFixed(3)}`, g.bss_positive],
    ['Beats the same signals with timing shuffled', `p ${g.shuffle_p_auc.toFixed(2)}, needs below 0.05`, g.beats_shuffled],
  ] : []
  return <>
    {g && <Section title={`Model v${brief.model.version}, refitted ${shortDate(brief.model.fitted)}`} aside={g.pass ? 'Live' : 'In shadow'}>
      {rows.map(([a, b, ok], i) => (
        <motion.div key={i} {...listAnim(i)} className="flex items-start gap-3 py-2">
          <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full" style={{ background: ok ? 'color-mix(in oklab, var(--accent) 18%, transparent)' : 'color-mix(in oklab, var(--crit) 16%, transparent)', color: ok ? 'var(--accent)' : 'var(--crit)' }} aria-label={ok ? 'passes' : 'fails'}>{ok ? <Check size={12} strokeWidth={3} /> : <X size={12} strokeWidth={3} />}</span>
          <span className="flex-1 text-[13px]">{a}<span className="num block text-[12px] text-fg3">{b}</span></span>
        </motion.div>
      ))}
    </Section>}
    <Section title="Forecasts logged before the fact" aside="90 scored days to judge">
      {forward.map((f, i) => (
        <div key={i} className="py-2.5">
          <div className="flex justify-between gap-3 text-[13px]"><span>{f.name}</span><span className="num shrink-0 text-fg3">{f.days} / {f.need}</span></div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--line)]"><motion.i className="block h-full rounded-full bg-accent" initial={{ width: 0 }} animate={{ width: `${Math.max(2, f.days / f.need * 100)}%` }} transition={{ duration: .9, ease: [.22, 1, .36, 1] }} /></div>
          <div className="mt-1.5 text-[11.5px] text-fg3">{f.logged} days logged since {shortDate(f.first)} · outcomes known to {shortDate(f.through)}</div>
        </div>
      ))}
    </Section>
  </>
}

function Health({ rec, go }: { rec: import('./data').RecordFile; go: Go }) {
  const sq = useSignals()
  const st = rec.health.statuses
  const total = Object.values(st).reduce((a, b) => a + b, 0)
  const [k, setK] = useState('error')
  const rows = (sq.data?.signals || []).filter(s => k === 'stale' ? s.status === 'ok' && !!s.stale : s.status === k)
  const tiles: [string, string, number, string, string?][] = [
    ['ok', 'Have a score', st.ok || 0, `of ${total} signals`],
    ['collecting', 'Collecting history', st.collecting || 0, 'they get a score later'],
    ['awaiting_key', 'Need a key', st.awaiting_key || 0, 'a free key is missing', 'var(--watch)'],
    ['error', 'Failed this run', (st.error || 0) + rec.health.errors.length, 'the next run tries again', 'var(--crit)'],
  ]
  return <>
    <div className="grid grid-cols-2 gap-px overflow-hidden border-y border-line bg-[var(--line)]">
      {tiles.map(([key, a, n, b, col]) => <button key={key} onClick={() => key !== 'ok' && setK(key)} aria-pressed={k === key} className={`bg-panel px-5 py-3 text-left ${key !== 'ok' ? 'hover:bg-hover' : 'cursor-default'} ${k === key ? 'bg-hover' : ''}`}>
        <div className="text-[11.5px] text-fg3">{a}</div><div className="num mt-1 text-[20px] font-medium" style={{ color: n && col ? col : undefined }}>{n}</div><div className="text-[11.5px] text-fg3">{b}</div></button>)}
    </div>
    <Section title={({ error: 'Failed this run', awaiting_key: 'Waiting for a free key', collecting: 'Collecting history', stale: 'Showing the last good copy' } as Record<string, string>)[k]} aside={<button onClick={() => setK('stale')} className="text-accent hover:underline">Stale copies</button>}>
      {k === 'error' && rec.health.errors.map((e, i) => <p key={'e' + i} className="py-1 text-[12.5px] text-fg2">{typeof e === 'string' ? e : JSON.stringify(e)}</p>)}
      {sq.isPending ? <Skeleton lines={4} /> : rows.length === 0 && !(k === 'error' && rec.health.errors.length) ? <p className="text-[13px] text-fg3">None.</p>
        : rows.slice(0, 200).map(s => <button key={s.id} onClick={() => go({ v: 'signal', id: s.id })} className="-mx-2 flex w-[calc(100%+16px)] justify-between gap-3 rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-hover"><span className="min-w-0 truncate text-fg2">{s.label}</span><span className="shrink-0 text-fg3">{k === 'stale' ? `copy of ${s.stale}` : s.sub}</span></button>)}
    </Section>
  </>
}

function Method({ brief }: { brief: Brief }) {
  const g = brief.model.gates
  const live = brief.model.active
  const H = ({ children }: { children: React.ReactNode }) => <h3 className="mb-1 mt-4 text-[14px] font-semibold first:mt-0">{children}</h3>
  const P = ({ children }: { children: React.ReactNode }) => <p className="text-[13.5px] leading-[1.6] text-fg2">{children}</p>
  return (
    <div className="px-5 py-4">
      <H>What you can trust today</H>
      <P>{live ? 'The 30-day model passed its checks at its last refit and sets the levels. Its forecasts are scored here as they mature.'
        : 'The readings are facts about each source: how far it sits from its own normal, and what governments and Crisis Group have published. The timing tells are fixed rules, shown with their record on our own history. The 30-day model has not passed its checks, so its chance is shown only as standing risk, for reference, and sets no level or colour.'}</P>
      <H>1. Each signal against its own history</H>
      <P>Daily data: the latest 7-day average against the 7-day averages of the previous year, leaving out the last 30 days so a slow build-up does not hide itself. With less than 120 days of history, the last 90 days are used. Monthly data: the previous 36 months, with the usual seasonal pattern removed.</P>
      <H>2. Distance from normal</H>
      <P>A modified z-score, 0.6745 × (value − median) / MAD, capped at ±5 so one bad value cannot control the result. Only movement in the warning direction counts; a calm signal never cancels an alarm in another. 2 SD or more is unusual, 3 SD or more is strong.</P>
      <H>3. One event counts once</H>
      <P>Signals that move together (recent changes correlated above 0.8) are averaged into one. Late data, published weeks or months after the fact, counts at 25%, because the aim is early warning.</P>
      <H>4. Groups and the level</H>
      <P>Each of the five groups (Logistics, Markets, People, News, Physical) combines its strongest signals with an ordered weighted average, so the strongest evidence weighs most. The groups combine into one index from 0 to 100. Watch starts at 50 and Critical at 90: the top 10% and the top 1% of a simulated calm world. The level shown is “Quiet” below Watch.</P>
      <H>5. The 30-day chance</H>
      <P>{`A fitted model (v${brief.model.version}, fitted ${shortDate(brief.model.fitted)}) turns the signals and each theatre's conflict history into the chance of a qualifying event in the next 30 days, starting from the theatre's long-run rate.`}{g ? ` On past theatre-months it has a test AUC of ${g.auc.toFixed(2)} (${g.auc_lo.toFixed(2)} to ${g.auc_hi.toFixed(2)}); 0.5 is a coin flip.` : ''}{live ? '' : ' It runs in shadow until it passes all three checks on the Record tab.'}</P>
      <H>6. Timing tells</H>
      <P>A timing tell is a fixed yes-or-no rule over the last 7 days on a costly, hard-to-reverse action: a US departure order, an advisory raise with a UK advice change, airliners thinning out, tankers parked forward, airspace closures, firing warnings at sea, strike waves. Each shows how often it fired before past events. Tells never set a level or enter the model.</P>
      <H>7. Bases on satellite radar</H>
      <P>Sentinel-1 radar passes every few days at 10 m. WarWatch counts bright objects on each base's aprons, harbour and grounds and compares the count with that base's own usual range. Two passes in a row far outside it mark the base as changed. Aircraft in shelters do not show, so a change is a reason to look, not proof.</P>
      <H>8. Context lines</H>
      <P>Lines such as “War under way” are set by hand and checked monthly. They say what the baseline is; they never change a level.</P>
      <p className="mt-4 text-[12.5px] text-fg3">The full method: <a className="text-accent hover:underline" href="https://github.com/khourix/warwatch/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">METHODOLOGY.md</a> and <a className="text-accent hover:underline" href="https://github.com/khourix/warwatch/blob/main/docs/MODEL.md" target="_blank" rel="noreferrer">MODEL.md</a>.</p>
    </div>
  )
}
