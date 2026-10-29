# P2 limited ES strategy-run — pre-registration (2026-10-29)

## GO addendum (2026-10-29 23:07)

Research team (NOT Steve) GO. Frozen answers
`docs/research/ONDERZOEKERS-ANTWOORDEN-LIMITEDGO-20261029T2307.md`
content sha256 `332003298fadfff06f28fced134d0a8c1a363933705d573cb3bd0407d4d9c414`
(prefix `33200329`).

This lock is executed in this change: ES only, the six `p2l-*` configs
including `p2l-tod-es`, no extra variants, no NQ, no promotion, no SIM,
holdout sealed, max trials = 6. Results:
`phase5_p2_limited_es.json` / `phase5_p2_limited_es_end_report_2026-10-29.md`.

The 22:08 body below is the parameter lock. Do not change lookbacks,
thresholds, or geometry after seeing results. Optional lower-hitrate /
no-lookahead plants are **not** in this run.

## Historical 22:08 lock (parameter freeze)

**Not executed at 22:08.** This file was the proposed lock for a later limited
strategy-run. The 22:08 task did not increment `TrialRegistry`, did not open
holdout, and did not propose promotion or SIM. Do not start this run from
the 22:08 power-floor task (superseded by the 23:07 GO above).

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md`
content sha256 `991138fdd4b741041e3288387dd8aaf89a09652329ada7eec7eaa0f037bfae9d`
(prefix `991138fd`). Prior 21:29 lock remains on file as
`docs/research/ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md`.

Team 22:08: power-only at 12.5% (optional 6.25%) first; then a limited ES
run of the pre-registered 6 (or 5) configs. Prefer drop/deprioritize
`p2l-tod-es` if high turnover / ETH exposure. No extra variants. NQ closed,
no promotion, no SIM, holdout sealed, max trials = pre-registered count.
**This file still does not start that run.**

Does **not** rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50, the 7/8 null gate,
holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

## Locked if the team OKs later

| field | lock |
|---|---|
| instruments | ES only; MES may be D13 control tape; **NQ closed** |
| families | fade / mean-reversion and breakout / momentum only |
| geometry | fade `1.0×ATR14 / 1.2×ATR14`; breakout `1.8×ATR14 / 0.9×ATR14` |
| holding | RTH session flatten, `time_stop_bars=2000` |
| n configs | 6 (inside the 6–8 cap; TOD kept, see below) |
| ids | new `p2l-*` (fresh trial; do not reuse killed `p2a-*` ids) |
| floors | DSR ≥ 0.95, PBO 0.50, A2 drempel unchanged |
| null | v2 `linear_magnitude`, 32 seeds `20261029+i`, fail at `n_edge ≥ 4/32` |
| positive control | must pass under fade 1.0/1.2 **and** breakout 1.8/0.9 |
| promotion | none |
| SIM / REAL | none |
| holdout | pin closed; no eval |

The four ATR DSR-only kills (`p2a-or-bo-es`, `p2a-rm-es`, `p2a-pb-es`,
`p2a-gap-es`) stay killed under those ids. They are **not** on this list.
Gap and pullback are out of the two allowed family buckets. High-turnover
`close_reversal` / `volume_imbalance` stay out.

## Proposed configs (not run)

| config_id | template | family bucket | mode | lookback | threshold | target/stop |
|---|---|---|---|---|---|---|
| `p2l-mr-es` | `mean_reversion` | fade / mean-reversion | fade | 60 | 1.5 | 1.0 / 1.2 |
| `p2l-or-fade-es` | `opening_range_fade` | fade / mean-reversion | fade | 30 | 0.0 | 1.0 / 1.2 |
| `p2l-vwap-es` | `vwap_distance` | fade / mean-reversion | fade | 60 | 1.5 | 1.0 / 1.2 |
| `p2l-tod-es` | `time_of_day_inventory` | fade / mean-reversion | fade | 30 | 0.0 | 1.0 / 1.2 |
| `p2l-rc-es` | `range_compression` | breakout / momentum | breakout | 60 | 0.25 | 1.8 / 0.9 |
| `p2l-vx-es` | `volatility_expansion` | breakout / momentum | breakout | 60 | 0.75 | 1.8 / 0.9 |

Six configs, three per bucket. Lookbacks/thresholds copy the existing ATR
catalog templates for those families; ids are new so this is a fresh trial
if later approved, not a silent rerun of `p2a-*`.

## TOD decision: keep `p2l-tod-es`

Checked from **existing** ATR ES PIT (`phase5_p2_atr_es_results.md` /
JSON), same fade `1.0/1.2` geometry and `session_filter=rth` that this
grid would reuse. No new strategy-run was used for this check.

| sibling (ATR ES) | n_trades / 598 sessions | trades/session | slippage $ |
|---|---|---|---|
| `p2a-mr-es` | 734 | 1.23 | 2.47e+04 |
| `p2a-vwap-es` | 729 | 1.22 | 2.35e+04 |
| `p2a-vx-es` | 732 | 1.22 | 2.38e+04 |
| `p2a-or-fade-es` | 695 | 1.16 | 1.67e+04 |
| `p2a-rc-es` | 682 | 1.14 | 1.94e+04 |
| `p2a-tod-es` | **589** | **0.98** | 1.93e+04 |

`p2a-tod-es` is the **lowest** trade count of the six families that map to
`p2l-*`. Not high turnover relative to this grid.

ETH: `_time_of_day` signals only on RTH bars in the first `lookback` minutes
after the RTH open (`lookback=30`). `session_filter=rth`. ATR exit mix is
473 session-end + 75 target + 41 stop (all RTH flatten). Residual ETH
slippage in CostModel 1.2.0 applies to ETH-session bars; this template does
not enter there. `overnight_gap` is the ETH-adjacent family and is already
excluded.

The 16/8 clipped `p2c-tod-es-15` row (2755 trades) is a different geometry
and is **not** this lock.

**Decision: keep `p2l-tod-es`. n configs stays 6. No extra variants. No
drop.** If a later start-OK disagrees, rewrite this lock before any run.

## Explicitly not in this file (22:08 lock; 23:07 executes the six)

- No NQ row
- No `p2a-or-bo-es` / `p2a-rm-es` revival
- 22:08: no execution. 23:07 GO: `--cycle limited-es` on the attached pre-holdout ES tape; holdout stays sealed
- No promotion candidate, no SIM whitelist change
- No extra variants; no parameter changes after seeing results
