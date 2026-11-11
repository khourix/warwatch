# Event desk: plan, fixed before the blind test is run

Committed 2026-11-09 with `warwatch/eventdesk.py`, before any LLM has answered a test question. Part P1 of [ACCURACY_PROPOSAL.md](ACCURACY_PROPOSAL.md), approved by the owner on 2026-11-09. Nothing here writes `warwatch/data/events.csv`: the desk proposes, a person approves each row, and approved rows are added by hand under [EVENTS.md](EVENTS.md).

## Why

Every score in WarWatch is read against the event list. The list is complete only to 2026-10-12, so no forward forecast has matured, and 2026 may be missing events (12 listed to 12 October, against 33 in 2024 and 31 in 2025). The desk keeps the list current.

## What the desk does

For each of the 17 areas (13 theatres and 4 sub-theatres) and each 14-day window, it reads public Google News search results for the area and asks a free LLM to list the qualifying events under the codebook, each with the ids of the headlines that report it.

- **Headlines.** One query per place name, per action list, per 7 days (`PLACES`, `ACTIONS` in `eventdesk.py`). Google News ignores the date limits on queries longer than about 15 terms, which is why each query is short. Title, outlet and date only; at most 160 per window, shared across days.
- **Answer.** JSON only. A candidate is kept only if it cites at least one real headline id, has one of the five types, a date inside the window and a date no later than its last cited headline.
- **Models.** `openai/gpt-oss-120b` on Groq's free plan (knowledge cutoff June 2024, OpenAI model card) and `gemini-3.5-flash-lite` on Google's free tier. Exact model versions are written to every answer.

## The blind test

| Item | Fixed value |
|---|---|
| Window | 2024-07-01 to 2025-12-31 (after gpt-oss-120b's cutoff), 40 windows of 14 days (the last one 3 days), 17 areas: 680 questions per model |
| Blind | The prompt never lists a known event. Every model reads exactly the same cached headlines (`backtest/eventdesk/news/`). |
| Listed events in the window | 51 (`events.csv` today) |
| Found | A listed event is found when a kept candidate in one of its areas (its theatre or any `site_theatre`) is dated within 3 days of it |
| Recall | Found events divided by listed events in the window |
| Extras | Kept candidates that match no listed event (3 days) and do not fall in the 30 days after a listed event in the same area (the codebook's continuation rule; counted separately), merged to one per area per 30 days |
| Review | A random sample of 40 extras (seed 20261109) goes to `backtest/eventdesk/review_<provider>.csv`. Each is judged against the codebook from its cited headlines and a check of the public record: `yes` if it is a qualifying event that the list is missing, `no` otherwise. Reviewer: the agent, with the table shown to the owner. |
| Pass | Recall 0.90 or more, **and** at least half of the reviewed extras judged `yes` |
| Order | gpt-oss-120b (Groq) is the primary test, because the window is new to it. Gemini is also run and reported, marked as possibly flattered: its training covers the window. The desk goes live on Groq if Groq passes; on Gemini only if Groq fails and Gemini passes, and then it is said on every candidate page. |
| Answers that are not JSON | Counted as answered with no candidates. No retry. |

**Feasibility check made before this plan was fixed.** On 12 listed events from the window (random, seed 7), the headlines were read by hand without any model. 10 of 12 were plainly reported. The two that were not (the Baltic cable cuts of November 2024 and the HTS offensive in Syria of November 2024) led to two changes: a second action list (`drills`, `exercise`, `blockade`, `seized`, `sabotage`, `cable`, `coup`, `troops`, `warships`) and the place names `Aleppo` and `Idlib`. No LLM was run. These 12 events stay in the test.

## Pace and cost

Free plans only, $0. Groq allows about 40 desk questions a day (200,000 tokens a day), so the Groq test takes about 17 days. Gemini runs up to 200 a day. The daily `eventdesk` workflow resumes where the last run stopped and writes `docs/EVENTDESK_TEST.md` as answers accumulate. A provider whose key is not set is skipped.

## After the test

- **Pass:** the weekly run (Mondays) proposes candidates from the day after `events_through.txt` to yesterday, with the listed events of the area shown to the model so it does not repeat them; candidates within 3 days of a listed event are dropped and those in a listed event's 30 days are marked. Output: `warwatch/data/event_candidates.csv` and `docs/EVENT_CANDIDATES.md`. The 2026 backlog (1 January to 12 October) is run once the same way. `propose` refuses to run while `backtest/eventdesk/verdict.json` does not say pass.
- **Fail:** recorded as it is. The list is kept current by hand, as now, and the result decides whether a different design is worth a new plan.
- Recall and the review are repeated each quarter on the newest approved events.
