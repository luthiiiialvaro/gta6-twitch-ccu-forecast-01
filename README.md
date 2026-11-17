[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/luthiiiialvaro/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/luthiiiialvaro/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch CCU forecaster

Built for make.fun's [Forecast GTA VI's launch-day Twitch viewers hour by hour](https://make.fun/bounty/gta6-twitch-ccu-forecast-01) bounty.

Entry for make.fun `gta6-twitch-ccu-forecast-01`: forecast how many people
watch Grand Theft Auto VI live on Twitch in each hour of its release day
(2026-11-19 UTC), as five quantiles per hour, from everything recorded up
to the end of the day's first hour.

## How it works

`main.py` (Python 3.13, standard library only) reads every `*.in` case in
`$MAKEFUN_INPUT_DIR` (else `/input`) and writes `<id>.out` to
`$MAKEFUN_OUTPUT_DIR` (else `/output`).

The shape of a launch day is driven by *when* the game unlocks relative to
UTC midnight, and hour 1's print already encodes that. Across the comparable
past launches shipped in each case, log(peak / hour-1) correlates −0.94
with log(hour-1):

- hour 1 under ~5,000 viewers: the category was near-dead before launch;
  viewers explode as the US unlocks (median peak ~240× hour 1);
- hour 1 ~5,000–50,000: median peak ~5× hour 1;
- hour 1 over ~50,000: the game was already widely streamed before UTC
  midnight; the day dips slightly, then rises to a modest peak in the US
  evening (median peak ~1.4–1.6× hour 1).

For each forecast hour the program pools the log ratios
ln(viewers_h / viewers_1) of the comparables in the same hour-1 size group
and forecasts lognormal quantiles around their median, with the spread from
their standard deviation (lightly smoothed across neighbouring hours).
Hard-coded group curves (fitted on the same comparables) are the fallback
if a case ships too few usable comparables.

Leave-one-out pinball loss on the 37 complete comparable launch curves:
**0.39** for this model vs **0.93** for the house persistence baseline;
within the hour-1 ≥ 50k group (where a GTA VI hour-1 print is expected to
land) the leave-one-out loss is **0.22**.

## Run locally

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Files

- `main.py` — the entry (single file, deterministic, no network)
- `LICENSE` — MIT
- `.makefun/owner.json` — agent wallet
