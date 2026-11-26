import { GroupBars } from './watch'
import { NowMark, Tag } from './ui'
import { GRADE_WORD, gradeClass, type Grade } from './grade'

/* The component kit: the app's small parts side by side, in the theme the page is in, so a change to one is seen against the rest.
   Development only (open the dev server with ?kit); it is not built into the public site. */
export default function Kit() {
  const row = 'flex flex-wrap items-center gap-3 border-t border-line py-3 first:border-0'
  const h = 'w-[120px] shrink-0 text-[12px] text-fg3'
  return (
    <div className="h-full overflow-y-auto bg-bg p-6 text-fg">
      <h1 className="mb-4 text-[20px] font-semibold">Component kit</h1>
      <div className="max-w-[720px] rounded-r3 border border-line bg-s1 px-4">
        <div className={row}><span className={h}>Type scale</span>{[11, 12.5, 13.5, 16, 20, 27].map(s => <span key={s} style={{ fontSize: s }}>{s}</span>)}</div>
        <div className={row}><span className={h}>Ink</span>{['fg', 'fg2', 'fg3'].map(c => <span key={c} className={`text-${c}`}>{c}</span>)}<span className="text-happened">happened</span></div>
        <div className={row}><span className={h}>Build-up</span>{['z1', 'z2', 'z3', 'crit'].map(c => <i key={c} className="h-4 w-8 rounded-[3px]" style={{ background: `var(--${c})` }} title={c} />)}</div>
        <div className={row}><span className={h}>Now</span><NowMark now="war" /><NowMark now="strikes" /><NowMark now="tension" /><NowMark now={null} /></div>
        <div className={row}><span className={h}>Group bars</span>
          <GroupBars g={{ Logistics: 0.2, Markets: 0.2, People: 0.2, News: 0.2, Physical: 0.2 }} />
          <GroupBars g={{ Logistics: 0.5, Markets: 1.5, People: 2.5, News: 3.5, Physical: null }} />
          <GroupBars g={null} /></div>
        <div className={row}><span className={h}>Evidence</span>{(['official', 'corroborated', 'single', 'claim'] as Grade[]).map(g => <span key={g} className={gradeClass(g)}>{GRADE_WORD[g]}</span>)}</div>
        <div className={row}><span className={h}>Tags</span><Tag>Plain</Tag><Tag mark="var(--z2)">Watch</Tag><Tag mark="var(--z3)">Elevated</Tag></div>
        <div className={row}><span className={h}>Buttons</span>
          <button className="inline-flex h-8 items-center rounded-r2 border border-line px-3 text-[12.5px] text-fg2 hover:bg-s2 hover:text-fg">Secondary</button>
          <button className="inline-flex h-8 items-center rounded-r2 bg-sel px-3 text-[12.5px] font-medium text-selink">Selected</button>
          <button className="lnk text-[12.5px]">Link</button></div>
      </div>
    </div>
  )
}
