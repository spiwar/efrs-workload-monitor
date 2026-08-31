#!/usr/bin/env python3
"""
incident-data-guard / validate.py  (HARD GATE)

Enforces the EFRS Incident Duration & Workload Monitor's fixed cleaning rules
BEFORE any duration or volume metric is computed. Mirrors Kinquiry's
codebook-guard: a rule enforced in code, not hoped for.

Exit 0 = clean & safe to compute. Exit 1 = a rule was violated.

Usage:
    python validate.py <csv>                 # validate only
    python validate.py <csv> --clean out.csv # validate + write cleaned rows
"""
import sys
import argparse
import pandas as pd

# --- FIXED RULES (AGENTS.md sec.5 + Knowledge/data-cautions.md) ---
NON_INCIDENT = {
    "TRAINING/MAINTENANCE",
    "COMMUNITY EVENT",
    "PRE-INCIDENT PLANNING",
}
NON_INCIDENT_PREFIXES = ("PERMIT-BURNING",)  # matches "PERMIT-BURNING OR OTHER"
TS_FORMAT = "%Y/%m/%d %I:%M:%S %p"           # 12-hour, AM/PM


def is_non_incident(desc) -> bool:
    if not isinstance(desc, str):
        return False
    d = desc.strip().upper()
    if d in NON_INCIDENT:
        return True
    return any(d.startswith(p) for p in NON_INCIDENT_PREFIXES)


def validate(path, clean_out=None):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    n0 = len(df)
    report = []
    violations = 0

    # Rule 0: required columns must exist
    required = {"event_description", "event_duration_mins",
                "dispatch_datetime", "neighbourhood_name"}
    missing = required - set(df.columns)
    if missing:
        print(f"FAIL rule-0 (schema): missing columns {sorted(missing)}")
        return 1

    # Rule 2: exclude non-incident administrative records
    mask_nonincident = df["event_description"].map(is_non_incident)
    n_nonincident = int(mask_nonincident.sum())
    df = df[~mask_nonincident]
    report.append(f"rule-2 non-incident records excluded: {n_nonincident}")

    # Rule 4: dispatch_datetime must be present & parse under the FIXED format
    blank_dispatch = (df["dispatch_datetime"].str.strip() == "")
    n_blank = int(blank_dispatch.sum())
    df = df[~blank_dispatch]
    parsed = pd.to_datetime(df["dispatch_datetime"], format=TS_FORMAT, errors="coerce")
    bad_ts = parsed.isna()
    n_bad_ts = int(bad_ts.sum())
    df = df[~bad_ts]
    report.append(f"rule-4 blank dispatch_datetime dropped: {n_blank}")
    report.append(f"rule-4 unparseable timestamps dropped: {n_bad_ts}")

    # Rule 3: clean duration -> numeric, drop non-numeric / <= 0
    dur = pd.to_numeric(df["event_duration_mins"], errors="coerce")
    n_nonnumeric = int(dur.isna().sum())
    nonpos = (dur <= 0)
    n_nonpos = int(nonpos.fillna(False).sum())
    keep_dur = dur.notna() & (dur > 0)
    df = df[keep_dur]
    report.append(f"rule-3 non-numeric durations dropped: {n_nonnumeric}")
    report.append(f"rule-3 zero/negative durations dropped: {n_nonpos}")

    # Rule 5: UNKNOWN neighbourhood is reported, NOT silently dropped
    n_unknown = int((df["neighbourhood_name"].str.strip().str.upper() == "UNKNOWN").sum())
    pct_unknown = (100 * n_unknown / len(df)) if len(df) else 0
    report.append(f"rule-5 UNKNOWN neighbourhood retained (state policy on screen): "
                  f"{n_unknown} ({pct_unknown:.1f}%)")

    # --- HARD GATE CHECK: nothing non-incident may survive ---
    leaked = df["event_description"].map(is_non_incident).sum()
    if leaked > 0:
        print(f"FAIL rule-2: {leaked} non-incident rows survived cleaning")
        violations += 1
    # --- HARD GATE CHECK: no non-positive / non-numeric duration may survive ---
    dur_final = pd.to_numeric(df["event_duration_mins"], errors="coerce")
    if dur_final.isna().any() or (dur_final <= 0).any():
        print("FAIL rule-3: invalid duration survived cleaning")
        violations += 1

    n_keep = len(df)
    print("=== incident-data-guard report ===")
    print(f"input rows:  {n0}")
    for line in report:
        print(f"  - {line}")
    print(f"VALID incident rows kept: {n_keep}")

    if clean_out and violations == 0:
        df.to_csv(clean_out, index=False)
        print(f"cleaned rows written to: {clean_out}")

    if violations:
        print(f"RESULT: FAIL ({violations} rule violation(s)) - DO NOT compute metrics.")
        return 1
    print("RESULT: PASS - safe to compute metrics on the kept rows.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--clean", dest="clean_out", default=None)
    args = ap.parse_args()
    sys.exit(validate(args.csv, args.clean_out))
