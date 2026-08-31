# Data Dictionary (curated)

*Field definitions are the publisher's, distilled. Full official metadata: dataset `7hsn-idqi` on
data.edmonton.ca. Only the columns that carry the project are described in depth; the rest are
listed so the agent knows they exist.*

One row = **one fire-response event** (`event_number`, unique; no duplicates in the file).

## Columns that carry the project

| Column | Meaning (publisher) | Notes for use |
| :--- | :--- | :--- |
| `event_number` | Unique identifier for an event. | Primary key. |
| `dispatch_datetime` | When the **first units are dispatched**. Blank if no units assigned. | Start of the clock. **This is dispatch, not call-received and not arrival.** |
| `event_close_datetime` | When the **last unit leaves** or the dispatch centre closes the file. Blank = event still open. | End of the clock. |
| `event_duration_mins` | **`event_close_datetime − dispatch_datetime`, in minutes.** | **NOT a response/arrival time.** It is total time the event was open. See `data-cautions.md`. |
| `event_type_group` | Short code for the event class (e.g. `MD`, `AL`, `TA`, `OF`, `FR`). | Pairs with `event_description`. |
| `event_description` | Plain-language event class (MEDICAL, ALARMS, MOTOR VEHICLE INCIDENT, OUTSIDE FIRE, FIRE, …). | Use this for grouping; clearer than the code. |
| `response_code` | *(Publisher description is blank — undocumented.)* | Do **not** invent meanings. `AL` co-occurs almost 1:1 with ALARMS; the rest are unverified. See cautions. |
| `equipment_assigned` | Number and type of units sent (e.g. `PUMPER(1)`; `DCCAR(1), LADDER(1), PUMPER(2), RESCUE(1)`). | Free-text list, not normalized. `NO UNITS DISPTCHED` is a real value. |
| `neighbourhood_name` | Neighbourhood of the event. | `UNKNOWN` is a frequent literal value, not missing. ~13% of rows. |
| `neighbourhood_id` | Numeric neighbourhood identifier. | — |
| `approximate_location` | Nearest intersection (not exact address). | Location is geocoded to the **closest intersection**, deliberately coarse. |
| `latitude` / `longitude` | Coordinates of the closest intersection (WGS84). | ~0.03% missing. Coarse by design. |

## Convenience / derived columns (the agent can read these directly — listed, not explained)
`dispatch_year`, `dispatch_month`, `dispatch_month_name`, `dispatch_day`, `dispatch_dayofweek`,
`dispatch_date`, `dispatch_date_date`, `dispatch_time`, `event_close_date`, `event_close_date_date`,
`event_close_time`, `geometry_point`.

> `dispatch_datetime` uses a **12-hour clock with AM/PM** (e.g. `2026/04/15 11:46:32 PM`).
> Parse with `%Y/%m/%d %I:%M:%S %p`, or use the split date/time columns. (Recorded because a
> naïve 24-hour parse silently corrupts every PM timestamp.)
