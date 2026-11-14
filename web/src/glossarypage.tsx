import { useEffect } from 'react'
import { TERMS, ORDER } from './glossary'
import { Crumbs } from './views'
import { Lnk } from './ui'
import type { Route } from './data'

/* The glossary: every term the explainers use, from glossary.ts, in one list. Each has an anchor (#sd, #tripwire) to link to. */
export function GlossaryView({ go, term }: { go: (r: Route) => void; term?: string }) {
  /* an address with a term (/glossary/#sd, an explainer's link, the command menu) opens the page at it */
  useEffect(() => {
    if (!term) return
    let n = 0, id = 0
    const find = () => { const el = document.getElementById(term); if (el) { el.scrollIntoView({ block: 'start' }); el.focus({ preventScroll: true }) } else if (n++ < 40) id = requestAnimationFrame(find) }
    id = requestAnimationFrame(find); return () => cancelAnimationFrame(id)
  }, [term])
  return (
    <div className="pb-8">
      <Crumbs back={{ v: 'brief' }} items={[['Watch', { v: 'brief' }], ['Glossary']]} go={go} />
      <div className="px-5 pb-2 pt-2">
        <h1 className="text-[27px] font-semibold leading-[1.1] tracking-[-0.028em]">Glossary</h1>
        <p className="mt-2.5 font-serif text-[17px] leading-[1.42] text-fg [text-wrap:pretty]">What WarWatch's words and numbers mean, and where each comes from. The same sentences open when you tap a dotted term anywhere in the app.</p>
      </div>
      <dl className="mx-5 mt-3 rounded-r3 border border-line bg-s1 px-4">
        {ORDER.map(k => { const t = TERMS[k]; return (
          <div key={k} id={k} tabIndex={-1} className="scroll-mt-4 border-t outline-none border-line py-3 first:border-0">
            <dt className="text-[14px] font-medium text-fg">{t.term}</dt>
            <dd className="mt-0.5 text-[13px] leading-[1.5] text-fg2"><span className="text-fg">{t.says}</span> {t.from}</dd>
          </div>) })}
      </dl>
      <p className="mx-5 mt-3 text-[12.5px] text-fg2">How the numbers have done, and the model's checks, are on the <Lnk to={{ v: 'record' }} go={go} className="lnk">Record</Lnk>.</p>
    </div>
  )
}
