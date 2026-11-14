/* The app's terms, written once. Each says what the word or number means, then where it comes from; the explainers (ui.tsx,
   Explain) and the glossary page read them from here, and warwatch/pages.py names them in the glossary's link preview.
   Every sentence follows the pipeline file it cites: change the code, change the sentence. */

export type Term = { term: string; says: string; from: string; see?: string }

export const TERMS = {
  /* engine.logistic_score: 0 to 100, 50 at the Watch threshold and 90 at the Critical one; the thresholds are percentiles of a
     simulated calm world (engine.PCTS 0.90, 0.95, 0.99) */
  unusual: { term: 'Unusual readings', says: 'A number from 0 to 100 for each theatre that says how far its signals sit from their own usual levels today, taken together. It is not a chance of war.',
    from: 'Built every run from the five signal groups. It has not shown that it can forecast, so it is drawn in grey.' },
  lines: { term: 'Watch, Elevated and Critical', says: 'Lines on the 0 to 100 reading. In a simulated world with no build-up, a theatre reads below Watch (50) on 90% of days, below Elevated on 95% and below Critical (90) on 99%.',
    from: 'Where Elevated sits differs a little by theatre, because each theatre has its own mix of signals. While the 30-day model is off, the reading against these lines sets the level.' },
  quiet: { term: 'Quiet', says: 'The level of a theatre whose reading is below its Watch line.', from: 'It says the signals are near their usual levels, not that nothing is happening there.' },
  tripwire: { term: 'Tripwire', says: 'A fixed yes or no rule over the last 7 days on a costly, hard to reverse step, such as a US embassy departure order, airliners thinning out or airspace closing.',
    from: 'Each is replayed on the stored history to show how often it fired before past events. Tripwires never set a level and do not enter the model.' },
  standing: { term: 'Standing risk', says: "The 30-day model's chance for a theatre divided by that theatre's usual chance, so 1.5 means one and a half times its usual.",
    from: 'The model has to pass three checks before it counts. Until then this is shown for reference and sets no level or colour.' },
  sd: { term: 'SD', says: "How far a signal sits from its own usual level, counted in steps of its usual spread (standard deviations). 2 or more is unusual, 3 or more is strong, and readings stop at 5.",
    from: 'Each signal is compared with its own history (a year of daily values, or three years of monthly ones) using the median and the median absolute deviation, so one odd value cannot dominate. Only movement in the warning direction counts.' },
  strong: { term: 'Strong signal', says: 'A scoring signal that reads 3 or more from its own usual: 3 SD for most series.',
    from: 'Travel-advisory sums read 3 for each level they moved in 14 days, and ratings such as Crisis Group 2.5 for each point, so those are counted in their own steps, not SD.' },
  group: { term: 'Signal groups', says: 'The five families every signal belongs to, from the slowest to move to the fastest: Logistics, Markets, People, News and Physical.',
    from: "A group's number is its strongest signals combined, in SD. Signals that move together count once." },
  Logistics: { term: 'Logistics', says: 'Armies must buy, ship and stock before they fight: contracts, tenders and trade flows.', from: 'It moves months ahead. Its data often arrives late, and late data counts at a quarter.' },
  Markets: { term: 'Markets', says: 'Money moves before armies: defence stocks, currencies, fuel and prediction markets.', from: 'It moves days ahead.' },
  People: { term: 'People', says: 'What governments, airlines and citizens do when they expect trouble: advisories, evacuations and alerts.', from: 'It moves days to hours ahead.' },
  News: { term: 'News', says: 'How the news and event record shifts: warning language and military-posture events.', from: 'It moves hours to days ahead.' },
  Physical: { term: 'Physical', says: 'Observable physical activity: aircraft, ships, jamming, closed airspace and internet blackouts.', from: 'It moves hours ahead.' },
  /* basewatch.py STATE_WHY and its counts */
  bright: { term: 'Bright objects', says: "Metal things such as aircraft, vehicles and ships show as bright points on radar. WarWatch counts them on a base's aprons, harbour or grounds and compares the count with that base's own usual range.",
    from: 'Sentinel-1 radar at 10 m, a pass every few days. Radar cannot tell what each object is, and aircraft in shelters do not show, so a change is a reason to look, not proof.' },
  /* firereview.py: dNBR 0.27 or more over the central kilometre; 1 hectare or more is a scar */
  scar: { term: 'Burn scar', says: 'Ground that turned dark in short-wave infrared between a clear Sentinel-2 picture before a fire and one after. At least 1 hectare burnt over the central kilometre counts as a scar.',
    from: 'An automatic reading, not a person\'s. A scar shows that something burned, not what caused it.' },
  /* gfw.py: Sentinel-1 detections with no matching AIS, inside its waters boxes */
  dark: { term: 'Dark ships', says: 'Vessels seen on satellite radar that sent no matching AIS position signal, counted by Global Fishing Watch in 10 km squares.',
    from: 'Covered only inside its waters boxes: the Gulf, the Red Sea, the East Mediterranean, the Black Sea, the Taiwan Strait, the South China Sea, Korea and the Caribbean. The data runs a few days late.' },
  /* gfw.py: Global Fishing Watch's loitering events, which cover carrier vessels only */
  loiter: { term: 'Loitering', says: 'A carrier vessel, the kind of cargo ship that takes on catch from fishing boats at sea, that slowed or drifted for hours, as Global Fishing Watch records it. Other ships are not counted.',
    from: 'Covered only inside the same waters boxes as dark ships, a few days late. It can mean waiting for a berth as easily as anything else.' },
  forward: { term: 'Forward record', says: "Every day WarWatch writes the model's chance for every theatre to a log before anything happens. Each line carries a fingerprint of the one before, so the log cannot be changed afterwards without it showing.",
    from: "A forecast is scored once its horizon has passed (30 days; 7 for the strike-wave target) and the event list has caught up with it. It is the planned harder test, read in full after 365 counted days; today the model is switched on only if it passes its three checks at a monthly refit." },
} satisfies Record<string, Term>

export type TermKey = keyof typeof TERMS
export const term = (k: TermKey): Term => TERMS[k]
/* the order the glossary page lists them in */
export const ORDER: TermKey[] = ['unusual', 'lines', 'quiet', 'sd', 'strong', 'group', 'Logistics', 'Markets', 'People', 'News', 'Physical', 'tripwire', 'standing', 'forward', 'bright', 'scar', 'dark', 'loiter']
