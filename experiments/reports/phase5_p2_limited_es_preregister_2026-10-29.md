# P2 limited ES strategy-run — pre-registration only (2026-10-29 21:29)

**Not executed.** This file is the proposed lock for a later limited
strategy-run. It does not increment `TrialRegistry`. It does not open
holdout. It does not propose promotion or SIM.

Binding input (Steve forwarded; **not** Steve's opinion):
`docs/research/ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md`
content sha256 `af183d1d6a9f329942d84bf80854791d69b20cd4264a88ae3da1d9677116e757`.

Team 21:29: limited run only after passed_gate is explained and 50%/25%
power is reported; ES only; only pre-registered families fade/mean-reversion
and breakout/momentum; max 6–8 configs; NQ closed; no promotion; no SIM.
A new OK is still required to **start** this run, even though those control
steps passed.

Does **not** rewrite CostModel 1.2.0, DSR 0.95, PBO 0.50, the 7/8 null gate,
holdout pin `2026-01-28T23:00:00Z`, or Risk Core.

## Locked if the team OKs later

| field | lock |
|---|---|
| instruments | ES only; MES may be D13 control tape; **NQ closed** |
| families | fade / mean-reversion and breakout / momentum only |
| geometry | fade `1.0×ATR14 / 1.2×ATR14`; breakout `1.8×ATR14 / 0.9×ATR14` |
| holding | RTH session flatten, `time_stop_bars=2000` |
| n configs | 6 (inside the 6–8 cap) |
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

## Explicitly not in this file

- No NQ row
- No `p2a-or-bo-es` / `p2a-rm-es` revival
- No execution, no CLI cycle invocation, no holdout unseal
- No promotion candidate, no SIM whitelist change
