# Edmonton Fire Rescue — Incident Duration & Workload Monitor

Final report of a five-person team project (July 2026): a deployed dashboard that turns
946K raw dispatch rows into a normed, decidable picture of how long incidents tie up crews
and where workload is drifting from the historical norm.

- **Deployment:** deployable to Render's free tier in minutes from this repo ([DEPLOY.md](../DEPLOY.md)); runs locally with one command
- **Data:** City of Edmonton Open Data `7hsn-idqi` (Fire Response, Current & Historical), updated daily
- **Built in an agentic coding workspace governed by [`AGENTS.md`](../AGENTS.md)**

## 1. Opportunity & creativity

The user is an **Edmonton Fire Rescue operations / performance lead** — someone who owns
every figure that goes up to the deputy chief and can act on the view weekly. The decision
the dashboard supports is narrow and real: **where and when to direct next week's attention,
staffing focus, and follow-up review**, based on which event types, neighbourhoods, and hours
are running abnormally against their own historical norm.

The concept was chosen *before* the dataset, against three locked criteria:
(1) the data can honestly carry the claim, (2) a real owner can act on it weekly,
(3) it needs the dataset's depth, not a single chart. Incident duration & workload
monitoring passed all three. Two alternatives the same data seemed to invite were
rejected on purpose:

| Candidate | Verdict & reason |
|---|---|
| **Incident duration & workload monitoring** | **Chosen.** Passes all three criteria; duration and volume are directly supported by the data. |
| Response-time / NFPA benchmarking | **Rejected.** Fails criterion 1 — the data has *no arrival or call-received timestamp*, so a response-time claim would be worth less than nothing: someone would act on a number that doesn't mean what it says. Kept as an explicit refusal (see §5 governance). |
| False-alarm reduction | **Parked.** Viable but narrower; `response_code` is undocumented, weakening the alarm-cause angle. |

The creativity is in the discipline, not the flash. The obvious build — a "response time
dashboard" — is the one the data cannot support, and refusing it is the design decision
that makes the rest trustworthy. The value is turning 946K rows of raw CAD dispatch data
into a comparison the lead currently *cannot make* without manual pulls: recent volume and
handling time read against the median of the same calendar window across the five prior years.

### Three user stories — benefit first

- **Story #1 — "Are fire cases running hot?"** (Operations/Performance Lead). Monday morning
  before the ops review: is recent fire volume genuinely above where it normally sits, or does
  it just feel that way? The monitor reads the current-window count against the **median of
  the same window across five prior years**, N attached — a number she can defend, not a hedge.
  *This is the story the app must not fail.*
- **Story #2 — "Are incidents taking longer to clear?"** (Operations/Performance Lead). She
  reads **median handling time (dispatch→close)** for the recent window against its five-year
  median for the same window, each with N — labelled for exactly what it is, never as a
  response time.
- **Story #3 — "Which areas are lighting up?"** (District Chief). Before the duty-officer
  briefing, the early-warning map highlights neighbourhoods running above their **own**
  five-year norm, shaded by how far above — so he briefs by name: "Rundle is above its norm;
  send your officer there."

## 2. Specification

The project is governed by a single living specification, [`AGENTS.md`](../AGENTS.md), read at
the start of every build session. It is not a summary written after the fact — it *directs*
the build and was revised as the project developed. It contains everything a fresh session
needs to reproduce the same app.

| Spec section | What it locks down |
|---|---|
| **§0 User stories** | Three ranked stories, benefit-first, Story #1 as the bar every decision is judged against. |
| **§1 Objective** | A "no-dataset sentence," the decision it changes, the owner, and the center of gravity: *duration and volume against a baseline*. |
| **§2 What good looks like** | Testable honesty rules + a **gold example** the build must reproduce + a **must-never-produce** list. |
| **§3 Scope** | Smallest valuable version, one stretch, and an *out-of-scope* list as specific as the core (response time, station performance, address-level mapping, causal claims). |
| **§4 Data** | Source, what one row is, representativeness, what blanks mean, and the load-bearing duration definition. |
| **§5 Capabilities** | The seam: what is fixed/hard-coded vs. left to the agent's discretion. |
| **§6 Human-in-the-loop** | The lead has the final word; refusal is a feature; overrides are logged. |

Two things make it a *usable* spec rather than prose. First, the success criteria are written
to be tested — e.g. "every duration figure is labelled event handling time (dispatch→close),
never response time," and "the distribution's final bar is an explicit `55+` catch-all, never
a bounded 55–60 label that hides the tail." Second, the spec was **revised after the
deployment week**: it now carries the fixed behaviours, a "Verify before shipping" checklist
with the exact oracle numbers, and a candid **"Gaps left open on purpose"** section naming
what was deferred and why.

> Gold example (the centerpiece the build must reproduce): *"Motor Vehicle Incidents — Q2 2026
> vs Q2 2021–2025 norm. Median handling time 27 min (p90 58), n = 3,140 this quarter vs a
> 5-year Q2 median of 26 min. Volume +8% above the Q2 norm, concentrated 15:00–18:00 in
> Downtown and Boyle Street. Handling time is stable; volume is up. Note: handling time is
> dispatch→close, not arrival time. UNKNOWN-neighbourhood events (12%) excluded from the
> geographic split."*

## 3. Data & context

The dashboard reads its source **directly, not pasted in**. A frozen snapshot
(`Fire_Response_Current_and_Historical_20260626.csv`, ~946,250 rows × 25 columns,
2011–25 Jun 2026) builds the cache, and the **live SODA API `7hsn-idqi` is an active
incremental connector**: `/api/refresh` pulls rows newer than the current max dispatch
timestamp. The city updates daily, so "live" means daily-fresh. Neighbourhood boundary
polygons (2019, dataset `xu6q-xcmj`) are frozen in `neighbourhoods.geojson` for the map.

| | |
|---|---|
| **946,250** | raw dispatch rows (2011 → 25 Jun 2026) |
| **890,938** | valid incidents after fixed cleaning |
| **57% / 15%** | medical / alarms — not primarily a fire dataset |
| **~13%** | literal `UNKNOWN` neighbourhood (a value, not missing) |

Context is where this dataset is dangerous, and the spec's
[`Knowledge/data-cautions.md`](../Knowledge/data-cautions.md) is load-bearing. The most
important line: `event_duration_mins = event_close_datetime − dispatch_datetime` is **total
handling time, not response time** — the data has no arrival or call-received timestamp.
Other cautions carried into every metric: non-incident administrative records
(`TRAINING/MAINTENANCE`, `COMMUNITY EVENT`, `PRE-INCIDENT PLANNING`, `PERMIT-BURNING`) are
excluded before any metric; 2026 is partial (Jan–Jun) and only ever compared year-to-date;
`UNKNOWN` is a literal value with a stated policy; `response_code` is undocumented (only
`AL` ≈ ALARMS is safe); locations are geocoded to the nearest intersection; and there is no
station or apparatus-ID field.

> ✔ **Data grounding, independently verified against the CSV.** Recomputing from the raw file
> reproduces the spec's headline figures exactly: 890,938 valid incidents; default Jan 1 →
> Jun 25 window = 427,500 rows at 11.4% UNKNOWN; and the Motor Vehicle Incident oracle (§5)
> matches to the digit. The dashboard's output is grounded in the data, not asserted.

## 4. The build

A working, deployed dashboard: a **Flask backend** (`app/server.py`, pandas + numpy,
gunicorn in prod) and a single-file **white-themed SPA** (`app/static/index.html`,
Chart.js + Leaflet) with a left sidebar and four pages — *How to use · Overview · Forecast ·
Ask the data*. Deployment is GitHub → Render (Python web service, `render.yaml` + `Procfile`).
On first run the app parses the 946K-row CSV in ~11s to build a ~60 MB cleaned cache; later
starts load from cache in ~1s, so it runs without the 315 MB CSV.

### Endpoints (every payload carries N and a 5-year baseline for the same window)

| Endpoint | What it returns |
|---|---|
| `/api/meta` | Years, event types, window label, exclusion note, UNKNOWN %, N, data cutoff, equipment vocabulary, refusal/refresh log counts. |
| `/api/metrics` | Five KPIs (median +Δ vs 5-yr median, p90, N, volume +% vs norm, committed event-hours), distribution + baseline, by-hour/weekday, weekday×hour heat matrix, by-type, by-equipment, and filter-aware "top movers." Insights are descriptive only. |
| `/api/forecast` | Monthly volume forecast (seasonal mean × level factor from completed months only; ~80% interval), never plotting the partial current month as a full bar. Volume only — never response time, never causal. |
| `/api/geo` | Per-neighbourhood centroid, count, median, 5-yr expected, % divergence, and tier (above/normal/below) — powers the early-warning choropleth. |
| `/api/refresh` | Incremental live SODA pull, same fixed cleaning, appends + re-derives + re-caches, logged. Idempotent (a second call adds 0). |
| `/api/ask` | The chatbot — a fixed, code-owned routing order (refusal gate → on-topic gate → editorial → query-planner → decision-support → forecast → basic KPI). |

### The agentic workspace

The build was directed from an agentic coding workspace, and three project capabilities take
the form of **agent skills** installed under `.agents/skills/`, each mirrored in the backend
code so the honesty rules hold at runtime, not just at authoring time:

| Skill | Posture | Job |
|---|---|---|
| `incident-data-guard` | **Hard gate** | Cleans the dispatch rows to the fixed standard and errors on un-fixable input *before* any metric is computed. |
| `claim-guard` | **Advisory** | Flags the forbidden "response time" claim, full-year-2026 totals, and undocumented-code meanings; drives refusals and logs them. |
| `presentation-render` | **Deterministic** | Stages the written brief in a fixed order with every required label guaranteed (same input → same output). |

The chatbot's optional phrasing layer uses Gemini (via Vertex AI) purely to *rephrase* an
already-computed, already-correct answer; every number still comes from the deterministic
backend, and the refusal and on-topic gates run in code before any model call. Language from
the model, truth and governance from code.

> ✔ **Oracle reproduced (the build's real test), verified against the raw CSV.**
> Motor Vehicle Incident · 2026 · window Jan 1 – Jun 25 vs 2021–2025 →
> **median 26 min, p90 69, n = 2,919, volume +35% vs the 5-yr norm**.
> Geo spot-check: Downtown MVI 2026 = **54** events (median 19.5). Both match the deployed API exactly.

## 5. Evaluation & governance

Because a single deployment week is thin evidence, the team built a test of the *output*
(not the code): a set of known-answer cases with the output a good answer would give,
recomputed independently and reviewed by hand. A baseline was measured, fixes were made, and
measured again. Three streams of evidence fed the loop: a **machine critic** (10 findings,
fresh context, never saw the source code), **human pitch feedback** (3 notes), and the
**use-week logs**. Every item got a verdict and a reason, and Story #1 settled every call:
*if the lead would say the number out loud in a review, it got fixed; if the user never sees
it, it was parked and said so.*

### Before → after (same app, same snapshot, re-run against the same brief)

| Check | Before | After |
|---|---|---|
| Oracle — MVI 2026 vs 2021–25 | 26 / 69 / 2,919 / +35% | **Unchanged** — the fixes didn't move the real numbers |
| **F1** distribution last bar | `55-60 : 1403` (really ≥55; hides the tail) | `55+ : 1403` — labelled as the catch-all it is |
| **F2** footer total / UNKNOWN | 450,433 · 15.1% (junk rows kept) | **427,500 · 11.4%** — reconciles with every chart |
| **F3** forecast tail | partial June drawn as a full month (fake collapse) | partial month returned separately, drawn as a hollow point |
| **F4** no-baseline slice (Vehicle Fire 2011) | asserted "handling time is down" against a non-existent baseline | "handling time can't be compared — no 5-year baseline for this period" |
| **F5** "which station is the slowest?" | not refused — answered with a citywide KPI | **refused & logged** (and "gas station downtown" is *not* refused) |
| **F7** forbidden ask via `{"question":…}` key | bypassed the gate, unlogged | **refused & logged** — gate closed on both request keys |

### Known-answer test suite — recomputed independently, not model-scored

Each case was paired with the output a good answer must give; the dashboard was checked
against them by recomputing the numbers from the CSV independently and reading the narrative
output by hand. Measured at the initial baseline, fixed, and measured again after the
revision: **baseline 6 / 12 pass → revised 12 / 12 pass.**

| # | Test case | Expected good answer | Day 2 | Day 3 |
|---|---|---|---|---|
| 1 | Oracle: MVI 2026 YTD vs 2021–25 | median 26 · p90 69 · n 2,919 · vol +35% | PASS | PASS |
| 2 | Geo spot-check: Downtown MVI 2026 | 54 events · median 19.5 | PASS | PASS |
| 3 | Footer reconciles with charts (default window) | n = 427,500 · UNKNOWN 11.4% (junk dropped) | FAIL | PASS |
| 4 | Distribution last bin label | `55+` catch-all, not `55-60` | FAIL | PASS |
| 5 | Forecast last *actual* point | complete month; partial June returned separately | FAIL | PASS |
| 6 | No-baseline slice (Vehicle Fire 2011) | "can't be compared — no 5-year baseline" | FAIL | PASS |
| 7 | Chatbot: "average response time?" | refuse + log (data has no arrival time) | PASS | PASS |
| 8 | Chatbot: "which station is slowest?" | refuse + log (no station field) | FAIL | PASS |
| 9 | Chatbot: "gas station downtown" (control) | *not* refused — unrelated place type | PASS | PASS |
| 10 | Forbidden ask via `{"question":…}` key | refuse + log (gate closed on both keys) | FAIL | PASS |
| 11 | Off-topic ask ("meaning of life") | redirected, not a stray KPI | PASS | PASS |
| 12 | Decision ask: "plan crews for downtown fire" | volume vs norm + peak hour + outlook, "the staffing call is yours" | PASS | PASS |

Cases 1, 2 and 9 are the controls that must *not* change — they held, confirming the fixes
corrected the failures without disturbing the correct numbers or over-refusing.

Verdicts: F1 (blocker) and F2–F5, F7 were **fixed** — each is exactly the kind of figure
repeated in a room that then falls over. Five minor findings (F6, F8–F10) and the deck
rewrite were **deferred on purpose**, each named with its reason in the spec, because
loosening an unseen contract or a one-neighbourhood rounding gap doesn't change where a
chief sends an officer.

### Governance & human-in-the-loop

The performance lead has the final word — **the app informs, it does not decide**. Three
governance points are built in and visible:

- **Refusal is a feature.** Asked for a response/arrival time, an NFPA benchmark, or
  station-level performance, the app declines and explains why the data can't support it —
  and *logs* the refusal. Prescriptive/decision-support text appears in exactly one place,
  the chatbot; the Overview and Forecast pages are descriptive only.
- **Override logging.** Any time a user overrides a default (includes `UNKNOWN`, changes
  the baseline, re-includes a non-incident type), the app records the override and the reason.
- **A live governance panel** on the guide page shows valid-N vs raw-N, UNKNOWN %, refusals
  logged, and refreshes run — straight from `/api/meta`.

> The clearest lesson came free from the use-week log: the single most-requested thing —
> asked over a dozen times, almost all "what was the average response time?" — is the one
> thing this data honestly cannot give. That is not a bug in demand; it is the reason the
> refusal is a headline feature, and why the guide page states the dispatch→close limitation
> up front.

## 6. What's next

Close the deferred minor items (F6 dead recommendation strings, F8 hotspot-count drift, F9
the placed `UNKNOWN` point), make the pitch material less text-heavy and more benefit-first,
and harden the chatbot's query-planner coverage. None of these change what the lead can
defend on Monday — which was always the bar.

---

*File inventory behind this report: [`AGENTS.md`](../AGENTS.md) (living spec) ·
`app/server.py` (Flask backend) · `app/static/index.html` (SPA) ·
`app/static/neighbourhoods.geojson` · `.agents/skills/{incident-data-guard, claim-guard,
presentation-render}/` · `evaluation/` (deployment assessment, machine + human critic
findings) · `render.yaml` + `DEPLOY.md`. Numbers in this document were re-verified against
the raw City of Edmonton snapshot on July 4, 2026.*

*Duration is **event handling time (dispatch→close)**, never response or arrival time.
Non-incident records (`TRAINING/MAINTENANCE`, `COMMUNITY EVENT`, `PRE-INCIDENT PLANNING`,
`PERMIT-BURNING`) are excluded from all operational metrics. 2026 is partial (Jan–Jun) and
only ever compared year-to-date. Data: City of Edmonton Open Data `7hsn-idqi`, updated
daily. Contains information licensed under the Open Government Licence – Edmonton.*
