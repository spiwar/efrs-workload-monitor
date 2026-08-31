# Data Cautions — What the Agent Cannot Guess

*The Deletion Test: every line below, if removed, would let a wrong number ship. Things the agent
can read off the data for itself are deliberately not here. Read this before computing anything.*

## 1. `event_duration_mins` is NOT a response time. (The load-bearing line.)
It is `event_close_datetime − dispatch_datetime`: the total time the event file was open, from
first dispatch to the last unit leaving. **It contains no arrival/on-scene timestamp**, so it
cannot measure how fast crews reached the scene. The dataset also has **no call-received time**,
so it cannot measure call-to-dispatch delay either.
- ✅ Honest framing: "total event handling time" or "how long events tie up units."
- ❌ Forbidden framing: "response time," "time to arrival," or any NFPA-style turnout/travel benchmark.
- If someone needs true response times, **this dataset cannot answer it** — say so and stop.

## 2. Exclude non-incident records before any duration or volume metric.
The file mixes real incidents with administrative records that share the same columns:
- `TRAINING/MAINTENANCE` (~18,100 rows, **median "duration" 138 min**) — not a real call.
- `COMMUNITY EVENT` (~2,480), `PRE-INCIDENT PLANNING` (~515), `PERMIT-BURNING` (~10).
Leave these in and average duration roughly doubles. **Filter them out** for operational metrics,
or report them in a separate "non-incident activity" lane.

## 3. 2026 is a partial year (Jan–25 Jun only). Never compare it as a full year.
Year-over-year totals will show a fake collapse in 2026. For trend work, either compare
**year-to-date vs year-to-date** (same Jan–Jun window in prior years) or annualize explicitly and label it.

## 4. `UNKNOWN` neighbourhood is ~13% of rows — a literal value, not missing data.
~122,400 events are filed under the neighbourhood `UNKNOWN`. Any per-neighbourhood ranking or map
must decide openly whether to drop, bucket, or footnote them. Dropping them silently understates
real volume; keeping them creates a phantom "busiest neighbourhood."

## 5. `response_code` is undocumented — do not invent meanings.
The publisher ships this column with **no description**. The only safe reading is `AL` ≈ ALARMS
(co-occurs ~1:1). All other codes (`D`, `C`, `B`, `A`, `NF`, `SR`, `E`, `DG`, `ST`, `TT`, …) are
**unverified** — likely dispatch priority or disposition, but treat as opaque. If a code's meaning
is needed, confirm with Edmonton Open Data first; otherwise don't build a metric on it.

## 6. Clean the duration column before math.
~232 rows have a non-numeric duration, ~2,229 are exactly 0, and **32 are negative** (down to
−163 min, likely clock/midnight-rollover artifacts). Drop or cap these; don't let negatives drag a mean.

## 7. Location is geocoded to the nearest intersection, by design.
`latitude`/`longitude`/`approximate_location` point at the **closest intersection**, not the exact
address. Fine for neighbourhood-level patterns; do **not** present it as a precise incident location.

## 8. There is no station, crew, or apparatus-ID column.
`equipment_assigned` is a free-text count of unit *types* (e.g. `PUMPER(2)`), not identified units,
and there is **no responding-station field**. Station-level analysis is only possible by an
**approximate spatial join** to the Fire Stations dataset (`b4y7-zhnz`) — flag it as approximate.

## 9. Counts reflect dispatches, not unique emergencies or workload hours.
One emergency can generate one row regardless of how many units or hours it consumed; `equipment_assigned`
hints at scale but isn't a person-hours measure. "Number of events" ≠ "amount of work."
