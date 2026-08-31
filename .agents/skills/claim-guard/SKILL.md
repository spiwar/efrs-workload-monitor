---
name: claim-guard
description: >
  Advisory guardrail for the EFRS Incident Duration & Workload Monitor. Use whenever
  the app is about to SHOW or WRITE a number, label, headline, KPI caption, tooltip,
  or insight to the user. Reads the draft text and flags the project's forbidden
  claims: calling handling time a "response time" / "time to arrival" / NFPA
  benchmark, presenting 2026 as a full year, asserting a meaning for any response_code
  other than AL, station-level performance, address-level precision, or causal /
  predictive language. Also detects when a user request is for something the dataset
  cannot support (a response/arrival time) so the app can refuse and LOG the refusal.
  It advises; the writer rewrites.
---

# claim-guard (ADVISORY)

This skill is **advisory** (like Kinquiry's `interpretation-guardrails`): it does not
block the run, it flags problems in draft user-facing text and lets a human decide.
Its job is to stop the one claim the spec forbids from ever shipping.

## When to use
- Before rendering any KPI, chart caption, headline, tooltip, or generated insight.
- When a user asks a question, to detect an **unsupported ask** (response/arrival
  time, station performance) that the app must refuse and log.

## What it flags (AGENTS.md sec.2 "must-never-produce" + sec.3/sec.6)
1. **Response-time framing** — "response time," "time to arrival," "turnout/travel
   time," "NFPA," "how fast crews arrived." The data has no arrival/call-received
   timestamp. Correct label: **"event handling time (dispatch->close)."**
2. **Full-year 2026** — 2026 is partial (Jan-25 Jun). Flags any 2026 total not
   labelled partial / not compared year-to-date against the same window.
3. **response_code meanings** — flags asserting any meaning for a code other than
   `AL ~ ALARMS`.
4. **Station-level performance** — no station field exists; a spatial join is not
   station performance.
5. **Address-level precision** — data is geocoded to nearest intersection.
6. **Causal / predictive language** — "caused," "because of," "will," "predict,"
   "forecast." This is monitoring, not inference.

## How to run
```
python check_claim.py "<draft text>"          # lint a string
python check_claim.py --file draft.txt          # lint a file
echo "<text>" | python check_claim.py -          # lint stdin
```
Output: each flagged span with the rule it violates and a suggested fix.
Exit `0` = no flags. Exit `2` = at least one flag (advisory — the writer rewrites,
the human may still proceed).

## Refusal logging (sec.6: refusal is a feature)
When the input is a user request for an unsupported metric, the skill emits a
`REFUSAL` line. Append it to `refusal_log.csv` (timestamp, request, reason) so the
Use-week review can see how often response-time/station asks were made. Likewise,
any user override of a default (including UNKNOWN, changing the baseline) should be
written to `override_log.csv` with the stated reason.

## What "good" looks like (behavior check)
- "Average response time was 8 minutes" -> FLAG rule-1, suggest "event handling time."
- "Total incidents in 2026: 41,000" -> FLAG rule-2 (partial year).
- "Median handling time 27 min (p90 58), n=3,140; UNKNOWN excluded" -> PASS.
