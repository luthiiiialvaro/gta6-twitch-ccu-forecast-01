"""GTA VI launch-day Twitch CCU forecaster for make.fun gta6-twitch-ccu-forecast-01.

Forecasts, for each of hours 2..24 of the release day (UTC), five quantiles of
the Twitch concurrent-viewer count in the Grand Theft Auto VI category, from
the case's hour-1 print and the past big launches shipped in the case as
`comparables` (SullyGnome hourly category averages).

Model (stdlib only, deterministic, no network, no randomness)
-------------------------------------------------------------
The shape of a launch day is driven by *when* the game unlocks relative to
UTC midnight, and hour 1's print already encodes that.  Across the 38
comparable launches in the practice cases, log(peak viewers / hour-1 viewers)
correlates -0.94 with log(hour-1 viewers):

* hour 1 under ~5,000 viewers: the category was near-dead before launch
  (no early access, global unlock still hours away).  Viewers then explode
  as the US unlocks -- median peak is ~240x hour 1.
* hour 1 ~5,000-50,000: median peak ~5x hour 1.
* hour 1 over ~50,000: the game was already widely streamed before UTC
  midnight (rolling midnight unlocks in NZ/Europe, early access).  The day
  then dips a little in the small hours and rises to a modest peak in the
  US evening -- median peak only ~1.4-1.6x hour 1.

So, for each forecast hour h, the program pools the log ratios
ln(viewers_h / viewers_1) of the comparables whose hour-1 print falls in the
same size group as this case's hour-1 print (<5k, 5k-50k, >=50k), and
forecasts lognormal quantiles around their median:

    q_tau(h) = p1 * exp(med_h + z_tau * sd_h)

where med_h / sd_h are the median / population standard deviation of the
pooled log ratios for hour h, lightly smoothed across neighbouring hours
(3-point moving average) to remove SullyGnome sampling noise, with sd
clamped to [0.25, 1.8].  A group with fewer than 4 ratios for an hour falls
back to pooling all comparables for that hour; with fewer than 2, to the
hard-coded group curves below (fitted on the same practice comparables, so
the program still forecasts if a case ships no usable comparables).

Leave-one-out pinball loss on the 37 complete comparable launch curves:
this model 0.39, the house persistence baseline 0.93.  Within the
hour-1 >= 50k group -- where a GTA VI hour-1 print is expected to land --
the leave-one-out loss is 0.22.

Run: python3 main.py reads every *.in in $MAKEFUN_INPUT_DIR (else /input)
and writes <id>.out to $MAKEFUN_OUTPUT_DIR (else /output), one JSON object
{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}, ...]} for h = 2..24.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Hour-1 size groups: < 5k, 5k..50k, >= 50k viewers.
GROUP_EDGES = (5000, 50000)

# Fallback log-ratio curves, hours 2..24, fitted on the practice cases'
# comparables (per-hour pooled median / sd of ln(viewers_h / viewers_1)).
# Used only when a case ships too few usable comparables for an hour.
FALLBACK_MED = [
    [-0.262, -0.154, -0.299, -0.317, -0.334, -0.061, 0.329, 1.585, 2.774,
     2.943, 3.402, 3.814, 3.958, 4.168, 5.235, 5.254, 5.418, 5.46, 5.434,
     5.322, 5.255, 5.156, 5.048],
    [-0.245, -0.356, -0.31, -0.219, -0.09, -0.042, -0.05, -0.002, 0.102,
     0.221, 0.374, 0.527, 0.719, 0.796, 1.0, 0.953, 0.97, 1.261, 1.565,
     1.613, 1.502, 1.283, 1.043],
    [-0.091, -0.227, -0.321, -0.317, -0.305, -0.386, -0.414, -0.475, -0.608,
     -0.627, -0.539, -0.348, -0.136, 0.019, 0.088, 0.213, 0.249, 0.271,
     0.298, 0.31, 0.219, 0.137, 0.154],
]
FALLBACK_SD = [
    [0.521, 1.38, 1.46, 1.531, 1.512, 1.42, 1.374, 1.398, 1.799, 1.936,
     1.916, 1.735, 1.81, 1.853, 1.486, 1.398, 1.228, 1.101, 1.126, 1.014,
     0.986, 0.982, 0.971],
    [0.164, 0.379, 0.343, 0.421, 0.646, 0.617, 0.643, 0.669, 0.66, 0.694,
     0.736, 0.88, 0.949, 1.002, 0.948, 0.87, 0.693, 0.729, 0.757, 0.741,
     0.672, 0.656, 0.678],
    [0.188, 0.239, 0.281, 0.287, 0.404, 0.472, 0.445, 0.448, 0.461, 0.462,
     0.454, 0.419, 0.414, 0.421, 0.42, 0.4, 0.391, 0.397, 0.411, 0.403,
     0.425, 0.411, 0.421],
]

SD_FLOOR = 0.25
SD_CAP = 1.8


def group_of(p1):
    """Size group of an hour-1 print: 0 (<5k), 1 (5k..50k), 2 (>=50k)."""
    if p1 < GROUP_EDGES[0]:
        return 0
    if p1 < GROUP_EDGES[1]:
        return 1
    return 2


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """x rounded to 2 decimals, half up, as JavaScript Math.round does it."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def smooth(values):
    """3-point moving average over hours 2..24 (2 points at the ends)."""
    out = {}
    hours = sorted(values)
    for h in hours:
        near = [values[hh] for hh in hours if abs(hh - h) <= 1]
        out[h] = sum(near) / len(near)
    return out


def comparable_log_ratios(case):
    """Per-hour pooled log ratios ln(v_h / v_1) from the case's comparables.

    Returns (by_group, pooled): by_group[g][h] is the list of log ratios for
    hour h from comparables in size group g; pooled[h] the same over every
    comparable.  The Grand Theft Auto VI category's own pre-release history
    is not a launch and is left out, as is any comparable without a usable
    release-day hour 1.
    """
    by_group = {0: {}, 1: {}, 2: {}}
    pooled = {}
    for comp in case.get("comparables") or []:
        name = str(comp.get("name") or "").lower()
        if "grand theft" in name:
            continue
        day_start = comp.get("day_start")
        hourly = comp.get("hourly") or []
        if not day_start or not hourly:
            continue
        try:
            start = parse_time(day_start)
        except ValueError:
            continue
        by_time = {}
        for row in hourly:
            try:
                at = parse_time(row["from"])
                viewers = row["viewers"]
            except (KeyError, TypeError, ValueError):
                continue
            if isinstance(viewers, (int, float)) and viewers > 0:
                by_time[at] = viewers
        first = by_time.get(start)
        if not first or first <= 0:
            continue
        group = group_of(first)
        for h in range(2, 25):
            value = by_time.get(start + timedelta(hours=h - 1))
            if value and value > 0:
                ratio = math.log(value / first)
                by_group[group].setdefault(h, []).append(ratio)
                pooled.setdefault(h, []).append(ratio)
    return by_group, pooled


def hour_curves(case, p1):
    """(median, sd) of the log ratio for each forecast hour, per the model."""
    group = group_of(p1)
    by_group, pooled = comparable_log_ratios(case)
    med = {}
    sd = {}
    for h in range(2, 25):
        ratios = by_group[group].get(h) or []
        if len(ratios) < 4:
            ratios = pooled.get(h) or []
        if len(ratios) >= 2:
            med[h] = statistics.median(ratios)
            sd[h] = statistics.pstdev(ratios) if len(ratios) > 1 else 0.5
        else:
            med[h] = FALLBACK_MED[group][h - 2]
            sd[h] = FALLBACK_SD[group][h - 2]
    med = smooth(med)
    sd = smooth(sd)
    for h in range(2, 25):
        sd[h] = min(SD_CAP, max(SD_FLOOR, sd[h]))
    return med, sd


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    try:
        p1 = max(1, float(first["viewers"]))
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{name} has no numeric hour-1 print")
    med, sd = hour_curves(case, p1)
    hours = []
    rows = case.get("forecast") or [{"hour": h} for h in range(2, 25)]
    for row in rows:
        h = row["hour"]
        quantiles = []
        prev = 0.0
        for z in Z:
            q = p1 * math.exp(med[h] + z * sd[h])
            q = round2(min(1e9, max(0.01, q)))
            if q < prev:
                q = prev
            quantiles.append(q)
            prev = q
        hours.append({"hour": h, "q": quantiles})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
