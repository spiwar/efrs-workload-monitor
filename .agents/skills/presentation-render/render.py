#!/usr/bin/env python3
"""
presentation-render / render.py  (DETERMINISTIC)

Stages the EFRS Workload Monitor's written claim in a FIXED order and guarantees the
spec's required labels. Same input -> same output. No analytical judgment: the
interpreter subagent supplies the reading; this formats it.

Exit 0 = block produced with all guarantees. Exit 1 = a required guarantee failed.

Example:
    python render.py --event "Motor Vehicle Incidents" --period "Q2 2026" \
      --baseline "Q2 2021-2025" --median 27 --p90 58 --n 3140 \
      --baseline-median 26 --volume-pct +8 \
      --concentration "15:00-18:00 in Downtown and Boyle Street" \
      --reading "Handling time is stable; volume is up." --unknown-pct 12 --unknown excluded
"""
import sys
import argparse


def build_block(a):
    lines = []
    # 1. Headline
    lines.append(f"{a.event} — {a.period} vs {a.baseline} norm.")

    # 2 + 3. Handling time (with N) + baseline
    core = (f"Median handling time (dispatch→close) {a.median} min "
            f"(p90 {a.p90}), n = {a.n:,}")
    if a.baseline_median is not None:
        core += f" vs a 5-year median of {a.baseline_median} min."
    else:
        core += "."
    lines.append(core)

    # 4. Volume
    if a.volume_pct is not None:
        lines.append(f"Volume {a.volume_pct}% vs the norm" +
                     (f", concentrated {a.concentration}." if a.concentration else "."))
    elif a.concentration:
        lines.append(f"Concentrated {a.concentration}.")

    # 6. Reading (from interpreter)
    if a.reading:
        lines.append(a.reading)

    # 7. Fixed notes
    notes = ["Note: handling time is dispatch→close, not arrival time."]
    if a.unknown_pct is not None:
        notes.append(f"UNKNOWN-neighbourhood events ({a.unknown_pct}%) "
                     f"{a.unknown} from the geographic split.")
    lines.append(" ".join(notes))

    # Partial-year label
    if "2026" in a.period:
        lines.append("(2026 is partial — Jan–Jun year-to-date.)")

    return "\n".join(lines)


def check_guarantees(block, args):
    failures = []
    if "handling time (dispatch→close)" not in block:
        failures.append("missing required 'handling time (dispatch->close)' label")
    if "response time" in block.lower():
        failures.append("forbidden phrase 'response time' present")
    if "n = " not in block:
        failures.append("a duration figure is missing its N")
    if "2026" in args.period and "partial" not in block.lower():
        failures.append("2026 period not labelled partial")
    if args.unknown_pct is not None and "UNKNOWN" not in block:
        failures.append("UNKNOWN-neighbourhood policy line missing")
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--period", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--median", required=True)
    ap.add_argument("--p90", required=True)
    ap.add_argument("--n", required=True, type=int)
    ap.add_argument("--baseline-median", dest="baseline_median", default=None)
    ap.add_argument("--volume-pct", dest="volume_pct", default=None)
    ap.add_argument("--concentration", default=None)
    ap.add_argument("--reading", default=None)
    ap.add_argument("--unknown-pct", dest="unknown_pct", default=None)
    ap.add_argument("--unknown", default="excluded", choices=["excluded", "included"])
    args = ap.parse_args()

    block = build_block(args)
    failures = check_guarantees(block, args)

    print(block)
    if failures:
        print("\nRENDER GUARANTEE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
