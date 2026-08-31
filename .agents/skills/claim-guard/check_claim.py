#!/usr/bin/env python3
"""
claim-guard / check_claim.py  (ADVISORY LINTER)

Reads draft user-facing text for the EFRS Workload Monitor and flags the claims the
spec forbids (AGENTS.md sec.2 "must-never-produce"). Advisory: it flags, the writer
rewrites. Mirrors Kinquiry's interpretation-guardrails check_claim.py.

Exit 0 = no flags. Exit 2 = at least one flag.

Usage:
    python check_claim.py "<text>"
    python check_claim.py --file draft.txt
    echo "<text>" | python check_claim.py -
"""
import sys
import re

# (rule_id, compiled pattern, message, suggested fix)
RULES = [
    ("rule-1 response-time",
     re.compile(r"\b(response\s*time|time\s*to\s*arrival|arrival\s*time|"
                r"turnout\s*time|travel\s*time|nfpa|how\s*fast.*(arriv|respond))\b", re.I),
     "Handling time is dispatch->close; the data has NO arrival timestamp.",
     'Use "event handling time (dispatch->close)".'),
    ("rule-2 full-year-2026",
     re.compile(r"\b(total|annual|full[-\s]?year|whole\s*year).{0,30}\b2026\b"
                r"|\b2026\b.{0,30}\b(total|annual|full[-\s]?year)\b", re.I),
     "2026 is partial (Jan-25 Jun); a full-year/total reading is misleading.",
     "Compare year-to-date vs same window in prior years; label 2026 partial."),
    ("rule-3 response_code-meaning",
     re.compile(r"response[_\s]?code\s*(=|is|means|of)\s*[\"']?(?!AL\b)[A-Z]{1,3}\b", re.I),
     "Only AL ~ ALARMS is documented; other codes are opaque.",
     "Do not assert a meaning for codes other than AL."),
    ("rule-4 station-performance",
     re.compile(r"\bstation[-\s]?(level|performance|by\s*station)\b", re.I),
     "No station field exists; this is not station performance.",
     "Report at neighbourhood granularity only."),
    ("rule-5 address-precision",
     re.compile(r"\b(exact|precise|street)\s*address|address[-\s]?level\b", re.I),
     "Data is geocoded to the nearest intersection, by design.",
     "State location as nearest intersection / neighbourhood."),
    ("rule-6 causal-predictive",
     re.compile(r"\b(caused?\s*by|because\s*of|due\s*to|led\s*to|will\s+(rise|fall|increase|"
                r"decrease|be)|predict|forecast|driven\s*by)\b", re.I),
     "This is monitoring, not inference; no causal/predictive claims.",
     'Use descriptive language ("associated with", "concentrated in").'),
]

# Detect an unsupported user REQUEST -> refusal candidate
REFUSAL = re.compile(r"\b(response\s*time|time\s*to\s*arrival|arrival\s*time|"
                     r"how\s*fast.*(arriv|respond)|station[-\s]?(level|performance))\b", re.I)

# Approved disclaimers: a sentence that DENIES a response/arrival reading is correct,
# not a violation. Strip these spans before linting so we flag claims, not disclaimers.
DISCLAIMER = re.compile(r"\bnot\b[^.;,]{0,40}\b(arrival|response)\b[^.;,]{0,20}", re.I)


def strip_disclaimers(text):
    return DISCLAIMER.sub(" ", text)


def lint(text):
    flags = []
    for rid, pat, msg, fix in RULES:
        for m in pat.finditer(text):
            flags.append((rid, m.group(0).strip(), msg, fix))
    return flags


def main():
    args = sys.argv[1:]
    if not args:
        print('usage: check_claim.py "<text>" | --file f | -')
        return 2
    if args[0] == "--file":
        text = open(args[1], encoding="utf-8").read()
    elif args[0] == "-":
        text = sys.stdin.read()
    else:
        text = " ".join(args)

    # Correct disclaimers ("...not arrival time") are not violations; strip them first.
    text = strip_disclaimers(text)

    flags = lint(text)

    if REFUSAL.search(text):
        print("REFUSAL: request appears to ask for an unsupported metric "
              "(response/arrival time or station performance).")
        print("  -> Decline, explain the dataset cannot support it, and append to "
              "refusal_log.csv (timestamp, request, reason).")

    if not flags:
        print("claim-guard: PASS - no forbidden claims detected.")
        return 0

    print(f"claim-guard: {len(flags)} flag(s) (advisory - rewrite before shipping):")
    for rid, span, msg, fix in flags:
        print(f"  [{rid}] matched: \"{span}\"")
        print(f"      why: {msg}")
        print(f"      fix: {fix}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
