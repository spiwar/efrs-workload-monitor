---
name: incident-data-guard
description: >
  Hard gate for the EFRS Incident Duration & Workload Monitor. Use BEFORE computing
  ANY duration or volume metric from the Fire Response dataset (7hsn-idqi / the
  Dataset/ snapshot). Normalizes and filters the dispatch rows to valid incident
  records, enforcing the project's fixed rules: parse 12-hour timestamps, exclude
  non-incident administrative records (TRAINING/MAINTENANCE, COMMUNITY EVENT,
  PRE-INCIDENT PLANNING, PERMIT-BURNING), and drop non-numeric / zero / negative
  durations. Trigger whenever the agent is about to count events, compute handling
  time, or build a baseline comparison. The rule lives here, not in the builder's head.
---

# incident-data-guard (HARD GATE)

This skill is a **hard gate**: it stops the run if the data going into a metric has
not been cleaned to the project's fixed standard. It mirrors Kinquiry's
`codebook-guard` — a rule enforced in code, not hoped for.

## When to use
Run `validate.py` on any dataframe/CSV slice **before** it feeds a count, a median,
a p90, or a baseline comparison. If it exits non-zero, fix the input — do not compute.

## The fixed rules it enforces (from AGENTS.md §5 and Knowledge/data-cautions.md)

1. **Duration is handling time, never response time.** `event_duration_mins =
   event_close_datetime − dispatch_datetime`. There is no arrival or call-received
   timestamp. This skill never relabels the column; the claim-side rule is enforced
   by the separate `claim-guard` skill.

2. **Exclude non-incident records** by `event_description`, before any metric:
   `TRAINING/MAINTENANCE`, `COMMUNITY EVENT`, `PRE-INCIDENT PLANNING`,
   `PERMIT-BURNING OR OTHER` (and any value starting `PERMIT-BURNING`).
   Leaving these in roughly doubles average duration (TRAINING/MAINTENANCE alone has
   a median "duration" of 138 min).

3. **Clean the duration column:** drop rows where `event_duration_mins` is
   non-numeric, `<= 0` (zeros and negatives, down to -163 min - clock artifacts).

4. **Timestamp parsing is fixed:** `%Y/%m/%d %I:%M:%S %p` (12-hour, AM/PM).
   Blank `dispatch_datetime` (~186 rows = no units assigned) is dropped from
   duration metrics.

5. **`UNKNOWN` neighbourhood (~13%, ~122k rows) is a literal value, not missing.**
   The skill does NOT drop it silently; it reports the count so the caller can state
   its policy on screen. Overriding the default (including UNKNOWN in a geo split)
   must be logged with a reason.

6. **`response_code` is opaque** except `AL ~ ALARMS`. The skill refuses to build a
   metric keyed on any other code.

## How to run
```
python validate.py <path-to-csv>                    # validates the snapshot / a slice
python validate.py <path-to-csv> --clean out.csv    # also writes the cleaned rows
```
Exit code `0` = clean and safe to compute. Exit code `1` = a rule was violated; the
message names which rule and the offending rows. **A non-zero exit means do not
compute the metric.**

## What "good" looks like (behavior check)
- A row with `event_description = TRAINING/MAINTENANCE` is **excluded**, not counted.
- A row with `event_duration_mins = -163` or `0` is **dropped**.
- A row with a malformed timestamp is **dropped**, and the count reported.
- The script **prints the N** kept and the N removed per rule, and the UNKNOWN count.
