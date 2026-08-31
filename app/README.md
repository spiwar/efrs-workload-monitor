# EFRS Incident Duration & Workload Monitor — Web App

A full-stack dashboard built from `AGENTS.md`. **Backend** (Flask + pandas) loads the
City of Edmonton Fire Response snapshot, applies the spec's fixed cleaning rules, and
serves metrics. **Frontend** (single-page, Chart.js) is an interactive white-themed
dashboard.

## What it does
- **Two views:** event **volume** and **handling-time distribution**, sliceable by
  **event type, neighbourhood, hour, and weekday**.
- **Like-for-like baseline:** every year is truncated to the same year-to-date window
  (Jan 1 → the snapshot's last date, **Jun 25**), and compared to the **5 prior years**
  over that same window. 2026 is always labelled **partial**.
- **KPIs:** median handling time (+Δ vs 5-yr median), p90, event volume N (+% vs norm),
  pooled baseline N.
- **An insight under every visualization**, plus a **"what changed"** reading.
- **Honest by design:** duration is always "event handling time (dispatch→close)" —
  never response time; non-incident records are excluded (stated on screen); the
  UNKNOWN-neighbourhood policy is shown and toggleable.

## Run it
```bash
cd app
pip install -r requirements.txt
python server.py
# open http://127.0.0.1:5000
```
The data file is read from `../Dataset/Fire_Response_Current_and_Historical_20260626.csv`
(override with the `EFRS_CSV` env var). Port override: `PORT`.

On first start it parses the 946,250-row snapshot (~12 s) and writes a cleaned-data
cache (`.cache_v5.pkl`); later starts load from cache in under a second. Delete the
cache to force a rebuild after the dataset is updated.

## Predictive & prescriptive layer (honest by design)
The app stays inside the spec's boundary: it forecasts **volume / workload only**
(counts over time), never response time, and makes **no causal claims**. Every
forecast carries a prediction interval; every recommendation is decision-support the
performance lead approves.

- **Forecast tab** — monthly volume with a ~80% prediction interval, a level-vs-norm
  factor, and a projected crew-hours workload (forecast volume × historical median
  handling time). Large level shifts trigger a "verify — may be a reporting change"
  data-check note.
- **Early-warning panel** — event-type × neighbourhood cells running ≥25% above the
  5-year YTD norm, ranked. Flags where to look; the lead decides any action.
- **Chatbot ("Ask the data")** — plain-language questions routed to the metric or
  forecast. Unsupported asks (response/arrival time, station performance) are
  **refused and logged** to `logs/refusal_log.csv` — refusal is a feature (spec §6).

## API
- `GET /api/meta` — years, event types, YTD window label, exclusion note, UNKNOWN %, N.
- `GET /api/metrics?year=<Y>&event=<TYPE|ALL>&unknown=<exclude|include>` — KPIs, the
  5-yr-prior-YTD baseline, distribution + hour/weekday/neighbourhood/event-type
  breakdowns, generated insights.
- `GET /api/forecast?event=<TYPE|ALL>&horizon=<1-12>` — monthly volume forecast with
  prediction intervals, level factor, and workload-hours projection.
- `GET /api/alerts?year=<Y>&unknown=<...>` — early-warning cells above the norm.
- `POST /api/ask {"q": "..."}` — chatbot; refuses + logs unsupported asks.

## How the spec's rules are enforced (backend)
- Exclude `TRAINING/MAINTENANCE`, `COMMUNITY EVENT`, `PRE-INCIDENT PLANNING`,
  `PERMIT-BURNING` before any metric.
- Parse the fixed 12-hour timestamp `%Y/%m/%d %I:%M:%S %p`; drop blank dispatch times.
- Drop non-numeric / zero / negative durations.
- Summarise duration by **median + p90** (never mean alone); every metric carries its N.
- `UNKNOWN` (and blank) neighbourhood treated as a literal value — reported, excluded
  from the geo split by default, with an include toggle.

## Verified numbers (against the real snapshot)
946,250 raw rows → **922,550 valid incidents**; 450,433 fall in the YTD window.
Example — *Motor Vehicle Incident, 2026 YTD vs 2021–2025*: median 26 min, p90 69, n = 2,919,
volume +35% vs the 5-year norm. (Matches an independent pandas check.)
