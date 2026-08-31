# AGENTS.md — Living Spec

**Project:** Edmonton Fire Rescue — Incident Duration & Workload Monitor
**Read this file at the start of every run.**

Knowledge backing this spec lives in `Knowledge/` (`data-cautions.md` is load-bearing — read it).

---

## 0. User Stories (who this is for — read before §1)

Stories ranked sharpest first. Story #1 is the one the critic plays all day; the app **must not** fail it.
Each story names the role, what they're trying to do, before-vs-after, and a STAR breakdown.

### Story #1 — Are Fire Cases Running Hot?

**Role:** Dana — EFRS **Operations / Performance Lead**, who owns every figure that goes up to the deputy chief.

It's Monday morning before the ops review , and Dana needs to know one thing: is the recent volume of fire cases actually above where it normally sits, or does it just feel that way ? Before the monitor she'd eyeball raw totals in a two-year-old spreadsheet with no history in front of her and write "seems elevated," because there was never time to answer "up from what?" Now she opens the monitor and reads the fire-case count for this window against the **median of the same window across the five prior years**, N attached to every figure . The recent count sits clearly above the historical median, so she walks into the review able to say fire volume is genuinely running hot — a traceable number she can defend — instead of a hedge she can't .

### Story #2 — Are Incidents Taking Longer to Clear?

**Role:** Mary — EFRS **Operations / Performance Lead**, prepping the same Monday review.

Volume is only half the picture; Mary also needs to know whether crews are being tied up longer than usual on each case , so she can tell whether recent incidents are clearing beyond their normal handling time . She used to have no way to check this — the CAD export gave her totals, not a sense of whether each event ran long, and asking for "response time" was off the table because the public data has no arrival timestamps. Instead she reads **median handling time (dispatch→close)** for the recent window against its **five-year median for the same window**, each with its N . When recent cases sit above that historical median, she can point to real drift in how long incidents are taking to clear — labelled for exactly what it is, never as a response or reaction time — and direct next week's attention there .

### Story #3 — Which Areas Are Lighting Up?

**Role:** Marcus — EFRS **District Chief**, briefing his duty officers for the coming shift.

Wednesday afternoon, before the duty-officer briefing , Marcus needs to name which neighbourhoods are carrying more fire cases than they should this week so he can point each officer somewhere real . Before the map he guessed from last month's memory — "I think the northeast is busy" — with nothing to point at. Now he opens the early-warning map, which highlights neighbourhoods running above their **own** five-year norm and shades each area by how far above it sits . He briefs by name — "Rundle is above its norm; send your officer there" — so his officers start the shift pointed at the areas actually lighting up, not a stale impression .

---

## 1. Objective

**No-dataset sentence:** *This lets an EFRS operations performance lead see how long events tie up
crews and apparatus, and where and when that workload concentrates, so they can spot where
turnaround and demand are drifting from the historical norm — a comparison they currently cannot
make without manual CAD pulls.*

- **Decision it changes:** where/when attention, staffing, or follow-up review is directed, based on
  which event types, neighbourhoods, and times show abnormal duration or volume against the norm.
- **User who owns it:** an EFRS operations / performance lead who can and will act on the view.
- **Leverage:** the data is already public and daily-updated; the value is turning 946K raw dispatch
  rows into a normed, decidable picture of workload.
- **Center of gravity:** *duration and volume against a baseline* — not a single chart, not raw counts.

## 2. What Good Looks Like (the hardest part — make it testable)

A good output is one the performance lead can read to a decision in under a minute and defend in a
review. Concretely:

- **Every duration figure is labelled "event handling time (dispatch→close)," never "response time."**
- **Non-incident records are excluded** from operational metrics (`TRAINING/MAINTENANCE`,
  `COMMUNITY EVENT`, `PRE-INCIDENT PLANNING`, `PERMIT-BURNING`). State the exclusion on screen.
- **Comparisons are like-for-like in time:** 2026 (partial, Jan–Jun) is only ever compared
  year-to-date against the same window in prior years, and labelled as partial.
- **Duration is summarised by median (with p90), not mean alone**, because the distribution has a
  long right tail (overall median 14 min, mean 23.3, p99 189). The distribution chart's final bar
  is an **explicit `55+` catch-all** — never a bounded "55-60" label that hides the tail.
- **Every metric shows its N**, and any neighbourhood view states its `UNKNOWN` policy. The
  on-screen "valid incidents" total and UNKNOWN % are computed on the **fully-cleaned** row set
  (junk event types dropped), so the footer agrees with every chart under it.
- **When a period has no 5-year baseline** (the earliest years) or no matching rows, the app says
  so plainly — it never asserts a direction ("handling time is down") or reassurance ("nothing
  unusual") against a norm that does not exist.
- **The monthly forecast never plots the partial current month as a full bar** — the current
  month-to-date is shown as a separate, labelled point, excluded from the trend and level.

**Gold example (the centerpiece the build must reproduce):**
> *"Motor Vehicle Incidents — Q2 2026 vs Q2 2021–2025 norm. Median handling time 27 min (p90 58),
> n = 3,140 this quarter vs a 5-year Q2 median of 26 min. Volume +8% above the Q2 norm,
> concentrated 15:00–18:00 in Downtown and Boyle Street. Handling time is stable; volume is up.
> Note: handling time is dispatch→close, not arrival time. UNKNOWN-neighbourhood events (12%)
> excluded from the geographic split."*

**Must-never-produce list:**
1. Any number called or implied to be a "response time," "time to arrival," or NFPA benchmark result.
2. A full-year 2026 total, or any chart that lets 2026 read as a complete year.
3. A duration metric that still includes `TRAINING/MAINTENANCE` or other non-incident records.
4. A `response_code`-based metric that asserts a meaning for any code other than `AL` ≈ ALARMS.
5. A precise-location claim (data is geocoded to the nearest intersection, by design).

## 3. Scope

- **Smallest valuable version (must ship):** filterable views of (a) event **volume** and
  (b) **handling-time distribution** by event type, neighbourhood, hour, and weekday, each shown
  against a multi-year baseline for the same period.
- **One stretch (only if the core is solid):** a thin "what changed" reading layer that flags the
  one or two event-type/area cells most divergent from the norm this period.
- **Out of scope — refused, as specifically as the core:**
  - **Response / arrival / turnout times** — the data has no arrival or call-received timestamp;
    we will not approximate one. (See refusal rationale, §6.)
  - **Station-level performance** — there is no station field; an approximate spatial join is not
    sold as station performance.
  - **Per-incident detail / address-level mapping** — neighbourhood granularity only.
  - **Causal or predictive claims** ("staffing caused X") — this is monitoring, not inference.

## 4. Data

- **Source:** City of Edmonton Open Data — *Fire Response (Current and Historical)*, dataset
  `7hsn-idqi`, updated daily. Connected live via the SODA API; frozen snapshot in `Dataset/`.
  Full pointers in `Knowledge/data-source.md`.
- **One row =** one dispatch event (`event_number`, unique). ~946,250 rows, 2011 → 25 Jun 2026.
- **Representativeness:** all EFRS-attended events, but **57% medical and 15% alarms** — this is a
  medical-and-alarms operation, not primarily a fire dataset. 2026 is partial.
- **What blanks/values mean:** `UNKNOWN` neighbourhood is a literal value (~13%), not missing;
  blank `dispatch_datetime` (186 rows) = no units assigned; `NO UNITS DISPTCHED` is a real
  `equipment_assigned` value. Codebook: **point at `Knowledge/data-dictionary.md`**, don't retype it.
- **The load-bearing data line:** `event_duration_mins` = `event_close_datetime − dispatch_datetime`.
  It is total handling time, **not** response time. Delete this line and the app ships a wrong claim.

## 5. Capabilities (the seam — where the agent decides vs. where behavior is fixed)

- **Fixed (hard-coded, the agent may not vary):**
  - The non-incident exclusion list and the dispatch→close definition of duration.
  - 12-hour timestamp parsing (`%Y/%m/%d %I:%M:%S %p`); drop negative/zero/non-numeric durations.
  - The "never call it response time" labelling rule.
- **Agent's discretion:** which slices/comparisons to surface for a given question, how to phrase
  the "what changed" reading, choice of baseline window when the user doesn't specify one.

## 6. Human-in-the-Loop (governance)

- The **performance lead has the final word** on any action; the app informs, it does not decide.
- **Refusal is a feature:** if asked for a response/arrival time or a benchmark result, the app
  **declines and explains** that the dataset cannot support it, rather than approximating. This
  refusal is logged so we can see how often it's requested.
- **Override logging:** any time a user overrides a default (e.g. includes `UNKNOWN`, changes the
  baseline, re-includes a non-incident type), the app records the override and the reason, so the
  Use-week log can show where the defaults were wrong.

---

## Convergence record (what was chosen, and why)

**Locked criteria (set before choosing):** (1) the data can honestly carry the claim;
(2) a real owner can act on it weekly; (3) it needs the dataset's depth, not a single chart.

| Candidate | Verdict |
| :--- | :--- |
| **Incident duration & workload monitoring** | **Chosen** — passes all three; duration & volume are directly supported. |
| Response-time / NFPA benchmarking | **Rejected** — fails criterion 1: no arrival or call-received timestamp exists, so the core claim cannot be supported. Kept as an explicit refusal in §3/§6. |
| False-alarm reduction | Viable, parked — narrower; `response_code` is undocumented, weakening the alarm-cause angle. |

**The one alternative we rejected and why:** *Response-time benchmarking.* It is the framing the
team first wanted and the one a "duration" column quietly invites — but the dataset measures
dispatch→close, not arrival. Asserting response time would be worth less than nothing: someone
would act on a number that does not mean what it says. We refuse it on purpose.


## Dashboard Mockup
For the dashboard, following these guidelines:
- White color theme
- No Overlapping text 
- Verify numbers & location 
- Interactive (Period and event drop down menu), comparing the currently selected period w median
- KPI's clearly stated with key numbers
- Have summary or generate key insight for every visualization used
- Baseline should be 5 year prior YTD
- Use the static dataset for now

Build a fully functional web application with both the front and the back end

---

## Application build spec (reproduce this exact app)

This section is load-bearing: a fresh session reading this file should rebuild the same
app. It lives in `app/` (Flask backend + single-page frontend). Everything below is
fixed unless the user says otherwise. All §2 honesty rules and the §3/§6 refusals
**must** carry through into every endpoint and every visual.

### Architecture (five layers)
- **Data:** the static snapshot `Dataset/Fire_Response_Current_and_Historical_20260626.csv`
  (~946K rows) builds the cache; the **live SODA API `7hsn-idqi` is an active incremental
  connector** — `/api/refresh` pulls rows newer than the current max dispatch timestamp
  (the city updates daily, so "live" = daily-fresh, never real-time). Neighbourhood boundary
  polygons (2019, dataset `xu6q-xcmj`) are frozen in `app/static/neighbourhoods.geojson`.
- **Capability:** three skills mirrored in code — `incident-data-guard` (hard-gate cleaning),
  `claim-guard` (refuse/flag forbidden claims), `presentation-render` (labelled output) —
  plus a baseline-stats pipeline, a volume-forecast pipeline, and decision-support logic.
- **Service:** Flask (`app/server.py`) exposing `/api/meta`, `/api/metrics`, `/api/forecast`,
  `/api/geo`, `/api/ask`, `/api/refresh`.
- **Presentation:** one white-themed single-page app (`app/static/index.html`), Chart.js +
  Leaflet, **left sidebar nav, four pages — How to use · Overview · Forecast · Ask the data**.
- **Governance:** refusals, refreshes, and overrides logged to `app/logs/`; a governance
  panel on the guide page shows the live counts; the performance lead approves every action;
  deployment via GitHub→Render (see `DEPLOY.md`).

### Backend (`app/server.py`, Flask + pandas + numpy; gunicorn in prod)
- **Cleaning (fixed, from §4/§5):** parse `%Y/%m/%d %I:%M:%S %p`; drop blank dispatch,
  non-numeric/≤0 durations; exclude `TRAINING/MAINTENANCE`, `COMMUNITY EVENT`,
  `PRE-INCIDENT PLANNING`, `PERMIT-BURNING`; treat blank/`UNKNOWN` neighbourhood as the
  literal `UNKNOWN`; drop junk event types (blank/`NULL`/`MESS`/len<4/<500 lifetime rows).
  The junk-type drop is applied **globally** (in `_derive`, so it holds on cache load and
  after a refresh), which is what makes the on-screen totals internally consistent — see
  F2 in the Deployment Assessment. Yields **~890,940 valid incidents (2011–2026)**; the
  default Jan 1 → data-cutoff YTD window shown on screen holds **~427,500** of them
  (UNKNOWN ≈ 11.4%).
- **Like-for-like window (generalised):** the cache keeps **full-year** cleaned rows; every
  request carries a window — `from`/`to` (MM-DD, defaults Jan 1 → data cutoff) and `h1`/`h2`
  (hour band, default 0–23). The baseline is always the **5 prior years over the SAME
  date+hour window**. The latest year is clamped to the data cutoff and labelled partial
  whenever its selected window reaches the cutoff; never shown as a full year.
- **Duration summarised by median + p90 + N** (never mean alone). Every payload carries N.
- **Equipment:** `equipment_assigned` is parsed into unit-TYPE counts (`PUMPER(2)` →
  eq_PUMPER=2; top-8 vocabulary discovered at build). Always labelled "unit types listed on
  dispatch", never apparatus/crew-hours (data-cautions §8).
- **Performance:** on first run, build a cleaned full-year cache (`app/.cache_v5.pkl`,
  ~60 MB, incl. neighbourhood centroids and the equipment vocabulary) so the app runs
  without the 315 MB CSV; later starts load from cache in ~1s. `load_data()` is cache-first
  and idempotent; called at import so `gunicorn server:app` works. `_derive()` recomputes
  all derived state from the row set (also after a live refresh).
- **Endpoints:**
  - `/api/meta` — years, event types, window label, exclusion note, UNKNOWN %, N, data
    cutoff, `data_current_to`, equipment vocabulary, refusal/refresh log counts.
  - `/api/metrics?year&event&unknown&from&to&h1&h2` — KPIs (median +Δ vs 5-yr median, p90,
    N, volume +% vs norm, **committed event-hours** = Σ duration/60 vs norm); **distribution
    and top-neighbourhoods each carry a 5-yr `baseline`** (per-year average over the same
    window, like by-hour/by-weekday) so both charts compare to norm, not just current;
    by-hour, by-weekday, **weekday×hour heat matrix**, by-type, **by-equipment (current vs
    5-yr avg)**, **top movers** (event×nbhd cells ≥25% off their own norm; n≥15, expected≥8/yr;
    **filter-aware — the movers respect the selected event type, scanning all types only for
    "All"**), and text insights. Insights are **descriptive only**.
  - `/api/forecast?event&horizon` — monthly volume forecast (transparent seasonal mean ×
    level factor computed from **completed months only**; ~80% interval = ±1.28σ), level %,
    event-hours projection, and a `data_flag` "verify — may be a reporting change" note when
    |level−1| ≥ 15%. **Volume/workload only — never response time, never causal.** Window
    filters do NOT apply (full monthly history).
  - `/api/geo?year&event&unknown&from&to&h1&h2` — per-neighbourhood centroid, count, median,
    expected (5-yr norm, same window), % divergence, and tier (`above`/`normal`/`below`;
    suppress % when expected < 3). Powers the choropleth/early-warning.
  - `/api/refresh` (POST) — incremental SODA pull (`$where dispatch_datetime > max_iso`),
    same fixed cleaning, appends, re-derives, re-caches, logs to `logs/refresh_log.csv`.
    Returns rows added + new `data_current_to`. Graceful 502 when offline.
  - `/api/ask` (POST) — chatbot. Reads **either `{"q":…}` or `{"question":…}`** so the gate
    can't be bypassed by key choice (F7). The routing order is fixed and lives in code (never
    delegated to the LLM): **(1) `claim-guard` refusal gate** — refuse + log (to
    `logs/refusal_log.csv`) any response/arrival-time, turnout/NFPA, or **station-performance**
    ask — the station matcher catches "which station is slowest", "compare stations", etc.,
    while exempting unrelated place types like "gas station" (F5). **(2) On-topic gate** — a
    question carrying no concrete data signal (no matched event type, no neighbourhood, no
    forecast/resourcing/editorial intent, and none of the `ON_TOPIC` keywords) is redirected
    with a "here's what I can answer" message instead of falling through to a stray KPI
    ("what is the meaning of life" no longer returns a year-to-date figure). **(3) Editorial
    branch** — open-ended asks ("what's most notable?", "summarise this", "what stands out?",
    "biggest change") route to a deterministic `_digest`, which reuses `build_flags` +
    `build_movers` (the same triage the Overview page shows) to assemble a ranked facts brief;
    the LLM then writes a short reading of it. Per the chosen design this **requires** the LLM
    layer — with it off (or on any failure) the app says so and steers to the exact queries
    that work offline, rather than hand-rolling a summary. **(4) Query-planner** — for a
    computable-but-unmatched ask (a specific slice/metric the fixed branches don't cover, e.g.
    "median handling time for medical on weekends downtown", "how many MVIs between 3–6pm",
    "compare fire volume in Downtown vs Boyle Street"), `plan_query` has Gemini fill a
    **whitelisted query schema** (event / nbhd / weekday / hour-band / year / metric ∈
    median·p90·count·eventhours·volume / groupby / compare) and `run_query` **executes it in
    code** against the cleaned rows — every figure still computed by code, always labelled
    handling time with N and the 5-yr baseline. The whitelist cannot express response/arrival
    time, station performance, causation, per-incident/address detail, or forecasts, so those
    stay refused/redirected. Runs only for non-resourcing, non-forecast asks (so planning →
    decision, forecast → forecast); needs the LLM (offline it falls through). **(5)
    Decision-support** (resourcing/where/when — planning intent; "how many" is NOT a planning
    trigger and routes to the planner): return volume vs norm, peak hour, busiest weekday, an
    estimated peak simultaneous-incident load (= per-day events in the busy hour × median
    handling-time hours), and the 6-month outlook — always closing that the dataset shows
    demand/workload, **not** an apparatus count, so the staffing call is the lead's. It must
    never echo only a basic KPI for a decision question. **(6) Forecast** (`wants_fc`) — the
    horizon is parsed from the question ("next month"→1, "6 months"/"six months"→6,
    "quarter"→3, "next year"→12; clamped 1–12 with an explicit "you asked for N, this covers
    M" note when out of range; default 6). **(7)** else a basic metric KPI.
    - **Optional Gemini phrasing layer (via Vertex AI):** when a Google Cloud project is
      configured via env (`GEMINI_PROJECT` or `GOOGLE_CLOUD_PROJECT`, plus optional
      `GEMINI_LOCATION`), the already-computed, already-correct answer is passed to Gemini
      (`gemini-2.5-flash-lite` by default, override `EFRS_GEMINI_MODEL`; via the `google-genai`
      SDK, `vertexai=True`, auth = Application Default Credentials — **not** an AI Studio API
      key) purely to rephrase it. The same layer, in an `editorial=True` mode, writes the
      Ask-the-data editorial readings from the `_digest` brief. **Every number still comes from
      the deterministic backend** — Gemini is told to preserve figures verbatim, never introduce
      response/arrival-time language, make no causal claim, and keep the "the staffing call is
      yours" note; it never sees the raw data. The refusal and on-topic gates run in code
      **before** any Gemini call. With no project/credentials (or on any API error/timeout) the
      deterministic metric/decision/forecast answers still run offline; only the editorial mode
      requires the layer. `/api/meta.chat_llm` / `chat_model` report whether it is live. This is
      the deliberate answer to F5's "make the chatbot real": language from the model, truth and
      governance from code.
    - **Deterministic-brief phrasing rule (guards against number mis-attribution):** the briefs
      handed to Gemini phrase the year as a period ("…in 2026 (…)") and label the count as
      "n = … incidents", and both system prompts state explicitly that a four-digit value after
      "in" is the YEAR, never a count — because a cheap phrasing model was otherwise misreading
      the year `2026` as a phantom "2026 incidents". Truth lives in the source text, not in the
      model's discretion.
    - **Scope-consistency guard (`scope` arg on the phrasing call):** metric/decision/forecast
      answers pass Gemini a plain-English `scope` of exactly what was computed (e.g. "a
      6-month volume forecast for Motor Vehicle Incident"). Gemini cross-checks it against the
      question and, **only on a clear mismatch the parser missed** (wrong horizon/event/area/
      year), says the tool computed something else and asks the user to rephrase — never
      inventing the corrected number. The conservative wording ("only for a clear, material
      mismatch") keeps it from false-flagging valid answers.

### Frontend (`app/static/index.html`, single file, white theme)
- **Layout: left sidebar** (brand + vertical nav, sticky; collapses to a top row on mobile)
  with four pages: **① How to use · ② Overview · ③ Forecast · ④ Ask the data**. The guide
  page is the landing page: purpose, the dispatch→close rule, how to use each page, filter
  explanations, data source, limitations list, and a **governance panel** (valid-N/raw-N,
  refusals logged, UNKNOWN %, refreshes run — live from `/api/meta`).
- Global controls (**sticky top bar**, pinned as you scroll so filters are always reachable):
  **Period** (year), **From/To date** pickers (latest year capped at the data cutoff), an
  **hour-band dual-thumb slider** (00:00–23:00, snaps to whole hours, live "HH:00 – HH:00"
  label, handles can't cross; drives the same `h1`/`h2` params), **Event type**, **UNKNOWN**
  toggle, plus a **"Data current to <date>" clock chip and a ⟳ Refresh-data button** (POST
  `/api/refresh`, then re-fetch meta + reload; shows "+N new"/"Up to date"/offline states).
  On-screen chips state the window (+day count), baseline ("same window"), UNKNOWN policy
  + %, and a partial-year warning only when the window reaches the cutoff; the **exclusion
  note lives in the page footer** (not a top chip — it's constant, so it belongs at the bottom).
- **Overview page:** **five KPI cards** (median, p90, volume N, **committed event-hours**,
  baseline N) — the old one-line headline summary box above them was **removed as redundant**
  with the cards, so the page leads with the KPIs. Then charts — handling-time distribution
  (**with a 5-yr baseline line**), volume by hour, volume by weekday, top neighbourhoods
  (**current vs 5-yr baseline, grouped bars**), **weekday×hour heatmap grid** (CSS grid,
  darker=more, hover for counts), **units dispatched by type** (current vs 5-yr avg; labelled
  unit TYPES, not crew-hours), **"Biggest shifts vs norm" table** (the §3 stretch: top
  event×nbhd movers with thresholds stated; **filter-aware — shows the selected event's
  neighbourhood shifts, or the cross-event scan for "All"**), median-by-type (only for "All")
  — each with a short factual **insight** caption. **No recommendation blocks here.**
  At the bottom, a **full-width choropleth map** (Leaflet + `neighbourhoods.geojson`):
  hotspots-only default (fill = % above own norm, others faint) vs all-neighbourhoods
  (fill = volume, sqrt scale), popups with count/median/vs-norm, dynamic gradient legend,
  auto-zoom, watch-list insight, note when a hotspot lacks a 2019 polygon.
- **Forecast page:** KPI cards (projected next-6-month volume + ~80% range; level; projected
  event-hours; signed % vs norm with the data-check), the actual+forecast line chart with a
  shaded interval band, and a factual insight. Notes that date/hour filters don't apply.
- **Ask the data page:** chat UI with example questions; this is the only place prescriptive
  decision-support text appears, and the only place editorial ("what's most notable?") readings
  are generated. Refused answers render in an amber bubble; off-topic and "editorial needs the
  LLM layer" replies render in the normal bubble.
- Libraries via CDN only: Chart.js 4, Leaflet 1.9 (+ CARTO light basemap). Keep the white
  theme, no overlapping text, every figure shows its N.

### Must-never (carry §2 through the whole app)
No "response time"/arrival/turnout/NFPA metric anywhere; no full-year 2026; no meaning for
`response_code` other than `AL`≈ALARMS; no station-level performance; no address-level
precision (neighbourhood granularity only); no causal/predictive claims (forecasts are
volume extrapolation with intervals, labelled as such).

### Gaps left open on purpose (as of the 2026-07-03 deployment review)
These were found by the critics, judged real, and **deferred** — the app is honest about each,
and none blocks the weekly attention decision (story #1). See the Deployment Assessment for full reasons.
- **Prescriptive text in `/api/metrics` & `/api/forecast` payloads (F6).** The endpoints still
  carry unused `rec_*` recommendation strings and a dead `setMeans()` renderer. Nothing renders
  them, so no screen shows prescriptive text outside the chatbot — but the endpoint contract is
  looser than the spec. Clean-up deferred; low risk because it is invisible to the user.
- **Hotspot count drift (F8): 109 vs 111.** The metrics "flag" count and the geo "note" count use
  slightly different rounding at the 25% boundary, so they can differ by one or two. Both are
  directionally right and spot-checked exact; a single shared definition is deferred.
- **UNKNOWN plotted as a placed point (F9).** With UNKNOWN included, the map gives the `Unknown`
  bucket a central-Edmonton centroid. The % may be a real signal, but showing it as a located
  "area" can mislead. Default excludes UNKNOWN and states the policy; the include-mode fix is deferred.
- **Odd query params (F10):** `horizon=0`, `year=2010`, etc. degrade to reasonable data but with
  imperfect labels. Self-labelled and survivable; deferred.
- **The 5-minute pitch deck** still over-weights the build/governance vs. user benefit, and reads
  as text-heavy/AI-generated (human critic). The app-side answer — user stories at the top of this
  file, benefit-first — is done; the deck rewrite itself is a separate deliverable, deferred.

### Verify before shipping (the build's real test)
Reproduce the oracle: **Motor Vehicle Incident, 2026, window Jan 1 – Jun 25 vs 2021–2025**
→ median 26 min, p90 69, n = 2,919, volume +35% vs the 5-yr norm. (After a live refresh the
default window extends past Jun 25, so pass `from=01-01&to=06-25` explicitly — the numbers
must still match exactly.) Confirm the chatbot **refuses** "average response time" **and**
"which station is the slowest?" (both logged), does **not** refuse "gas station", refuses the
same asks under the `{"question":…}` key, and gives a real decision-support answer to "how
should I plan crews for downtown fire?". Confirm the **on-topic gate redirects** an off-topic
ask ("what is the meaning of life") instead of returning a KPI; that an **editorial** ask
("what's most notable this year?") returns a reading whose every figure traces to
`/api/metrics` (e.g. volume % and top movers); and that no phrased answer turns the **year**
into a count ("2026 incidents" — the count is `n = … incidents`, never the year). Confirm the
**query-planner** answers a computable-but-unmatched ask ("median handling time for medical on
weekends downtown", "how many MVIs between 3–6pm", "compare fire volume Downtown vs Boyle
Street") with figures that trace to a code-run slice, while still **refusing** the same
whitelist's forbidden asks; that the **forecast horizon tracks the question** ("next month"→1,
"4 months"→4, "next year"→12, "18 months"→clamped to 12 with a note); that the **movers table
is filter-aware** (a specific event shows that event's neighbourhood shifts); and that the
**distribution and top-neighbourhood charts each show a 5-yr baseline**. Confirm the
distribution's last bin is labelled
**`55+`** (not `55-60`); that `/api/meta` `n_total` ≈ **427,500** with UNKNOWN ≈ **11.4%**;
that a **no-baseline** slice (Vehicle Fire 2011) says handling time can't be compared rather
than "down"; and that the forecast's last **actual** point is a complete month with the partial
current month returned separately (`forecast.partial`). Confirm `/api/refresh` is idempotent
(second call adds 0). Spot-check one geo number against a raw-CSV count (Downtown MVI 2026 = 54).

### File inventory (what the build produces)
- `app/server.py` — Flask backend (cleaning, metrics incl. equipment/heat/movers/event-hours,
  forecast, geo, live refresh, chatbot).
- `app/static/index.html` — single-file white-themed SPA (sidebar, 4 pages, Chart.js + Leaflet).
- `app/static/neighbourhoods.geojson` — 2019 neighbourhood boundary polygons (0.5 MB,
  name-keyed uppercase, coords rounded to 5 dp; from dataset `xu6q-xcmj`).
- `app/requirements.txt` — flask, pandas, numpy, gunicorn, google-genai (optional Gemini
  phrasing layer via Vertex AI; live refresh uses stdlib urllib).
- `app/.cache_v5.pkl` — full-year cleaned cache incl. centroids + equipment vocabulary
  (~60 MB; the app runs from this alone, no 315 MB CSV needed; rewritten on refresh).
- `app/Procfile`, `app/runtime.txt`, `render.yaml`, `.gitignore`, `DEPLOY.md` — deployment.
- `.agents/launch.json` — preview/dev-server launch config (`python app/server.py`, port 5000).
- `.agents/skills/{incident-data-guard,claim-guard,presentation-render}/` — the three skills
  the backend mirrors in code (hard-gate cleaning, claim refusal, labelled render).

### Regenerate from a fresh session (procedure)
1. Read this file and `Knowledge/data-cautions.md` (load-bearing).
2. Verify the dataset window + metrics against the CSV before coding (oracle numbers above).
3. Build `app/server.py` to the Backend spec; run it once to build `app/.cache_v5.pkl`
   (parses the 946K-row CSV in ~11 s, then loads from cache in ~1 s; cache-first and
   idempotent so `gunicorn server:app` works without the CSV).
4. Build `app/static/index.html` to the Frontend spec (sidebar + 4 pages; guide page first;
   choropleth map in Overview; descriptive-only Overview/Forecast; decision-support only in
   the chatbot). Fetch `neighbourhoods.geojson` from dataset `xu6q-xcmj` if missing.
5. **Test by behaviour, not code:** reproduce the oracle (explicit window post-refresh),
   confirm the chatbot refusal + decision answer, test a date+hour window against the same
   window's baseline, confirm refresh idempotency, spot-check one geo number.
6. Carry every §2 honesty rule and §3/§6 refusal through every endpoint and visual.

> Note: this build spec is the single source of truth for regeneration. If asked instead for
> a portable **skill**, package these same rules as a `cowork`/an agentic coding CLI skill — but for this
> project the spec lives here so the agent loads it automatically each session.

