# Knowledge Workspace — Edmonton Fire Rescue Response

> **Opportunity (one sentence):** Give an Edmonton Fire Rescue Services operations
> performance lead a view of **how long events tie up crews and apparatus, and where and
> when that workload concentrates**, so they can decide where turnaround and demand are
> drifting from the historical norm — *without* claiming a response (arrival) time the data
> cannot support.

This folder is the **stocked, curated Knowledge** for the project, built before any dashboard.
The method: connect the source and the document that explains it,
then record only **what the agent cannot guess** (the Deletion Test).

## What's here

| File | What it carries | Why it earns its place |
| :--- | :--- | :--- |
| `data-source.md` | Where the data lives: local file + the **live Edmonton API**, plus the companion Fire Stations source. | Connect the source, don't paste a fragment. |
| `data-dictionary.md` | Curated meaning of each column; points at the official Edmonton dictionary. | The codebook — numbers without meaning are read confidently and wrongly. |
| `data-cautions.md` | **The load-bearing note.** What the agent cannot guess: duration ≠ response time, partial 2026, UNKNOWN geography, undocumented codes, training records mixed in. | Delete a line here and a wrong number ships. |
| `data-profile.md` | A profiled snapshot of the actual file: size, coverage, event mix, duration distribution, quality flags. | What one row is and how representative the data is. |
| `research/edmonton-fire-response-domain.md` | Distilled domain note on EFRS and response-time standards — **treated as claims to verify, not facts.** | Domain context the agent needs but can't read off the columns. |
| `Class/` | Course materials (assignment brief, overview, Day 1 deck). | Source material, kept separate from curated knowledge. |

## The data, in one breath

~946K Edmonton Fire Rescue dispatch events, **Jan 2011 → 25 Jun 2026**, one row per event.
**57% are medical calls, 15% are alarms**; real fires are ~2.5%. Each row has when, where
(neighbourhood + nearest intersection), what (event type), which units were sent, and a total
event duration. Updated daily from the City of Edmonton open data portal.

## The discipline this workspace is graded on

*Curation, not accumulation.* Every line in `data-cautions.md` would change the next run if
deleted. Everything the agent can read for itself (that there is a `neighbourhood_name` column,
that months run 1–12) is deliberately **not** written here. The codebook is pointed at, not retyped.
