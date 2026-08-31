#!/usr/bin/env python3
"""
EFRS Incident Duration & Workload Monitor - backend.

FIXED cleaning rules (AGENTS.md sec.5). Duration is ALWAYS event handling time
(dispatch->close), never response time. Predictive features forecast VOLUME/workload
only, with intervals, never causal. Decision-support answers describe demand patterns
and workload; the lead owns every resourcing decision (sec.6).

Data: full-year cleaned snapshot cached in .cache_v5.pkl; optional incremental
live refresh from the SODA API (dataset 7hsn-idqi, updated daily by the city).
"""
import os, re, json, datetime
import urllib.request, urllib.parse
from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "..", "Dataset",
                           "Fire_Response_Current_and_Historical_20260626.csv")
CSV_PATH = os.environ.get("EFRS_CSV", DEFAULT_CSV)
CACHE_PATH = os.path.join(HERE, ".cache_v5.pkl")
LOG_DIR = os.path.join(HERE, "logs")
TS_FORMAT = "%Y/%m/%d %I:%M:%S %p"
SODA_URL = "https://data.edmonton.ca/resource/7hsn-idqi.json"

# Optional Gemini phrasing layer for the chatbot. The deterministic backend below
# computes EVERY number; Gemini (when configured) only rephrases the already-correct
# answer conversationally. It never sees the raw data and cannot invent a figure. The
# refusal gate runs in code BEFORE any Gemini call. Falls back to the deterministic
# wording whenever the SDK/credentials are absent or the call fails, so the app always
# runs offline. Model per project default; override with EFRS_GEMINI_MODEL.
#
# Runs via Vertex AI (auth = Application Default Credentials, `gcloud auth
# application-default login`), not the AI Studio API key. Project/location come from env
# with a project default; override GEMINI_PROJECT / GEMINI_LOCATION as needed.
GEMINI_MODEL = os.environ.get("EFRS_GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_PROJECT = (os.environ.get("GEMINI_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
GEMINI_LOCATION = (os.environ.get("GEMINI_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION")
                   or "global")
GEMINI_ENABLED = bool(GEMINI_PROJECT)

NON_INCIDENT = {"TRAINING/MAINTENANCE", "COMMUNITY EVENT", "PRE-INCIDENT PLANNING"}
NON_INCIDENT_PREFIX = ("PERMIT-BURNING",)
EXCLUSION_NOTE = ("Non-incident records (TRAINING/MAINTENANCE, COMMUNITY EVENT, "
                  "PRE-INCIDENT PLANNING, PERMIT-BURNING) are excluded from all metrics.")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
EQ_TOKEN = re.compile(r"([A-Z]+)\((\d+)\)")

FORBIDDEN = re.compile(r"\b(response\s*time|time\s*to\s*arriv\w*|arrival\s*time|eta|"
                       r"turnout|travel\s*time|nfpa|"
                       r"how\s*(fast|long|quick\w*|soon|rapid\w*).{0,40}(arriv\w*|respond\w*|"
                       r"get\s*there|show\s*up|reach\w*|on\s*scene)|"
                       r"time\s*to\s*(respond|reach|get\s*there|show\s*up|on\s*scene)|"
                       r"station[-\s]?(level|performance|by\s*station))\b", re.I)
# "how many" deliberately excluded: count questions (esp. with an hour/weekday filter) route
# to the query-planner, which honours those filters; this stays for staffing/planning intent.
RESOURCING = re.compile(r"\b(schedule|staff\w*|resourc\w*|truck\w*|apparatus|engine\w*|"
                        r"pumper\w*|crew\w*|deploy\w*|cover\w*|when\s*should|where\s*should|"
                        r"prepare|plan\w*|peak|busiest|allocate)\b", re.I)
# Station-performance asks (F5). There is no station field in the dataset, so any
# station-comparison/ranking question is refused. STATION_OK exempts unrelated place
# types ("gas station", "transit station") so those aren't wrongly refused.
STATION = re.compile(r"(which|what|slowest|fastest|best|worst|rank\w*|compar\w*|busiest|"
                     r"performance|slow|fast)\b[^?]{0,30}\bstations?\b|"
                     r"\bstations?\b[^?]{0,30}(slow\w*|fast\w*|perform\w*|rank\w*|best|worst|"
                     r"compar\w*|respond\w*|arriv\w*|busiest)", re.I)
STATION_OK = re.compile(r"\b(gas|petrol|fuel|transit|power|train|bus|subway|lrt|charging|"
                        r"weather|space|radio|police)\s+stations?\b", re.I)
# On-topic gate: this assistant only answers about incident VOLUME, HANDLING TIME,
# WORKLOAD, and WHERE/WHEN demand concentrates. A question with no concrete data signal
# (no event type, no neighbourhood, no forecast/resourcing intent, and none of these
# keywords) is off-topic — we redirect instead of dumping a stray default KPI. Requiring
# a concrete word (not vague ones like "data"/"impactful") is what stops "meaning of
# life" and "what's the most impactful thing?" from returning a confident wrong number.
ON_TOPIC = re.compile(r"\b(incident\w*|event\w*|call\w*|fire\w*|medical|ems|alarm\w*|rescue\w*|"
                      r"volume|count\w*|how\s*many|number\s*of|total|tally|"
                      r"handling|duration|median|p90|percentile|minutes?|how\s*long|"
                      r"busiest|busy|peak|when|what\s*time|hour\w*|weekday\w*|"
                      r"morning|afternoon|evening|night|day|month\w*|"
                      r"forecast|predict\w*|project\w*|trend\w*|outlook|next|coming|expect|future|"
                      r"workload|demand|hotspot\w*|norm|baseline|compar\w*|above|below|rising|"
                      r"neighbou?rhood\w*|area\w*|district\w*|where|map)\b", re.I)
# Editorial / open-ended asks ("what's most notable?", "summarise this", "what stands
# out?"). These are ON-topic and route to the deterministic digest, which the LLM then
# phrases into a short reading. Numbers still come from code; the model only writes prose.
EDITORIAL = re.compile(r"\b(most\s+(impactful|notable|important|concerning|interesting|significant|"
                       r"striking|surprising)|impactful|notable|takeaways?|highlight\w*|"
                       r"summ(ary|arise|arize|aries)|overview|recap|big\s+picture|"
                       r"stands?\s+out|standout|what\s+should\s+i\s+know|"
                       r"anything\s+(unusual|notable|concerning|interesting|off)|"
                       r"what'?s?\s+(unusual|notable|interesting|going\s+on|happening|the\s+story)|"
                       r"key\s+(insight\w*|finding\w*|takeaway\w*|point\w*)|what\s+changed|"
                       r"biggest\s+(change|shift|concern|issue|deal|story)|most\s+concerning)\b", re.I)

app = Flask(__name__, static_folder=os.path.join(HERE, "static"))
DATA = {}


def _is_non_incident(desc):
    d = str(desc).strip().upper()
    return d in NON_INCIDENT or any(d.startswith(p) for p in NON_INCIDENT_PREFIX)


def _log(name, row):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, name)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as f:
            if new:
                f.write("timestamp,detail\n")
            f.write(f'{datetime.datetime.now().isoformat()},"{row}"\n')
    except Exception as e:
        print("[EFRS] log skipped:", e)


def _count_log(name):
    path = os.path.join(LOG_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    except OSError:
        return 0


# ---------------- data build ----------------
def _eq_columns(series, eq_types):
    """Unit-TYPE counts parsed from equipment_assigned ('PUMPER(2), LADDER(1)').
    These are unit types listed on dispatch, NOT identified apparatus or crew-hours
    (data-cautions sec.8)."""
    uniq = series.unique()
    parsed = {u: {t: int(n) for t, n in EQ_TOKEN.findall(str(u))} for u in uniq}
    out = pd.DataFrame(index=series.index)
    for t in eq_types:
        out["eq_" + t] = series.map({u: p.get(t, 0) for u, p in parsed.items()}).astype("int16")
    out["eq_total"] = series.map({u: sum(p.values()) for u, p in parsed.items()}).astype("int16")
    return out


def _features(raw, dt, dur, eq_types):
    df = pd.DataFrame(index=raw.index)
    df["dur"] = dur.astype(float)
    df["year"] = dt.dt.year.astype("int16")
    df["month"] = dt.dt.month.astype("int8")
    df["day"] = dt.dt.day.astype("int8")
    df["hour"] = dt.dt.hour.astype("int8")
    df["weekday"] = dt.dt.dayofweek.astype("int8")
    df["desc"] = raw["event_description"].astype(str).str.strip().str.upper()
    df["nbhd"] = raw["neighbourhood_name"].astype(str).str.strip().str.upper().replace({"": "UNKNOWN"})
    eq = _eq_columns(raw["equipment_assigned"].astype(str), eq_types)
    for c in eq.columns:
        df[c] = eq[c]
    return df


def _derive(df):
    """Recompute everything derived from the row set (also called after a live refresh)."""
    # Global junk-type drop (F2): the spec says drop blank/NULL/MESS/len<4/<500-row event
    # types. Applying it here (not just to the dropdown) makes the on-screen "valid
    # incidents" total, the UNKNOWN %, and every slice consistent with each other. Decided
    # on lifetime counts so a type isn't dropped just for being thin in one window.
    _vc_all = df["desc"].value_counts()
    _bad = {"", "NULL", "MESS"}
    _valid = {e for e in _vc_all.index if e not in _bad and len(e) >= 4 and _vc_all[e] >= 500}
    df = df[df["desc"].isin(_valid)].copy()

    latest_year = int(df["year"].max())
    latest = df[df["year"] == latest_year]
    cm = int(latest["month"].max())
    cd = int(latest[latest["month"] == cm]["day"].max())
    DATA["cutoff"] = (cm, cd)
    DATA["latest"] = latest_year
    DATA["years"] = sorted(df["year"].unique().tolist())
    DATA["window_label"] = f"Jan 1 - {MONTHS[cm]} {cd} (year-to-date)"
    DATA["current_label"] = f"{MONTHS[cm]} {cd}, {latest_year}"
    DATA["days_default"] = _win_days(1, 1, cm, cd)

    g = df.groupby(["year", "month", "desc"]).size().reset_index(name="n")
    gall = df.groupby(["year", "month"]).size().reset_index(name="n"); gall["desc"] = "ALL"
    DATA["monthly"] = pd.concat([g, gall], ignore_index=True)
    DATA["max_month"] = cm
    DATA["dur_by_type"] = df.groupby("desc")["dur"].median().to_dict()
    DATA["dur_all"] = float(df["dur"].median())

    ytd = _window_mask(df, 1, 1, cm, cd, 0, 23)
    win = df[ytd]
    _vc = win.groupby("desc").size().sort_values(ascending=False)
    _bad = {"", "NULL", "MESS"}
    DATA["event_types"] = [e for e in _vc.index.tolist()
                           if e not in _bad and len(e) >= 4 and _vc[e] >= 500]
    DATA["unknown_pct"] = round(100 * (win["nbhd"] == "UNKNOWN").mean(), 1)
    DATA["n_total"] = int(len(win))
    DATA["df"] = df


def load_data():
    if "df" in DATA:
        return
    csv_exists = os.path.exists(CSV_PATH)
    cache_ok = os.path.exists(CACHE_PATH) and (
        not csv_exists or os.path.getmtime(CACHE_PATH) >= os.path.getmtime(CSV_PATH))
    if cache_ok:
        blob = pd.read_pickle(CACHE_PATH)
        if "df" in blob and "eq_types" in blob:
            DATA.update({k: blob[k] for k in ("centroids", "eq_types", "n_raw", "max_iso")})
            _derive(blob["df"])
            print(f"[EFRS] loaded {len(DATA['df']):,} incidents from cache")
            return
    if not csv_exists:
        raise RuntimeError("No cache (.cache_v5.pkl) and no source CSV. Provide EFRS_CSV "
                           "or commit the cache.")

    cols = ["dispatch_datetime", "event_duration_mins", "event_description",
            "neighbourhood_name", "latitude", "longitude", "equipment_assigned"]
    raw = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False, usecols=cols)
    n_raw = len(raw)
    raw = raw[~raw["event_description"].map(_is_non_incident)]
    raw = raw[raw["dispatch_datetime"].str.strip() != ""]
    dt = pd.to_datetime(raw["dispatch_datetime"], format=TS_FORMAT, errors="coerce")
    raw = raw[dt.notna()].copy(); dt = dt[dt.notna()]
    dur = pd.to_numeric(raw["event_duration_mins"], errors="coerce")
    keep = dur.notna() & (dur > 0)
    raw = raw[keep].copy(); dt = dt[keep]; dur = dur[keep]

    # global equipment vocabulary: top unit types by total units dispatched
    vc = raw["equipment_assigned"].value_counts()
    totals = {}
    for combo, cnt in vc.items():
        for t, n in EQ_TOKEN.findall(str(combo)):
            totals[t] = totals.get(t, 0) + int(n) * cnt
    eq_types = [t for t, _ in sorted(totals.items(), key=lambda kv: -kv[1])[:8]]

    df = _features(raw, dt, dur, eq_types)

    lat = pd.to_numeric(raw["latitude"], errors="coerce")
    lon = pd.to_numeric(raw["longitude"], errors="coerce")
    vcoord = lat.between(53.2, 53.9) & lon.between(-113.9, -113.1)
    cdf = pd.DataFrame({"nbhd": df["nbhd"][vcoord], "_lat": lat[vcoord], "_lon": lon[vcoord]})
    cent = cdf.groupby("nbhd").agg(lat=("_lat", "mean"), lon=("_lon", "mean")).round(5)
    centroids = {ix: (float(r["lat"]), float(r["lon"])) for ix, r in cent.iterrows()}

    DATA.update(dict(centroids=centroids, eq_types=eq_types, n_raw=n_raw,
                     max_iso=dt.max().strftime("%Y-%m-%dT%H:%M:%S")))
    _derive(df)
    try:
        pd.to_pickle(dict(df=df, centroids=centroids, eq_types=eq_types,
                          n_raw=n_raw, max_iso=DATA["max_iso"]), CACHE_PATH)
    except Exception as e:
        print("[EFRS] cache write skipped:", e)
    print(f"[EFRS] built {n_raw:,} raw -> {len(df):,} incidents; {len(centroids)} centroids; "
          f"equipment types: {eq_types}")


# ---------------- helpers ----------------
def _int_arg(name, default):
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def _year_arg():
    y = _int_arg("year", DATA["latest"])
    return y if y in DATA["years"] else DATA["latest"]


def _mmdd(s, default):
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", (s or "").strip())
    if not m:
        return default
    mo, dy = int(m.group(1)), int(m.group(2))
    if not 1 <= mo <= 12:
        return default
    return (mo, max(1, min(MONTH_DAYS[mo - 1], dy)))


def _window_args(year):
    """Parse from/to (MM-DD) and h1/h2 hour range; clamp the latest (partial) year
    to the data cutoff so it is never compared beyond the data it has."""
    cm, cd = DATA["cutoff"]
    m1, d1 = _mmdd(request.args.get("from"), (1, 1))
    m2, d2 = _mmdd(request.args.get("to"), (cm, cd) if year == DATA["latest"] else (12, 31))
    if year == DATA["latest"] and (m2, d2) > (cm, cd):
        m2, d2 = cm, cd
    if (m1, d1) > (m2, d2):
        m1, d1 = m2, d2
    h1 = max(0, min(23, _int_arg("h1", 0)))
    h2 = max(0, min(23, _int_arg("h2", 23)))
    if h1 > h2:
        h1, h2 = h2, h1
    return m1, d1, m2, d2, h1, h2


def _window_mask(df, m1, d1, m2, d2, h1, h2):
    a = (df["month"] > m1) | ((df["month"] == m1) & (df["day"] >= d1))
    b = (df["month"] < m2) | ((df["month"] == m2) & (df["day"] <= d2))
    w = a & b
    if h1 > 0 or h2 < 23:
        w &= (df["hour"] >= h1) & (df["hour"] <= h2)
    return w


def _win_days(m1, d1, m2, d2):
    return (datetime.date(2024, m2, d2) - datetime.date(2024, m1, d1)).days + 1


def _wlabel(m1, d1, m2, d2, h1, h2):
    s = f"{MONTHS[m1]} {d1} - {MONTHS[m2]} {d2}"
    if (h1, h2) != (0, 23):
        s += f", {h1:02d}:00-{h2:02d}:59"
    return s


def _slice(year, event, nbhd=None, wmask=None):
    df = DATA["df"]
    if wmask is None:
        cm, cd = DATA["cutoff"]
        wmask = _window_mask(df, 1, 1, cm, cd, 0, 23)
    s = df[wmask & (df["year"] == year)]
    if event and event != "ALL":
        s = s[s["desc"] == event]
    if nbhd:
        s = s[s["nbhd"] == nbhd]
    return s


def _stats(series):
    if len(series) == 0:
        return dict(n=0, median=None, p90=None, mean=None)
    return dict(n=int(len(series)), median=round(float(series.median()), 1),
                p90=round(float(series.quantile(0.90)), 1), mean=round(float(series.mean()), 1))


def _base_years(year):
    return [y for y in range(year - 5, year) if y in DATA["years"]]


def peak_concurrency(slc, median_min, days):
    """Estimate average simultaneous OPEN incidents in the busiest hour-of-day:
    (events/day in that hour) x (median handling time in hours). A workload measure,
    not an apparatus requirement."""
    if len(slc) == 0 or days <= 0:
        return None, None, None
    h = slc.groupby("hour").size()
    peak_hour = int(h.idxmax())
    per_day = h.max() / days
    conc = per_day * (median_min / 60.0)
    return peak_hour, round(conc, 2), round(per_day, 2)


def _kpi_text(label, year, cs, bs, vol_pct, mdelta, window_label, partial):
    base_txt = (f"vs a 5-year median of {bs['median']} min" if bs["median"] is not None
                else "(no comparable 5-year baseline for this period)")
    # F4: with no baseline (earliest years) mdelta is None — do NOT assert "down" against
    # nothing. Only state a direction when there is actually a norm to compare to.
    if mdelta is None:
        dirn_txt = "Handling time can't be compared — this period has no 5-year baseline."
    else:
        dirn = "stable" if abs(mdelta) <= 1 else ("up" if mdelta > 0 else "down")
        dirn_txt = f"Handling time is {dirn} vs the 5-year median."
    vol_txt = (f"Volume {'+' if (vol_pct or 0) >= 0 else ''}{vol_pct}% vs the norm. "
               if vol_pct is not None else "")
    ptxt = "partial year, " if partial else ""
    # Phrase the year as a period ("in 2026"), never a bare trailing number, and label the
    # count as "n = ... incidents" — a weak phrasing model was misreading the year 2026 as
    # a count of incidents. Keep both unambiguous so the figure cannot be mis-attributed.
    return (f"{label} in {year} ({ptxt}{window_label}): median handling time "
            f"(dispatch->close) {cs['median']} min (p90 {cs['p90']}) across n = {cs['n']:,} "
            f"incidents {base_txt}. {vol_txt}{dirn_txt} Note: handling time is "
            f"dispatch->close, not arrival time.")


# ---------------- meta ----------------
@app.route("/api/meta")
def meta():
    cm, cd = DATA["cutoff"]
    return jsonify(dict(
        years=DATA["years"][::-1], latest=DATA["latest"],
        event_types=[{"id": "ALL", "label": "All incident types"}] +
                    [{"id": e, "label": e.title()} for e in DATA["event_types"]],
        window_label=DATA["window_label"], exclusion_note=EXCLUSION_NOTE,
        unknown_pct=DATA["unknown_pct"], n_total=DATA["n_total"], n_raw=DATA["n_raw"],
        cutoff=[cm, cd], data_current_to=DATA["current_label"],
        eq_types=DATA["eq_types"], refusal_count=_count_log("refusal_log.csv"),
        refresh_count=_count_log("refresh_log.csv"),
        chat_llm=GEMINI_ENABLED, chat_model=(GEMINI_MODEL if GEMINI_ENABLED else None)))


# ---------------- metrics ----------------
@app.route("/api/metrics")
def metrics():
    year = _year_arg()
    event = request.args.get("event", "ALL").upper()
    unknown = request.args.get("unknown", "exclude")
    m1, d1, m2, d2, h1, h2 = _window_args(year)
    df = DATA["df"]
    wmask = _window_mask(df, m1, d1, m2, d2, h1, h2)
    wlabel = _wlabel(m1, d1, m2, d2, h1, h2)
    wdays = _win_days(m1, d1, m2, d2)
    partial = (year == DATA["latest"] and (m2, d2) >= DATA["cutoff"])

    cur = _slice(year, event, wmask=wmask)
    by = _base_years(year); nby = len(by)
    base = df[wmask & df["year"].isin(by)]
    if event != "ALL":
        base = base[base["desc"] == event]

    cs = _stats(cur["dur"]); bs = _stats(base["dur"])
    base_vol_mean = (len(base) / nby) if nby else 0
    vol_pct = (round(100 * (cs["n"] - base_vol_mean) / base_vol_mean, 1) if base_vol_mean else None)
    median_delta = (round(cs["median"] - bs["median"], 1)
                    if cs["median"] is not None and bs["median"] is not None else None)

    # committed event-hours: total time events were open (dispatch->close), NOT crew-hours
    eh_cur = round(float(cur["dur"].sum()) / 60)
    eh_base = round(float(base["dur"].sum()) / 60 / nby) if nby and len(base) else None
    eh_pct = (round(100 * (eh_cur - eh_base) / eh_base, 1) if eh_base else None)

    # Handling-time distribution: 5-min bins up to 55, then an explicit "55+" catch-all.
    # The final bin is unbounded on the right, so it must be LABELLED as such (F1) — the
    # old "55-60" label hid the long right tail (most of that bar runs well past 60 min).
    dv = cur["dur"].to_numpy(); bvd = base["dur"].to_numpy()
    dist = [{"bin": f"{lo}-{lo+5}", "count": int(((dv >= lo) & (dv < lo + 5)).sum()),
             "baseline": round(float(((bvd >= lo) & (bvd < lo + 5)).sum()) / nby, 1) if nby else 0}
            for lo in range(0, 55, 5)]
    dist.append({"bin": "55+", "count": int((dv >= 55).sum()),
                 "baseline": round(float((bvd >= 55).sum()) / nby, 1) if nby else 0})
    cur_h = cur.groupby("hour").size(); base_h = base.groupby("hour").size()
    by_hour = [dict(hour=h, current=int(cur_h.get(h, 0)),
                    baseline=round(float(base_h.get(h, 0)) / nby, 1) if nby else 0)
               for h in range(24)]
    cur_w = cur.groupby("weekday").size(); base_w = base.groupby("weekday").size()
    by_weekday = [dict(weekday=WEEKDAYS[k][:3], current=int(cur_w.get(k, 0)),
                       baseline=round(float(base_w.get(k, 0)) / nby, 1) if nby else 0)
                  for k in range(7)]

    hw = cur.groupby(["weekday", "hour"]).size()
    heat = [[int(hw.get((w, h), 0)) for h in range(24)] for w in range(7)]

    cn = cur if unknown == "include" else cur[cur["nbhd"] != "UNKNOWN"]
    bn = base if unknown == "include" else base[base["nbhd"] != "UNKNOWN"]
    base_nb = bn.groupby("nbhd").size()
    top = cn.groupby("nbhd").agg(count=("dur", "size"), median=("dur", "median")) \
            .sort_values("count", ascending=False).head(10)
    by_nbhd = [dict(name=ix.title(), count=int(r["count"]), median=round(float(r["median"]), 1),
                    baseline=round(float(base_nb.get(ix, 0)) / nby, 1) if nby else 0)
               for ix, r in top.iterrows()]
    by_type = []
    if event == "ALL":
        bt = cur.groupby("desc").agg(count=("dur", "size"), median=("dur", "median")) \
                .sort_values("count", ascending=False).head(8)
        by_type = [dict(type=ix.title(), count=int(r["count"]), median=round(float(r["median"]), 1))
                   for ix, r in bt.iterrows()]

    by_equipment = []
    for t in DATA["eq_types"]:
        c = int(cur["eq_" + t].sum())
        b = round(float(base["eq_" + t].sum()) / nby) if nby else 0
        by_equipment.append(dict(type=t, current=c, baseline=b))
    by_equipment.sort(key=lambda r: -r["current"])
    avg_units = round(float(cur["eq_total"].mean()), 2) if len(cur) else None

    movers = build_movers(year, wmask, unknown, event)
    insights = build_insights(year, event, cs, bs, vol_pct, median_delta, by_hour, by_weekday,
                              by_nbhd, by_type, unknown, wlabel, partial, heat, by_equipment,
                              avg_units, movers, eh_cur, eh_pct)
    flags = build_flags(event, cs, vol_pct, median_delta, by_hour, cur, base, nby)
    return jsonify(dict(
        year=year, event=event, partial=partial, window_label=wlabel,
        window=dict(m1=m1, d1=d1, m2=m2, d2=d2, h1=h1, h2=h2, days=wdays),
        baseline_years=by, selected=cs, baseline=bs,
        baseline_vol_mean=round(base_vol_mean, 0), vol_pct=vol_pct, median_delta=median_delta,
        event_hours=eh_cur, event_hours_base=eh_base, event_hours_pct=eh_pct,
        unknown_pct=round(100 * (cur["nbhd"] == "UNKNOWN").mean(), 1) if len(cur) else 0,
        unknown_policy=unknown, dist=dist, by_hour=by_hour, by_weekday=by_weekday, heat=heat,
        by_nbhd=by_nbhd, by_type=by_type, by_equipment=by_equipment, avg_units=avg_units,
        movers=movers, insights=insights, flags=flags))


def build_movers(year, wmask, unknown, event="ALL"):
    """Event-type x neighbourhood cells most divergent from their own 5-yr norm this window.
    For 'ALL' it scans across every event type (a cross-event radar); when a specific event
    is selected it restricts to that type's neighbourhood cells so the table tracks the
    filter. Thresholds: current n >= 15, expected >= 8/yr, divergence >= 25%."""
    df = DATA["df"]; by = _base_years(year); nby = len(by)
    if not nby:
        return []
    cur = df[wmask & (df["year"] == year)]
    base = df[wmask & df["year"].isin(by)]
    if event != "ALL":
        cur = cur[cur["desc"] == event]; base = base[base["desc"] == event]
    if unknown != "include":
        cur = cur[cur["nbhd"] != "UNKNOWN"]; base = base[base["nbhd"] != "UNKNOWN"]
    cg = cur.groupby(["desc", "nbhd"]).size()
    bg = base.groupby(["desc", "nbhd"]).size() / nby
    rows = []
    for key, c in cg.items():
        b = float(bg.get(key, 0))
        if b >= 8 and c >= 15:
            pct = 100 * (c - b) / b
            if abs(pct) >= 25:
                rows.append(dict(event=key[0].title(), nbhd=key[1].title(),
                                 n=int(c), expected=round(b), pct=round(pct)))
    rows.sort(key=lambda r: -abs(r["pct"]))
    return rows[:6]


def build_flags(event, cs, vol_pct, mdelta, by_hour, cur, base, nby):
    """Short list of what's UNUSUAL this period vs the 5-year norm (decision triage)."""
    # F4: don't reassure ("nothing unusual ... track the 5-year norm") when there is
    # nothing to compare against. Say so plainly instead.
    if cs["n"] == 0:
        return [dict(sev="warn", text="No incidents match this selection in the chosen "
                                      "window — there is nothing to compare to a norm.")]
    if not nby:
        return [dict(sev="warn", text="No 5-year baseline exists for this period (it is among "
                                      "the earliest years in the data), so volume and handling "
                                      "time can't be compared to a prior norm.")]
    flags = []
    if vol_pct is not None and vol_pct >= 10:
        flags.append(dict(sev="up", text=f"Volume is {vol_pct:.0f}% ABOVE the 5-year norm (n = {cs['n']:,})."))
    elif vol_pct is not None and vol_pct <= -10:
        flags.append(dict(sev="down", text=f"Volume is {abs(vol_pct):.0f}% BELOW the 5-year norm (n = {cs['n']:,})."))
    if mdelta is not None and mdelta >= 2:
        flags.append(dict(sev="up", text=f"Median handling time is up {mdelta:.0f} min vs the norm (now {cs['median']:.0f} min)."))
    elif mdelta is not None and mdelta <= -2:
        flags.append(dict(sev="down", text=f"Median handling time is down {abs(mdelta):.0f} min vs the norm (now {cs['median']:.0f} min)."))
    hot = [(x["hour"], (x["current"] - x["baseline"]) / x["baseline"] * 100)
           for x in by_hour if x["baseline"] >= 5]
    hot = sorted([h for h in hot if h[1] >= 25], key=lambda z: -z[1])
    if hot:
        flags.append(dict(sev="up", text=f"{len(hot)} hour(s) running >=25% above their norm — biggest gap at "
                                         f"{hot[0][0]:02d}:00 (+{hot[0][1]:.0f}%)."))
    if nby:
        cg = cur[cur["nbhd"] != "UNKNOWN"].groupby("nbhd").size()
        bg = base[base["nbhd"] != "UNKNOWN"].groupby("nbhd").size() / nby
        ab = []
        for nb, c in cg.items():
            b = bg.get(nb, 0)
            if b >= 3 and (c - b) / b >= 0.25:
                ab.append((nb.title(), round(100 * (c - b) / b)))
        if ab:
            ab.sort(key=lambda z: -z[1])
            names = ", ".join(f"{n} (+{p}%)" for n, p in ab[:3])
            flags.append(dict(sev="warn", text=f"{len(ab)} neighbourhood(s) >=25% above their own norm — "
                                               f"e.g. {names}. See the Hotspot map."))
    f = forecast_volume(event, 6)
    if f and abs(f["level"] - 1) >= 0.15:
        d = round((f["level"] - 1) * 100)
        flags.append(dict(sev="warn", text=f"Projected volume is {abs(d)}% {'above' if d > 0 else 'below'} the "
                                           "seasonal norm — a large shift; verify it isn't a recording change."))
    if not flags:
        flags.append(dict(sev="ok", text="Nothing unusual this period — volume and handling time track the 5-year norm."))
    return flags


def build_insights(year, event, cs, bs, vol_pct, mdelta, by_hour, by_weekday, by_nbhd, by_type,
                   unknown, wlabel, partial, heat, by_equipment, avg_units, movers, eh_cur, eh_pct):
    label = "All incidents" if event == "ALL" else event.title()
    out = {}
    if cs["n"] == 0:
        return {"kpi": "No incidents match this selection in the chosen window."}
    out["kpi"] = _kpi_text(label, year, cs, bs, vol_pct, mdelta, wlabel, partial)
    out["dist"] = (f"Half of {label.lower()} events close within {cs['median']:.0f} min; the slowest "
                   f"10% run past {cs['p90']:.0f} min. Figures are handling time, not response time.")
    peak = max(by_hour, key=lambda x: x["current"])
    out["hour"] = (f"Demand peaks around {peak['hour']:02d}:00 ({peak['current']} events). "
                   f"Bars are this period; the line is the 5-year average for the same window.")
    pw = max(by_weekday, key=lambda x: x["current"])
    out["weekday"] = f"{pw['weekday']} is the busiest day in this window ({pw['current']} events)."
    if by_nbhd:
        unk = "included" if unknown == "include" else "excluded"
        out["nbhd"] = (f"{by_nbhd[0]['name']} leads with {by_nbhd[0]['count']} events "
                       f"(median {by_nbhd[0]['median']:.0f} min). UNKNOWN events are {unk}.")
    mx, mw, mh = 0, 0, 0
    for w in range(7):
        for h in range(24):
            if heat[w][h] > mx:
                mx, mw, mh = heat[w][h], w, h
    out["heat"] = (f"The single busiest cell is {WEEKDAYS[mw]} {mh:02d}:00 ({mx} events). "
                   f"Darker = more events; each cell is one weekday-hour combination.")
    if by_equipment:
        te = by_equipment[0]
        out["equipment"] = (f"{te['type']} units dominate: {te['current']:,} dispatched this window "
                            f"vs a 5-yr average of {te['baseline']:,}. Average {avg_units} units per "
                            f"event. Counts are unit TYPES listed on dispatch, not identified "
                            f"apparatus or crew-hours.")
    if movers:
        m0 = movers[0]
        out["movers"] = (f"Biggest shift: {m0['event']} in {m0['nbhd']} — {m0['n']} events vs an "
                         f"expected ~{m0['expected']}/yr ({'+' if m0['pct'] >= 0 else ''}{m0['pct']}%). "
                         f"Cells shown need n >= 15 and an expected baseline >= 8/yr.")
    else:
        scope = "event-type / neighbourhood cell" if event == "ALL" else f"{event.title()} neighbourhood"
        out["movers"] = (f"No {scope} diverges >=25% from its own norm in this window "
                         "(cells need n >= 15 and an expected baseline >= 8/yr).")
    eh_txt = (f" ({'+' if eh_pct >= 0 else ''}{eh_pct}% vs the 5-yr norm)" if eh_pct is not None else "")
    out["hours"] = (f"Events were open for a combined {eh_cur:,} hours this window{eh_txt}. "
                    f"This is dispatch->close time, not crew-hours or apparatus utilisation.")
    changed = []
    if vol_pct is not None and abs(vol_pct) >= 5:
        changed.append(f"volume is {'up' if vol_pct > 0 else 'down'} {abs(vol_pct):.0f}% on the norm")
    if mdelta is not None and abs(mdelta) >= 2:
        changed.append(f"median handling time {'rose' if mdelta > 0 else 'fell'} {abs(mdelta):.0f} min")
    out["what_changed"] = ("What changed: " + "; ".join(changed) + "." if changed else
                           "What changed: nothing material - volume and handling time track the norm.")
    return out


# ---------------- forecast ----------------
def monthly_series(event):
    m = DATA["monthly"]
    return m[m["desc"] == event].set_index(["year", "month"])["n"]


def forecast_volume(event, horizon=6):
    s = monthly_series(event)
    if s.empty:
        return None
    latest = DATA["latest"]; cm = DATA["max_month"]
    hist_years = [y for y in range(latest - 5, latest)]
    seas_mean, seas_std = {}, {}
    for mo in range(1, 13):
        vals = [float(s.get((y, mo), 0.0)) for y in hist_years]
        seas_mean[mo] = float(np.mean(vals)) if vals else 0.0
        seas_std[mo] = float(np.std(vals)) if len(vals) > 1 else seas_mean[mo] * 0.15
    complete = range(1, cm)
    cur_actual = sum(float(s.get((latest, mo), 0.0)) for mo in complete)
    cur_expect = sum(seas_mean.get(mo, 0.0) for mo in complete)
    level = (cur_actual / cur_expect) if cur_expect > 0 else 1.0
    # F3: the current month is partial (data ends mid-month), so plotting it as a full
    # "actual" bar reads as a demand collapse. Stop the actual line at the last COMPLETE
    # month and hand the partial month back separately, flagged, for a distinct marker.
    cut_m, cut_d = DATA["cutoff"]
    partial_month = cut_d < MONTH_DAYS[cut_m - 1]
    end_mo = (cm - 1) if partial_month else cm
    actual, ym = [], []
    for y in range(latest - 2, latest + 1):
        for mo in range(1, 13):
            if y == latest and mo > end_mo:
                break
            actual.append(int(s.get((y, mo), 0))); ym.append((y, mo))
    partial = None
    if partial_month and cm >= 1:
        partial = dict(label=f"{MONTHS[cm]} {latest % 100:02d}",
                       value=int(s.get((latest, cm), 0)),
                       note=(f"{MONTHS[cm]} {latest} is month-to-date (to the {cut_d}th) — a "
                             "partial month, shown as a separate hollow point and excluded "
                             "from the trend and level."))
    fc = []; yy, mm = latest, cm
    for _ in range(horizon):
        mm += 1
        if mm > 12:
            mm = 1; yy += 1
        mean = seas_mean.get(mm, 0.0) * level
        sd = seas_std.get(mm, 0.0) * max(level, 1.0)
        fc.append(dict(year=yy, month=mm, label=f"{MONTHS[mm]} {yy}", mean=round(mean),
                       lo=round(max(0.0, mean - 1.28 * sd)), hi=round(mean + 1.28 * sd)))
    return dict(actual=actual, actual_labels=[f"{MONTHS[m]} {y%100:02d}" for (y, m) in ym],
                forecast=fc, level=round(level, 3), cutoff_label=f"{MONTHS[cm]} {latest}",
                partial=partial)


def _forecast_payload(event, horizon):
    f = forecast_volume(event, horizon)
    if f is None:
        return None
    label = "all incidents" if event == "ALL" else event.title()
    total = sum(x["mean"] for x in f["forecast"])
    lo = sum(x["lo"] for x in f["forecast"]); hi = sum(x["hi"] for x in f["forecast"])
    med = DATA["dur_by_type"].get(event, DATA["dur_all"]) if event != "ALL" else DATA["dur_all"]
    wh = round(total * med / 60.0)
    trend = ("running above" if f["level"] > 1.05 else "running below" if f["level"] < 0.95 else "tracking")
    note = ""
    if abs(f["level"] - 1) >= 0.15:
        note = (f" Data check: completed-month volume differs from the norm by {abs(f['level']-1)*100:.0f}% "
                "- a shift this large may reflect a reporting change; verify before acting.")
    insight = (f"Projected {label} volume for the next {horizon} months is about {total:,} events "
               f"(range {lo:,}-{hi:,}, ~80% interval), {trend} the 5-year seasonal norm "
               f"(level x{f['level']:.2f}). At the historical median handling time ({med:.0f} min) that is "
               f"roughly {wh:,} event-hours. Projection is of volume only - not response time, not causal." + note
               + (" " + f["partial"]["note"] if f.get("partial") else ""))
    level_pct = round((f["level"] - 1) * 100)
    rec = (f"Budget for ~{total:,} {label} events / {wh:,} event-hours over the next {horizon} months; "
           f"size to the upper bound ({hi:,}) if overflow can't be absorbed.")
    if note:
        rec += " But verify the volume shift first — it may be a recording change, not real demand."
    return dict(event=event, horizon=horizon, **f, total_next=total, lo_next=lo,
                hi_next=hi, workload_hours=wh, level_pct=level_pct, data_flag=bool(note),
                rec=rec, insight=insight)


@app.route("/api/forecast")
def forecast():
    event = request.args.get("event", "ALL").upper()
    horizon = max(1, min(12, _int_arg("horizon", 6)))
    p = _forecast_payload(event, horizon)
    if p is None:
        return jsonify(dict(error="no data"))
    return jsonify(p)


# ---------------- geospatial ----------------
@app.route("/api/geo")
def geo():
    """Per-neighbourhood hotspots: volume, median handling time, and divergence from the
    5-year norm for the SAME window, with map coordinates. Spatial early-warning."""
    year = _year_arg()
    event = request.args.get("event", "ALL").upper()
    unknown = request.args.get("unknown", "exclude")
    m1, d1, m2, d2, h1, h2 = _window_args(year)
    df = DATA["df"]
    wmask = _window_mask(df, m1, d1, m2, d2, h1, h2)
    cur = _slice(year, event, wmask=wmask)
    by = _base_years(year); nby = len(by)
    base = df[wmask & df["year"].isin(by)]
    if event != "ALL":
        base = base[base["desc"] == event]
    if unknown != "include":
        cur = cur[cur["nbhd"] != "UNKNOWN"]; base = base[base["nbhd"] != "UNKNOWN"]
    cg = cur.groupby("nbhd").agg(count=("dur", "size"), median=("dur", "median"))
    bg = base.groupby("nbhd").size()
    pts = []
    for nb, r in cg.iterrows():
        c = DATA["centroids"].get(nb)
        if not c:
            continue
        exp = (bg.get(nb, 0) / nby) if nby else None
        pct = (round(100 * (r["count"] - exp) / exp) if exp and exp >= 3 else None)
        tier = ("above" if pct is not None and pct >= 25 else
                "below" if pct is not None and pct <= -25 else "normal")
        pts.append(dict(nbhd=nb.title(), lat=c[0], lon=c[1], count=int(r["count"]),
                        median=round(float(r["median"]), 1),
                        expected=(round(exp) if exp else None), pct=pct, tier=tier))
    pts.sort(key=lambda x: x["count"], reverse=True)
    above = [p for p in pts if p["tier"] == "above"]
    note = (f"{len(above)} neighbourhood(s) running >=25% above the {by[0]}-{by[-1]} norm for this window. "
            f"Shading = divergence vs each area's own norm. Spatial early-warning; the lead decides any action."
            if nby else "No 5-year baseline for this period.")
    return jsonify(dict(year=year, event=event, points=pts, above=len(above), note=note,
                        center=[53.5444, -113.4909]))


# ---------------- live refresh ----------------
@app.route("/api/refresh", methods=["POST"])
def refresh():
    """Incremental pull from the live SODA dataset (city updates it daily). Applies the
    SAME fixed cleaning rules, then recomputes all derived data. Never real-time."""
    try:
        q = urllib.parse.urlencode({"$where": f"dispatch_datetime > '{DATA['max_iso']}'",
                                    "$order": "dispatch_datetime", "$limit": 50000})
        with urllib.request.urlopen(SODA_URL + "?" + q, timeout=45) as r:
            rows = json.loads(r.read().decode())
    except Exception as e:
        return jsonify(dict(ok=False, error="Live source unreachable: " + str(e)[:150])), 502
    if not rows:
        return jsonify(dict(ok=True, added=0, data_current_to=DATA["current_label"],
                            window_label=DATA["window_label"], note="Already up to date."))
    raw = pd.DataFrame(rows)
    for c in ["dispatch_datetime", "event_duration_mins", "event_description",
              "neighbourhood_name", "latitude", "longitude", "equipment_assigned"]:
        if c not in raw.columns:
            raw[c] = ""
    raw = raw.fillna("")
    n_fetched = len(raw)
    raw = raw[~raw["event_description"].map(_is_non_incident)]
    dt = pd.to_datetime(raw["dispatch_datetime"], errors="coerce")
    raw = raw[dt.notna()].copy(); dt = dt[dt.notna()]
    dur = pd.to_numeric(raw["event_duration_mins"], errors="coerce")
    keep = dur.notna() & (dur > 0)
    raw = raw[keep].copy(); dt = dt[keep]; dur = dur[keep]
    if len(raw) == 0:
        return jsonify(dict(ok=True, added=0, data_current_to=DATA["current_label"],
                            window_label=DATA["window_label"],
                            note=f"Fetched {n_fetched} rows; none were valid incidents."))
    new = _features(raw, dt, dur, DATA["eq_types"])
    # extend centroids for any new neighbourhood
    lat = pd.to_numeric(raw["latitude"], errors="coerce")
    lon = pd.to_numeric(raw["longitude"], errors="coerce")
    ok = lat.between(53.2, 53.9) & lon.between(-113.9, -113.1)
    for nb, grp in pd.DataFrame({"nbhd": new["nbhd"][ok], "la": lat[ok], "lo": lon[ok]}).groupby("nbhd"):
        if nb not in DATA["centroids"]:
            DATA["centroids"][nb] = (round(float(grp["la"].mean()), 5),
                                     round(float(grp["lo"].mean()), 5))
    DATA["max_iso"] = dt.max().strftime("%Y-%m-%dT%H:%M:%S")
    _derive(pd.concat([DATA["df"], new], ignore_index=True))
    try:
        pd.to_pickle(dict(df=DATA["df"], centroids=DATA["centroids"], eq_types=DATA["eq_types"],
                          n_raw=DATA["n_raw"] + n_fetched, max_iso=DATA["max_iso"]), CACHE_PATH)
        DATA["n_raw"] += n_fetched
    except Exception as e:
        print("[EFRS] cache write skipped:", e)
    _log("refresh_log.csv", f"fetched {n_fetched} / added {len(new)} valid incidents; "
                            f"now current to {DATA['current_label']}")
    return jsonify(dict(ok=True, added=int(len(new)), data_current_to=DATA["current_label"],
                        window_label=DATA["window_label"], latest=DATA["latest"],
                        cutoff=list(DATA["cutoff"])))


# ---------------- chatbot: decision support ----------------
def parse_event(q):
    ql = q.upper()
    # longest match wins so "VEHICLE FIRE" isn't swallowed by the substring "FIRE"
    hits = [e for e in DATA["event_types"] if e in ql]
    if hits:
        return max(hits, key=len)
    for a, e in {"MVI": "MOTOR VEHICLE INCIDENT", "CAR": "MOTOR VEHICLE INCIDENT",
                 "CRASH": "MOTOR VEHICLE INCIDENT", "ALARM": "ALARMS"}.items():
        if a in ql and e in DATA["event_types"]:
            return e
    return "ALL"


def parse_year(q):
    yrs = [int(x) for x in re.findall(r"20\d\d", q) if int(x) in DATA["years"]]
    return yrs[0] if yrs else DATA["latest"]


def parse_nbhd(q):
    ql = q.upper()
    hits = [nb for nb in DATA["centroids"].keys() if nb != "UNKNOWN" and nb in ql and len(nb) >= 4]
    return max(hits, key=len) if hits else None


def phrase_answer(question, grounded_answer, editorial=False, scope=None):
    """Optional Gemini layer over an ALREADY-CORRECT deterministic answer. In the default
    mode it rephrases the draft conversationally; in `editorial` mode it writes a short
    reading that leads with the most notable signal in the supplied facts. In BOTH modes
    Gemini never sees the dataset and is told to preserve every number verbatim, never add
    a figure, never use response/arrival-time language, and make no causal claim — so it
    cannot fabricate a number or break a project guardrail. Returns None on any failure
    (caller decides the fallback). The refusal gate has already run in code before this.

    `scope` (default mode only): a plain-English description of exactly what the draft
    covers (e.g. "a 6-month forecast for Motor Vehicle Incident"). Gemini cross-checks it
    against the question and, on a CLEAR mismatch the parser missed (wrong horizon / event
    / area / year), says so and asks the user to rephrase instead of presenting a figure
    that doesn't answer what was asked. It never invents the corrected number."""
    if not GEMINI_ENABLED:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    if editorial:
        system = (
            "You are a fire-service data analyst writing a brief editorial reading of the current "
            "dashboard view for an operations lead. STRICT RULES: (1) Use ONLY the facts in the "
            "brief below — never add, compute, or estimate a number that is not there. (2) Keep "
            "every number, unit, and N exactly as written. (3) Lead with the single MOST notable "
            "signal (the largest deviation from the 5-year norm); mention one or two others if "
            "useful. (4) Never call anything a 'response time', 'arrival time', or 'turnout' — this "
            "is dispatch->close handling time only. (5) Make NO causal claim (no 'because ...'); "
            "describe what the numbers show, not why. (6) End by noting the staffing/resourcing "
            "decision belongs to the lead. (7) A four-digit value after 'in' (e.g. 'in 2026') is "
            "the YEAR/period, NEVER a count of incidents — the only incident count is the value "
            "labelled 'n = ... incidents'. Write 2-4 sentences, no preamble, no headings.")
        user = f"User question:\n{question}\n\nData brief (all figures already computed):\n{grounded_answer}"
    else:
        check = ""
        if scope:
            check = (" (7) CONSISTENCY CHECK: the draft was computed for exactly this scope: "
                     f"\"{scope}\". Compare it to the user's question. If the user CLEARLY asked for "
                     "a different horizon (number of months), event type, neighbourhood, or year "
                     "than the scope states, do NOT present the draft as their answer — instead say "
                     "plainly that the tool computed " + f"\"{scope}\"" + ", which does not match what "
                     "they asked, and ask them to restate the exact months / type / area / year. "
                     "Never invent the corrected figure. Apply this ONLY for a clear, material "
                     "mismatch; if the scope matches the question, ignore this rule entirely.")
        system = (
            "You rephrase a fire-service data assistant's answer to be clear and conversational. "
            "STRICT RULES: (1) Use ONLY the facts in the draft — never add, compute, or estimate a "
            "number that is not already there. (2) Keep every number, unit, and N exactly as written. "
            "(3) Never call anything a 'response time', 'arrival time', or 'turnout' — this data is "
            "dispatch->close handling time only. (4) Keep any note that the staffing/resourcing "
            "decision belongs to the lead. (5) A four-digit value after 'in' (e.g. 'in 2026') is the "
            "YEAR/period, NEVER a count of incidents — the only incident count is the value labelled "
            "'n = ... incidents'. (6) Respond with only the final answer — no preamble, no "
            "meta-commentary. Keep it to a short paragraph or two." + check)
        user = f"User question:\n{question}\n\nDraft answer (already correct — rephrase it):\n{grounded_answer}"
    try:
        # Vertex AI backend: auth via Application Default Credentials, not an API key.
        client = genai.Client(vertexai=True, project=GEMINI_PROJECT, location=GEMINI_LOCATION,
                              http_options=types.HttpOptions(timeout=12000))
        resp = client.models.generate_content(
            model=GEMINI_MODEL, contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system, max_output_tokens=600))
        text = (resp.text or "").strip()
        return text or None
    except Exception as e:
        print("[EFRS] Gemini phrasing skipped:", str(e)[:120])
        return None


def _digest(event, year, nbhd):
    """Assemble a ranked, plain-text facts brief for an editorial ('what's most notable?')
    answer over the default YTD window. Reuses build_flags — the same triage the Overview
    page shows — so the reading agrees with the dashboard. EVERY figure here is computed
    deterministically; the LLM (phrase_answer editorial=True) only turns it into prose."""
    df = DATA["df"]
    cm, cd = DATA["cutoff"]
    wmask = _window_mask(df, 1, 1, cm, cd, 0, 23)
    cur = _slice(year, event, nbhd, wmask=wmask)
    by = _base_years(year); nby = len(by)
    label = "All incidents" if event == "ALL" else event.title()
    scope = f" in {nbhd.title()}" if nbhd else ""
    base = df[wmask & df["year"].isin(by)]
    if event != "ALL":
        base = base[base["desc"] == event]
    if nbhd:
        base = base[base["nbhd"] == nbhd]
    cs = _stats(cur["dur"]); bs = _stats(base["dur"])
    if cs["n"] == 0:
        return (f"No {label.lower()} events{scope} match the current window "
                f"({DATA['window_label']}, {year}), so there is nothing to compare to a norm.")
    bvm = (len(base) / nby) if nby else 0
    vol_pct = (round(100 * (cs["n"] - bvm) / bvm, 1) if bvm else None)
    mdelta = (round(cs["median"] - bs["median"], 1)
              if cs["median"] is not None and bs["median"] is not None else None)
    partial = (year == DATA["latest"])
    lines = [_kpi_text(label + scope, year, cs, bs, vol_pct, mdelta, DATA["window_label"], partial)]
    cur_h = cur.groupby("hour").size(); base_h = base.groupby("hour").size()
    by_hour = [dict(hour=h, current=int(cur_h.get(h, 0)),
                    baseline=(float(base_h.get(h, 0)) / nby if nby else 0)) for h in range(24)]
    # build_flags gives the ranked "what's unusual vs the 5-year norm" list (or an honest
    # "no baseline"/"nothing unusual"), matching the Overview triage.
    for fl in build_flags(event, cs, vol_pct, mdelta, by_hour, cur, base, nby):
        lines.append("- " + fl["text"])
    # citywide top mover only for the unfiltered view (build_movers scans all types/areas)
    if event == "ALL" and not nbhd:
        mv = build_movers(year, wmask, "exclude")
        if mv:
            t = mv[0]
            lines.append(f"- Biggest event×area shift: {t['event']} in {t['nbhd']} "
                         f"{'+' if t['pct'] >= 0 else ''}{t['pct']}% vs its own 5-yr norm "
                         f"(n = {t['n']}, expected ~{t['expected']}).")
    return "\n".join(lines)


# ---- open-ended-but-computable questions: LLM plans a query, CODE runs it ----
# The LLM never computes a number; it only fills a WHITELISTED query schema, which
# run_query() then executes against the same cleaned rows with the same labels/guardrails.
# Anything the schema can't express (response/arrival/turnout time, station performance,
# causal "why", per-incident/address detail, forecasts, open-ended summaries) is marked
# not-answerable and falls through to the existing branches. Truth stays in code.
WD_SETS = {"weekend": [5, 6], "weekday": [0, 1, 2, 3, 4]}


def plan_query(q):
    """Ask Gemini to translate the question into a structured query (fields only, no
    computation). Returns a dict or None (offline / SDK missing / parse error)."""
    if not GEMINI_ENABLED:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    events = ["ALL"] + list(DATA["event_types"])
    system = (
        "You convert a fire-service data question into a STRUCTURED QUERY over a cleaned "
        "incident dataset. You NEVER compute or answer — you ONLY fill fields; separate code "
        "runs the query. Output ONLY a JSON object with these keys: "
        "answerable (bool), event (string), nbhd (string or null), compare_nbhd (string or null), "
        "weekday ('all'|'weekday'|'weekend'), h1 (int 0-23), h2 (int 0-23), year (int or null), "
        "metric ('median'|'p90'|'count'|'eventhours'|'volume'), "
        "groupby (null|'hour'|'weekday'|'nbhd'|'event'|'month'), reason (string). "
        f"event MUST be exactly one of {events} (map synonyms: car crash/collision -> "
        "MOTOR VEHICLE INCIDENT, fire alarm -> ALARMS, ems -> MEDICAL). If the question names an "
        "incident type (fire, medical, alarm, MVI/collision, rescue, hazmat, outside/vehicle "
        "fire), set event to that type — NEVER default to ALL when a type is named. nbhd = an "
        "Edmonton neighbourhood name in UPPER CASE, or null. YEAR: use null for 'this year', "
        "'currently', 'so far', 'now', or when no year is stated (null means the latest year); "
        "set a specific 4-digit year ONLY if the user names one. metric meaning: median/p90 = "
        "handling time (dispatch->close); count = number of incidents; eventhours = committed "
        "event-hours; volume = count compared to the 5-yr norm. Defaults: h1=0, h2=23, "
        "weekday='all', year=null, groupby=null. Use groupby when the question asks which "
        "hour/day/area/type is highest or for a breakdown. Set answerable=false (and explain "
        "briefly in reason) when the "
        "question needs a RESPONSE / ARRIVAL / TURNOUT time, STATION-level performance, a CAUSE "
        "('why'), per-incident or address detail, a forecast/projection, an open-ended "
        "'what's notable' summary, or anything the fields above cannot express.")
    try:
        client = genai.Client(vertexai=True, project=GEMINI_PROJECT, location=GEMINI_LOCATION,
                              http_options=types.HttpOptions(timeout=12000))
        resp = client.models.generate_content(
            model=GEMINI_MODEL, contents=q,
            config=types.GenerateContentConfig(system_instruction=system,
                    response_mime_type="application/json", max_output_tokens=300))
        return json.loads(resp.text or "{}")
    except Exception as e:
        print("[EFRS] plan_query skipped:", str(e)[:120])
        return None


def _hr(h):
    return f"{h:02d}:00"


def run_query(plan):
    """Execute a whitelisted structured query. EVERY figure is computed here in code; returns
    a deterministic answer string (labelled handling time, with N and the 5-yr baseline where
    it applies) or None if the plan is missing / not answerable / empty."""
    if not plan or not plan.get("answerable"):
        return None
    df = DATA["df"]
    ev = str(plan.get("event") or "ALL").upper()
    if ev != "ALL" and ev not in DATA["event_types"]:
        ev = "ALL"
    year = plan.get("year")
    year = year if isinstance(year, int) and year in DATA["years"] else DATA["latest"]
    def _nb(v):
        return v.upper() if isinstance(v, str) and v.upper() in DATA["centroids"] \
            and v.upper() != "UNKNOWN" else None
    nb = _nb(plan.get("nbhd")); nb2 = _nb(plan.get("compare_nbhd"))
    try:
        h1 = max(0, min(23, int(plan.get("h1", 0)))); h2 = max(0, min(23, int(plan.get("h2", 23))))
    except Exception:
        h1, h2 = 0, 23
    if h1 > h2:
        h1, h2 = 0, 23
    wd = plan.get("weekday", "all"); wd = wd if wd in WD_SETS else "all"
    metric = plan.get("metric", "median")
    if metric not in ("median", "p90", "count", "eventhours", "volume"):
        metric = "median"
    groupby = plan.get("groupby")
    if groupby not in ("hour", "weekday", "nbhd", "event", "month"):
        groupby = None
    cm, cd = DATA["cutoff"]
    wmask = _window_mask(df, 1, 1, cm, cd, h1, h2)
    by = _base_years(year); nby = len(by)

    def filt(frame, area):
        s = frame
        if ev != "ALL":
            s = s[s["desc"] == ev]
        if area:
            s = s[s["nbhd"] == area]
        if wd in WD_SETS:
            s = s[s["weekday"].isin(WD_SETS[wd])]
        return s

    ev_label = "all incidents" if ev == "ALL" else ev.title()
    quals = []
    if wd in WD_SETS:
        quals.append("on " + ("weekends" if wd == "weekend" else "weekdays"))
    if (h1, h2) != (0, 23):
        quals.append(f"during {_hr(h1)}-{_hr(h2)}")
    qual = (" " + ", ".join(quals)) if quals else ""
    area_txt = (" in " + nb.title()) if nb else ""
    scope_txt = f"{ev_label}{area_txt}{qual}, {year} year-to-date"
    HT = " Figures are handling time (dispatch→close), not response time."

    # two-neighbourhood comparison
    if nb2:
        parts = []
        for area in (nb, nb2):
            st = _stats(filt(df[wmask & (df["year"] == year)], area)["dur"])
            parts.append(f"{(area or 'citywide').title()}: n = {st['n']:,}" +
                         (f", median {st['median']:.0f} min" if st['median'] is not None else ""))
        return f"{ev_label.title()}{qual}, {year} year-to-date — " + "; ".join(parts) + "." + HT

    cur = filt(df[wmask & (df["year"] == year)], nb)
    base = filt(df[wmask & df["year"].isin(by)], nb)
    if len(cur) == 0:
        return f"No {ev_label} events match {scope_txt}."

    # grouped breakdown ("which weekday/hour/area/type is highest")
    if groupby:
        col = {"hour": "hour", "weekday": "weekday", "nbhd": "nbhd",
               "event": "desc", "month": "month"}[groupby]
        if metric in ("median", "p90"):
            qt = 0.5 if metric == "median" else 0.9
            agg = cur.groupby(col)["dur"].quantile(qt); unit = "min"
        else:
            agg = cur.groupby(col).size(); unit = "events"
        agg = agg.sort_values(ascending=False)

        def lbl(k):
            if col == "weekday":
                return WEEKDAYS[int(k)]
            if col == "hour":
                return _hr(int(k))
            if col == "month":
                return MONTHS[int(k)]
            return str(k).title()
        body = ", ".join(f"{lbl(k)} ({v:,.0f} {unit})" for k, v in agg.head(5).items())
        mword = {"median": "median handling time", "p90": "p90 handling time",
                 "count": "volume", "volume": "volume", "eventhours": "volume"}[metric]
        return (f"{scope_txt} by {groupby} — {mword}, highest first: {body} "
                f"(total n = {len(cur):,}).{HT if metric in ('median', 'p90') else ''}")

    cs = _stats(cur["dur"]); bs = _stats(base["dur"])
    if metric == "median":
        bt = (f" vs a 5-yr median of {bs['median']:.0f} min" if bs['median'] is not None
              else " (no 5-yr baseline for this period)")
        return (f"Median handling time (dispatch→close) for {scope_txt} is {cs['median']:.0f} min "
                f"(p90 {cs['p90']:.0f}), n = {cs['n']:,} incidents{bt}.")
    if metric == "p90":
        bt = f" vs a 5-yr p90 of {bs['p90']:.0f} min" if bs['p90'] is not None else ""
        return (f"The slowest 10% of {scope_txt} run past {cs['p90']:.0f} min "
                f"(median {cs['median']:.0f}), n = {cs['n']:,} incidents{bt}.{HT}")
    bvm = (len(base) / nby) if nby else 0
    if metric == "count":
        vp = round(100 * (cs['n'] - bvm) / bvm) if bvm else None
        vt = (f", {abs(vp)}% {'above' if vp >= 0 else 'below'} the 5-yr norm" if vp is not None else "")
        return f"{cs['n']:,} {ev_label} incidents{area_txt}{qual} in {year} year-to-date{vt}."
    if metric == "eventhours":
        eh = round(cur['dur'].sum() / 60)
        ehb = round(base['dur'].sum() / 60 / nby) if nby and len(base) else None
        bt = f" vs a 5-yr norm of ~{ehb:,} h/yr" if ehb else ""
        return (f"{ev_label.title()}{area_txt}{qual} committed {eh:,} event-hours in {year} "
                f"year-to-date{bt} (dispatch→close time, not crew-hours).")
    if metric == "volume":
        vp = round(100 * (cs['n'] - bvm) / bvm, 1) if bvm else None
        if vp is None:
            return f"{cs['n']:,} {ev_label} incidents{area_txt}{qual} in {year} year-to-date (no 5-yr baseline to compare)."
        return (f"{ev_label.title()}{area_txt}{qual} volume is {'+' if vp >= 0 else ''}{vp}% vs the "
                f"5-yr norm ({cs['n']:,} vs ~{bvm:.0f}/yr) in {year} year-to-date.")
    return None


@app.route("/api/ask", methods=["POST"])
def ask():
    body = request.json or {}
    # accept either {"q": ...} (frontend) or {"question": ...} (documented shape) so the
    # refusal gate and logging can never be bypassed by using the other key (F7).
    q = (body.get("q") or body.get("question") or "").strip()
    if not q:
        return jsonify(dict(answer="Ask about volume, handling time, the forecast, or a "
                                   "resourcing question like 'when is downtown busiest for fire?'"))
    # F5: refuse response/arrival-time AND station-performance asks, and log every one.
    if FORBIDDEN.search(q) or (STATION.search(q) and not STATION_OK.search(q)):
        _log("refusal_log.csv", q.replace('"', "'"))
        return jsonify(dict(refused=True, answer=(
            "I can't answer that from this dataset. It records dispatch->close handling time only "
            "- no arrival/call-received timestamp and no station field - so response time, "
            "time-to-arrival, and station-level performance cannot be measured. (Logged.) I can "
            "show handling time, volume vs the norm, the forecast, and where/when demand concentrates.")))

    event = parse_event(q); year = parse_year(q); nbhd = parse_nbhd(q)
    label = "all incidents" if event == "ALL" else event.title()
    area = nbhd.title() if nbhd else None
    wants_fc = bool(re.search(r"\b(forecast|predict|project|next|coming|expect|future)\b", q, re.I))
    # horizon from the question ("next 4 months", "3-month outlook"); default 6, clamp 1-12.
    # keep the raw requested value so an out-of-range ask (e.g. 18) is flagged, not silently
    # answered as 12.
    fc_horizon = 6; fc_requested = None
    _WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
    _mh = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
                    r"\s*[-\s]?months?\b", q, re.I)
    if _mh:
        tok = _mh.group(1).lower()
        fc_requested = int(tok) if tok.isdigit() else _WORDNUM[tok]
        fc_horizon = max(1, min(12, fc_requested))
    elif re.search(r"\b(next|this|a|the|coming|upcoming|following)\s+month\b", q, re.I):
        fc_requested = 1; fc_horizon = 1              # "next month" (singular, no number)
    elif re.search(r"\bquarter\b", q, re.I):
        fc_requested = 3; fc_horizon = 3
    elif re.search(r"\b(next|coming|upcoming|following|a|one)\s+year\b|\bannual\w*|\byearly\b", q, re.I):
        fc_requested = 12; fc_horizon = 12            # "next year" -> 12 months
    resourcing = bool(RESOURCING.search(q))
    editorial = bool(EDITORIAL.search(q))

    # On-topic gate (before any metric is computed): if the question carries no concrete
    # data signal, redirect instead of falling through to the default KPI dump. Without
    # this, "what is the meaning of life" returns a stray year-to-date figure as an answer.
    # A matched event type or neighbourhood, or a forecast/resourcing/editorial intent,
    # always counts as on-topic. (Vague-but-on-topic asks route to the editorial branch.)
    on_topic = (event != "ALL" or nbhd is not None or wants_fc or resourcing or editorial
                or bool(ON_TOPIC.search(q)))
    if not on_topic:
        return jsonify(dict(intent="offtopic", answer=(
            "I can only answer questions about EFRS incident volume, handling time "
            "(dispatch→close), workload, and where/when demand concentrates — not general "
            "questions. Try: \"how many fire incidents this year vs the norm?\", \"when is "
            "Downtown busiest for fires?\", \"what's the 6-month volume forecast?\", or "
            "\"what stands out in the data this year?\"")))

    # Editorial / open-ended reading ("what's most notable?", "summarise this"). Facts are
    # assembled deterministically by _digest; the LLM only writes the prose. Per the chosen
    # design this REQUIRES the Gemini layer — with it off (or on any failure) we say so and
    # steer to the exact queries that work offline, rather than hand-rolling a summary.
    if editorial:
        if not GEMINI_ENABLED:
            return jsonify(dict(intent="editorial", answer=(
                "Summary / \"what's most notable\" answers use the AI phrasing layer, which "
                "isn't enabled right now. I can still answer specific questions directly — e.g. "
                "\"how many " + label + " this year vs the norm?\", \"when is Downtown busiest "
                "for fires?\", or \"what's the 6-month forecast?\"")))
        brief = _digest(event, year, nbhd)
        phrased = phrase_answer(q, brief, editorial=True)
        if not phrased:
            return jsonify(dict(intent="editorial", answer=(
                "The AI phrasing layer is temporarily unavailable, so I can't compose a summary "
                "right now. Ask a specific question — volume, handling time, a neighbourhood, or "
                "the forecast — and I'll answer it directly.")))
        return jsonify(dict(intent="editorial", phrased=True, event=event, year=year,
                            nbhd=nbhd, answer=phrased))

    # Query-planner: for computable-but-unmatched asks (a specific slice/metric the fixed
    # branches don't cover), let Gemini fill a whitelisted query and run it in CODE. Skipped
    # for resourcing (-> decision branch) and forecast (-> forecast branch) intents, and for
    # anything the plan marks not-answerable — those fall through unchanged. Numbers from code.
    if GEMINI_ENABLED and not resourcing and not wants_fc:
        det = run_query(plan_query(q))
        if det:
            return jsonify(dict(intent="query", phrased=True, answer=phrase_answer(q, det) or det))

    # decision-support answer for resourcing / where / when questions
    if resourcing or nbhd:
        cur = _slice(year, event, nbhd)
        if len(cur) == 0:
            return jsonify(dict(answer=f"No {label} events recorded for {area or 'that area'} in {year} YTD."))
        cs = _stats(cur["dur"])
        by = _base_years(year)
        cm, cd = DATA["cutoff"]
        wmask = _window_mask(DATA["df"], 1, 1, cm, cd, 0, 23)
        base = DATA["df"][wmask & DATA["df"]["year"].isin(by)]
        if event != "ALL":
            base = base[base["desc"] == event]
        if nbhd:
            base = base[base["nbhd"] == nbhd]
        exp = (len(base) / len(by)) if by else None
        vp = (round(100 * (cs["n"] - exp) / exp) if exp else None)
        days = DATA["days_default"]
        ph, conc, perday = peak_concurrency(cur, cs["median"] or DATA["dur_all"], days)
        wk = cur.groupby("weekday").size(); busiest = WEEKDAYS[int(wk.idxmax())] if len(wk) else "n/a"
        f = forecast_volume(event, 6); trend = "n/a"
        if f:
            trend = ("rising" if f["level"] > 1.05 else "easing" if f["level"] < 0.95 else "flat")
        where = f" in {area}" if area else ""
        # a thin slice makes hour/weekday peaks and the concurrency estimate noise, not signal
        small = cs["n"] < 100
        cph = None
        if small and event != "ALL":
            cw = _slice(year, event)
            if len(cw) >= 100:
                cph, _, _ = peak_concurrency(cw, float(cw["dur"].median()), days)
        vp_txt = (f"{abs(vp)}% {'above' if vp >= 0 else 'below'} the 5-year norm for this period"
                  if vp is not None else "no baseline available")
        overlap = (f"expect roughly {conc} incidents open at once in the peak hour"
                   if conc is not None and conc >= 0.05 else
                   "events rarely overlap — well under one open at a time even in the peak hour")
        ll = label.lower()
        # answer the question asked FIRST, then only the relevant context
        when_q = bool(re.search(r"\b(when|what\s*time|busiest|peak)\b", q, re.I))
        howmany_q = bool(re.search(r"\b(how\s*many|number\s*of|volume|count)\b", q, re.I))
        plan_q = bool(re.search(r"\b(plan|staff\w*|crew\w*|resourc\w*|deploy\w*|prepare|"
                                r"allocate|schedul\w*|cover\w*|how\s*should)\b", q, re.I))
        lines = []
        if when_q and not plan_q:
            if small:
                lines.append(f"Too few {ll} events{where} this year (n = {cs['n']}) for a reliable "
                             f"peak — nominally {ph:02d}:00 and {busiest}s." +
                             (f" Citywide {ll} is the steadier guide: it peaks around {cph:02d}:00."
                              if cph is not None else ""))
            else:
                lines.append(f"{label}{where} is busiest around {ph:02d}:00, and {busiest} is the "
                             f"heaviest day ({year} YTD, n = {cs['n']:,}).")
            lines.append(f"Context: volume is {vp_txt}; {overlap} (median event "
                         f"{cs['median']:.0f} min, dispatch→close).")
        elif howmany_q and not plan_q:
            lines.append(f"{cs['n']:,} {ll} events{where} in {year} year-to-date — {vp_txt}.")
            if not small:
                lines.append(f"They concentrate around {ph:02d}:00 and on {busiest}s; median event "
                             f"{cs['median']:.0f} min (dispatch→close).")
        else:
            if small:
                lines.append(f"Short answer: {ll}{where} is a small slice ({cs['n']} events YTD, "
                             f"{vp_txt}) — too thin to roster around." +
                             (f" Align crews to the citywide {ll} pattern instead: peak around "
                              f"{cph:02d}:00, 6-month outlook {trend}." if cph is not None else
                              f" 6-month outlook (citywide {ll}): {trend}."))
                lines.append(f"Why: with {cs['n']} events the local peak (nominally {ph:02d}:00 / "
                             f"{busiest}s) is noise, and {overlap} (median {cs['median']:.0f} min, "
                             f"dispatch→close).")
            else:
                lines.append(f"Short answer: weight coverage toward {ph:02d}:00 and {busiest}s — "
                             f"that is when {ll}{where} demand concentrates "
                             f"({cs['n']:,} events YTD, {vp_txt}).")
                lines.append(f"Load: {overlap} ({perday}/day in that hour, median "
                             f"{cs['median']:.0f} min, dispatch→close). 6-month outlook "
                             f"(citywide {ll}): {trend}.")
            lines.append("The data shows demand, not crew counts (no unit-availability or station "
                         "info) — the staffing call is yours.")
        det = "\n".join(lines)
        dscope = f"{label}{(' in ' + area) if area else ''} for {year} year-to-date"
        return jsonify(dict(event=event, year=year, nbhd=nbhd, intent="decision",
                            phrased=GEMINI_ENABLED, answer=phrase_answer(q, det, scope=dscope) or det))

    if wants_fc:
        p = _forecast_payload(event, fc_horizon)
        if p:
            det = p["insight"]
            # deterministic guard for the out-of-range case the parser clamps
            if fc_requested and fc_requested != fc_horizon:
                det = (f"You asked for {fc_requested} months, but the forecast only supports a "
                       f"1-12 month horizon, so this covers the next {fc_horizon} months instead. "
                       + det)
            scope = f"a {fc_horizon}-month volume forecast for {label}"
            return jsonify(dict(intent="forecast", phrased=GEMINI_ENABLED,
                                answer=phrase_answer(q, det, scope=scope) or det))
    cur = _slice(year, event)
    by = _base_years(year); nby = len(by)
    cm, cd = DATA["cutoff"]
    wmask = _window_mask(DATA["df"], 1, 1, cm, cd, 0, 23)
    base = DATA["df"][wmask & DATA["df"]["year"].isin(by)]
    if event != "ALL":
        base = base[base["desc"] == event]
    cs = _stats(cur["dur"]); bs = _stats(base["dur"])
    bvm = (len(base) / nby) if nby else 0
    vol_pct = (round(100 * (cs["n"] - bvm) / bvm, 1) if bvm else None)
    mdelta = (round(cs["median"] - bs["median"], 1)
              if cs["median"] is not None and bs["median"] is not None else None)
    kpi = _kpi_text("All incidents" if event == "ALL" else event.title(), year, cs, bs,
                    vol_pct, mdelta, DATA["window_label"], year == DATA["latest"])
    mscope = f"{label} for {year} year-to-date (handling time and volume vs the 5-yr norm)"
    return jsonify(dict(intent="metric", phrased=GEMINI_ENABLED,
                        answer=phrase_answer(q, kpi, scope=mscope) or kpi))


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:p>")
def static_files(p):
    return send_from_directory(app.static_folder, p)


load_data()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, use_reloader=False)
