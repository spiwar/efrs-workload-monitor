# Data Profile

*A profiled snapshot of the actual file, so the agent and the team know what one row is and how
representative the data is. Figures computed from
`../Dataset/Fire_Response_Current_and_Historical_20260626.csv` on 2026-06-26 and reproducible
(see `research/` notes / verification). Round in the dashboard; these are the source figures.*

## Shape & coverage
- **946,250 rows × 25 columns.** One row per event; `event_number` unique (0 duplicates).
- **Date range:** 2011-01-01 → 2026-06-25.
- **2026 is partial** (Jan–Jun, 33,605 rows). See caution #3.

### Events per year
| Year | Events | | Year | Events |
| :--- | ---: | :-- | :--- | ---: |
| 2011 | 49,794 | | 2019 | 57,500 |
| 2012 | 38,703 | | 2020 | 54,939 |
| 2013 | 41,041 | | 2021 | 67,698 |
| 2014 | 43,653 | | 2022 | 80,153 |
| 2015 | 49,198 | | 2023 | 97,209 |
| 2016 | 50,304 | | 2024 | 88,500 |
| 2017 | 51,477 | | 2025 | 88,472 |
| 2018 | 54,004 | | 2026* | 33,605 |

Volume roughly doubled from ~40–50K/yr (early 2010s) to ~88–97K/yr (2023–25). *2026 partial.

## Event mix (what EFRS actually responds to)
| Event description | Rows | Share |
| :--- | ---: | ---: |
| MEDICAL | 535,314 | 56.6% |
| ALARMS | 143,682 | 15.2% |
| MOTOR VEHICLE INCIDENT | 64,451 | 6.8% |
| OUTSIDE FIRE | 48,027 | 5.1% |
| CITIZEN ASSIST | 35,444 | 3.7% |
| FIRE | 24,226 | 2.6% |
| HAZARDOUS MATERIALS | 19,938 | 2.1% |
| TRAINING/MAINTENANCE † | 18,109 | 1.9% |
| (blank / unclassified) | ~32,200 | 3.4% |
| RESCUE, VEHICLE FIRE, COMMUNITY EVENT, others | remainder | — |

† Non-incident administrative records — exclude for operational metrics (caution #2).
**The dataset is a medical-and-alarms operation far more than a fire operation.**

## Duration (dispatch → close), in minutes
Overall: **median 14, mean 23.3** (p90 = 41, p95 = 68, p99 = 189, max 997). Long right tail.

Median / mean by event type — note how event class drives duration:
| Event | Count | Median | Mean |
| :--- | ---: | ---: | ---: |
| MEDICAL | 535,281 | 13 | 15.7 |
| ALARMS | 143,674 | 13 | 16.8 |
| MOTOR VEHICLE INCIDENT | 64,443 | 27 | 34.7 |
| OUTSIDE FIRE | 48,013 | 13 | 17.8 |
| FIRE | 24,097 | 25 | 49.5 |
| HAZARDOUS MATERIALS | 19,932 | 20 | 29.4 |
| TRAINING/MAINTENANCE † | 18,103 | 138 | 182.6 |

## Time pattern
- **Busiest hours:** afternoon/early evening — peak 12:00–18:00 (each hour ~50–56K events);
  quietest 03:00–05:00 (~19–21K).
- **By weekday:** nearly flat; Friday highest (140,118), Tuesday lowest (129,979).

## Geography
- **415 distinct neighbourhood values**, including the literal `UNKNOWN` (122,423 rows ≈ 12.9%).
- Highest real neighbourhoods: Downtown (50,374), McCauley (45,148), Boyle Street (20,009),
  Central McDougall (19,771), Oliver (18,589) — the urban core dominates.
- Coordinates present for ~99.97% of rows (nearest-intersection geocoding).

## Quality flags (carried into `data-cautions.md`)
- Duration: 232 non-numeric, 2,229 zeros, 32 negative.
- `event_type_group` ~3.3% blank; `event_description` ~3.4% blank.
- 186 rows have blank `dispatch_datetime` (no units assigned).
- `NO UNITS DISPTCHED` appears as an `equipment_assigned` value (9,789 rows).
