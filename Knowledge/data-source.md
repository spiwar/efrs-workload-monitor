# Data Source

*Connect the source so the agent reads it in full — do not paste a fragment.*

## Primary source — Fire Response (Current and Historical)

- **Publisher:** City of Edmonton Open Data Portal — Edmonton Fire Rescue Services
- **Dataset ID:** `7hsn-idqi`
- **Portal page:** https://data.edmonton.ca/Emergency-Services/Fire-Response_Current-and-Historical/7hsn-idqi
- **Update frequency:** Daily, automated. Quality indicators: duplicates removed, verified for accuracy.
- **License:** City of Edmonton Open Data — see portal Terms of Use.
- **Coverage in the file we hold:** 1 Jan 2011 → 25 Jun 2026 (snapshot dated 2026-06-26).

### Local copy (frozen snapshot)
- `../Dataset/Fire_Response_Current_and_Historical_20260626.csv` (~946,250 rows, 25 columns).
- This is a point-in-time export. For a live dashboard, read the API instead so the view stays current.

### Live API (Socrata / SODA) — the connected source
Records endpoint (JSON / CSV):
```
https://data.edmonton.ca/resource/7hsn-idqi.json?$limit=50000&$offset=0
```
Useful patterns:
- Filter by year: `?dispatch_year=2025`
- Server-side aggregate (counts by neighbourhood):
  `?$select=neighbourhood_name,count(1)&$group=neighbourhood_name&$order=count_1 DESC`
- Recent window: `?$where=dispatch_datetime > '2026-01-01T00:00:00'`
- A free **App Token** raises rate limits; not required for low volume.

## Companion source (optional join) — Fire Stations
- **Dataset ID:** `b4y7-zhnz` (map view `phf8-mpfm`)
- Locations of Edmonton fire stations and whether an EMS unit is co-located.
- **Why it matters:** the response dataset has **no station ID**. Stations can only be brought
  in by a spatial join on lat/long, and that is approximate. See `data-cautions.md`.

## What is NOT available here
There is no separate codebook file shipped with the data. The authoritative field definitions
live in the portal's column metadata; they are distilled in `data-dictionary.md`. The `response_code`
values are **not documented** by the publisher (see cautions).
