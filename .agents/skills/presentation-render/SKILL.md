---
name: presentation-render
description: >
  Deterministic render skill for the EFRS Incident Duration & Workload Monitor. Use
  whenever the app needs to write a KPI caption, chart summary, headline, or the
  one-paragraph brief for a slice. Given already-computed metrics (median, p90, N,
  baseline), it stages the written claim in a FIXED order and guarantees the required
  labels every time: "event handling time (dispatch->close)" (never response time),
  the N for every figure, a 5-year-prior-YTD baseline comparison, a partial-2026
  label when 2026 is in the period, and a stated UNKNOWN-neighbourhood policy.
  Same input -> same output. It writes; it makes no analytical judgment (the
  interpreter subagent supplies the reading; this skill formats it).
---

# presentation-render (DETERMINISTIC)

A repeatable procedure with **no judgment in it** (slide 13/19): same input produces
the same output every run. It does not decide what the numbers mean — the interpreter
subagent does that and hands the reading in. This skill guarantees the *form* of every
user-facing claim so the spec's labelling rules can never be forgotten in a caption.

## When to use
Before showing any KPI, chart caption, or generated brief. Feed it the computed
metrics (from the analysis fixed-pipeline, after `incident-data-guard`); it returns the
standardized block. Then lint that block with `claim-guard` before it ships.

## Fixed output order (AGENTS.md sec.2 gold example)
1. **Headline** — `{event_type} — {period} vs {baseline_period} norm.`
2. **Handling time** — `Median handling time (dispatch->close) {median} min (p90 {p90}), n = {n}`
3. **Baseline** — `vs a {baseline_years}-year {period_kind} median of {baseline_median} min`
4. **Volume** — `Volume {±pct}% vs the {period_kind} norm` (omitted if not supplied)
5. **Concentration** — `concentrated {hours} in {areas}` (omitted if not supplied)
6. **Reading** — the one-line stable/up reading from the interpreter (passed in)
7. **Notes** — fixed: handling time is dispatch->close, not arrival; UNKNOWN policy + %.

## Guarantees enforced in code (`render.py`)
- The phrase **"event handling time (dispatch->close)"** always appears; the words
  "response time" never do.
- **Every duration figure carries its N.**
- If the period contains **2026**, the block is labelled **partial (Jan-Jun YTD)**.
- The **UNKNOWN policy line is mandatory** (excluded / included + %).
- Baseline defaults to **5-year prior YTD** when not specified (spec default).

## How to run
```
python render.py --event "Motor Vehicle Incidents" --period "Q2 2026" \
  --baseline "Q2 2021-2025" --median 27 --p90 58 --n 3140 \
  --baseline-median 26 --volume-pct +8 \
  --concentration "15:00-18:00 in Downtown and Boyle Street" \
  --reading "Handling time is stable; volume is up." --unknown-pct 12 --unknown excluded
```
Prints the standardized brief block. Exit 0 on success; exit 1 if a required label
could not be produced (a guarantee failed).

## What "good" looks like (behavior check)
Feeding the gold-example numbers reproduces the spec's centerpiece paragraph, and the
output passes `claim-guard` with zero flags.
