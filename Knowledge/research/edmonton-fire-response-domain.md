# Research Note — EFRS Response & Duration (claims to verify)

*Distilled domain context the agent needs but cannot read off the columns. **Treat every line as a
claim to verify, not a fact.** Verify load-bearing claims before a dashboard asserts them. Status
tags: [SOLID] grounded in this dataset / official metadata · [VERIFY] plausible, confirm before relying.*

## Why this matters for the opportunity
The chosen opportunity is **duration & workload monitoring**. The single biggest domain risk is
conflating "event duration" with "response time" — a distinction fire services treat as fundamental.
Getting the vocabulary right *is* the project's credibility.

## The anatomy of a fire-service response (the vocabulary)
A standard incident timeline runs: **call received → call processing → turnout → travel →
arrival on scene → on-scene time → last unit clears**. [VERIFY]
- **Total response time** normally means *call received → arrival on scene*. [VERIFY]
- This dataset gives us only **dispatch → close**. It has **no call-received, no arrival, and no
  on-scene timestamp**. [SOLID — confirmed from official field definitions]
- Therefore the only honest metric here is **total event handling/open time**, which overlaps with
  none of the standard response-time segments cleanly. Frame accordingly (see `data-cautions.md` #1).

## Response-time standards (context only — we cannot measure against them)
- **NFPA 1710** sets benchmark response-time objectives for career fire departments (commonly cited:
  ~240 seconds travel time for the first engine, met ~90% of the time). [VERIFY — confirm exact
  figures and current edition before quoting]
- Edmonton Fire Rescue Services reports response-time performance in its own public reporting, but
  those figures come from its CAD system, **not from this open dataset**. [VERIFY]
- **Implication:** if a stakeholder asks "are we meeting our response standard?", this dataset
  cannot answer it. Name that boundary rather than approximating.

## What this data IS good for
- **Demand & workload patterns** — volume by neighbourhood, hour, weekday, season, event type. [SOLID]
- **How long different event types tie up units** (duration distributions by class). [SOLID]
- **Trend** — multi-year growth in call volume (volume ~doubled 2011→2024). [SOLID, this dataset]
- **Where the core load sits** — downtown/inner-city neighbourhoods dominate. [SOLID, this dataset]

## Domain facts worth confirming
- **Medical dominance:** ~57% of events are medical, not fires. Fire services across North America
  increasingly function as medical-first responders; Edmonton fits the pattern. [VERIFY the framing,
  SOLID for this dataset's share]
- **Co-response with EMS:** in Alberta, ground ambulance is run by Alberta Health Services, while
  EFRS provides medical first response — which is why medical calls dominate a *fire* dataset. [VERIFY]
- **Seasonality:** outside/grass fires are expected to spike in dry spring/summer months; worth
  testing in the data rather than assuming. [VERIFY against the data]

## Open questions to resolve before/while building
1. Confirm `response_code` values with Edmonton Open Data, or commit to not using them.
2. Decide the `UNKNOWN` neighbourhood policy (drop / bucket / footnote) and write it into the spec.
3. Confirm the exact NFPA 1710 figures and EFRS's own reported standard *if* the dashboard
   references benchmarks at all (recommended: it should not claim to measure them).
