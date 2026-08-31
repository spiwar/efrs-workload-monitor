# Deployment Assessment — EFRS Incident Duration & Workload Monitor

**the project team · 2026-07-03**
One pass through the loop: triage the evidence → classify and fix → re-run the critic → write it down.
The bar for every decision was **Story #1 — Dana, the Operations/Performance Lead asking "are fire cases running hot?"** — she needs a number she can defend in the Monday ops review.

---

## 1. What the critics found, and what we decided

We had three streams of evidence: a machine critic (10 findings, fresh context, never saw our source code), the human pitch feedback (3 notes), and the use-week logs. Every item got a verdict and a reason. We fixed the ones that touch a number Dana would quote out loud, and deferred the ones that never reach a screen.

### Consolidated triage table

| # | Source | Sev | Finding (plain language) | Verdict | Reason | Home |
|---|--------|-----|--------------------------|---------|--------|------|
| **F1** | Machine | Blocker | The handling-time chart's last bar says "55-60 min" but actually holds **everything ≥ 55 min** — most of it runs well past an hour. Hides the long tail. | **Accept — fixed** | Dana could quote "most cases close in under an hour" and be wrong. Directly a defensibility failure. | Deliverables (chart) |
| **F2** | Machine | Major | The footer's "450,433 valid incidents / 15.1% UNKNOWN" **includes 22,933 junk rows** the cleaning rule says to drop — so the total disagrees with every chart under it. | **Accept — fixed** | Story #1 is "a traceable number she can defend." A headline count that doesn't reconcile with the charts fails that on sight. | Skills / Spec |
| **F3** | Machine | Major | The forecast plots the **partial current month (Jun 1-25) as a full month**, so June looks like a demand collapse. | **Accept — fixed** | Same trap as a full-year-2026 read, one tab over. A lead's eye reads the dip even though the math ignores it. | Deliverables (chart) |
| **F4** | Machine | Major | For the earliest years or a no-match filter, the app asserts **"Handling time is down"** and **"nothing unusual — tracks the 5-year norm"** against a baseline that **doesn't exist**. | **Accept — fixed** (this is the "partial agreement" in our notes — 2011 shows no baseline, but the app still claimed a direction) | A reassurance with no norm behind it is worse than silence. Story #1 lives on the comparison being real. | Governance / Spec |
| **F5** | Machine | Major | "Which station is the slowest?" is **not refused** — it answers with a citywide KPI. The refusal was designed but never fired for that phrasing. | **Accept — fixed** | Refusal is a feature (§6). A missed refusal also undercounts the "how often is this asked" telemetry. | Skills / Governance |
| **F7** | Machine | Minor | The documented `{"question":…}` request shape **bypasses the refusal gate** — every ask under that key gets a generic fallback, unlogged. | **Accept — fixed** (folded into the F5 work — same gate, one line) | It's a governance hole, not cosmetics: a non-frontend client gets zero guardrails. The fix was free, so we took it. | Governance |
| **F6** | Machine | Minor | `/api/metrics` and `/api/forecast` payloads carry prescriptive "recommendation" text the spec bans there; a dead renderer ships in the page. | **Defer** | Nothing renders it — no screen shows prescriptive text outside the chatbot. Contract is loose, but the user never sees it. Parked. | Spec (cleanup) |
| **F8** | Machine | Minor | The same slice reports **109 vs 111** hotspots (metrics flag vs geo note) from different rounding at the 25% edge. | **Defer** | Both are directionally right and the underlying points spot-check exact. A one-neighbourhood drift doesn't change where Marcus sends an officer. | Spec (cleanup) |
| **F9** | Machine | Minor | Including UNKNOWN puts a placed "Unknown" point at a central-Edmonton centroid, topping the watch-list. | **Defer** | Default **excludes** UNKNOWN and states the policy, so the misleading view only appears if the lead opts in. Fix later. | Deliverables |
| **F10** | Machine | Minor | Odd params (`horizon=0`, `year=2010`) degrade to reasonable data with imperfect labels. | **Defer** | Self-labelled and survivable; nobody drives these in a real review. | Spec (cleanup) |
| **P1** | Pitch | — | Too much build/governance, not enough user benefit; open with who the user is and what decision gets easier. | **Accept** | The single most consistent note. App-side answer: three user stories now sit **at the top of AGENTS.md**, benefit-first. | Deliverables (deck) |
| **P2** | Pitch | — | Content felt AI-heavy, text-heavy, repetitive. | **Accept — deferred (deck)** | Real, but it's a deck rewrite, not an app change. Parked past today with the reason recorded. | Deliverables (deck) |
| **P3** | Pitch | — | Add guardrails/input validation to the chatbot; offer a live daily feed, not a frozen snapshot. | **Partly already built; rest fixed** | The live feed already exists (`/api/refresh`, daily SODA pull). The guardrail gap **is** F5/F7 — now fixed. | Governance |
| **U1** | Use-week | — | The refusal log shows **~20 refusals, almost all "average response time"** variants. | **Accept — informs design** | The single most-requested thing is the one thing we correctly refuse. Validates the refusal design and the "we don't do response time" framing on the guide page. | Governance |

**Rejected:** none outright. The machine critic's 14 passed checks (oracle recompute, geo spot-checks, no response-time framing, exclusion applied, N shown everywhere, refusal + decision-support working) we accept as-is — they're the spine, and they held.

---

## 2. The evidence — before-and-after critic readings

Same app, same static snapshot, re-run against the same brief after the fixes. Numbers are from the live API (`/api/metrics`, `/api/forecast`, `/api/meta`, `/api/ask`).

| Check (Story #1's lens) | Before (baseline critic run) | After (this afternoon) |
|---|---|---|
| **Oracle** — MVI 2026 YTD vs 2021-25 | median 26 / p90 69 / n 2,919 / vol +35% | **Unchanged: 26 / 69 / 2,919 / +35%** — fixes didn't move the real numbers |
| **F1** distribution last bar (ALL 2026) | `55-60 : 1403` (really ≥55) | `55+ : 1403` — labelled as the catch-all it is |
| **F2** footer total / UNKNOWN | `n_total = 450,433` · `15.1%` (junk kept) | `n_total = 427,500` · `11.4%` — matches the spec rule and every chart |
| **F3** forecast tail (ALL) | last *actual* = "Jun 26" = 4,320 (partial, unmarked) | last *actual* = "May 26"; **partial "Jun 26 = 4,316" returned separately**, drawn as a hollow point |
| **F4** no-baseline (Vehicle Fire 2011) | "…n = 194 (no baseline). **Handling time is down.**" + "Nothing unusual — tracks the 5-year norm." | "…(no comparable 5-year baseline). **Handling time can't be compared — this period has no 5-year baseline.**" + flag: "No 5-year baseline exists for this period…" |
| **F4** zero-match (Unicorn Attack 2026) | same false "nothing unusual" reassurance | "No incidents match this selection — nothing to compare to a norm." |
| **F5** "Which station is the slowest?" | `refused = None`, answered with citywide KPI | **`refused = True`, logged** (and "gas station downtown" is *not* refused) |
| **F7** forbidden ask via `{"question":…}` | generic fallback, unlogged | **`refused = True`, logged** — gate closed on both keys |
| **Geo spot-check** (Downtown MVI 2026) | count 54 / median 19.5 / expected 47 | **Unchanged: 54 / 19.5 / 47** — data integrity preserved |

**Pitch feedback that mattered:** P1 (lead with the user) drove the story-first ordering of the spec. P3 (chatbot guardrails + live feed) turned out to be half-done already (the live refresh) and half-covered by the F5/F7 fix.

**Use-week episode that taught us something:** the refusal log (`logs/refusal_log.csv`) is almost entirely "what was the average response time?" — over a dozen times across the week. The thing users most want is the one thing the data honestly cannot give, and the app is right to refuse it every time. That's not a bug in demand; it's the reason the refusal is a headline feature, and it's why the guide page states the dispatch→close limitation up front.

---

## 3. What we changed

Fixes F1–F5 + F7 all landed in `app/server.py` (and the forecast render in `app/static/index2.html`). The cleaning fix (F2) went into `_derive()` so it takes effect on cache-load and after every live refresh, without rebuilding the 315 MB CSV. The **F5** fix hardened the chatbot's refusal gate so station-performance asks are declined and logged like the response-time asks already were, and closed the `{"question"}` key that had bypassed it (**F7**).

---

## 4. The revised spec

`AGENTS.md` is updated so the next reader sees the app as it now is:
- The **three user stories are at the top** (§0), Story #1 first — benefit before build (answers pitch note P1).
- §2 "What Good Looks Like" now names the `55+` catch-all, the junk-excluded totals, the no-baseline honesty rule, and the partial-month forecast rule.
- The build spec's cleaning, metrics, forecast, and chatbot sections describe the fixed behaviour.
- A new **"Gaps left open on purpose"** section lists F6, F8, F9, F10, and the deck rewrite, each with its reason.
- The "Verify before shipping" checklist now includes the station refusal, the `{"question"}` key, the `55+` label, the 427,500 total, the no-baseline reading, and the partial-forecast split — so a fresh session can confirm all of it by behaviour.

---

## 5. A record of judgment (one paragraph)

We treated each finding as a claim, not a verdict, and let Story #1 settle every call: if Dana would say the number out loud in a review, we fixed it; if the user never sees it, we parked it and said so. That put the Blocker (F1) and the three Majors (F2–F4) on the fix list because each is exactly the kind of figure that gets repeated in a room and then falls over — a bar that hides the tail, a total that won't reconcile, a month that reads as a collapse, a reassurance with no baseline behind it. F5 we fixed so the refusal that is meant to be a feature actually fires for station-performance asks, not just response-time ones — a guardrail that only counts if it triggers on the questions people really type. The five minor findings we deferred on purpose, because loosening an unseen contract or a one-neighbourhood rounding gap doesn't change where a chief sends an officer on Wednesday. The clearest lesson came free from the use-week log: the thing people ask for most is the thing this data honestly can't give, and the app's job is to keep refusing it — clearly, and on the record. What's left open is small, visible, and named; what's fixed is the part a lead has to defend.
