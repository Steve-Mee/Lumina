# Phase 5 first-cycle pre-registration (before seeing data)

- generated_at: `2026-10-28T20:35:18.925608+00:00`
- prefilter_n: `24`
- first_cycle_n: `12`
- holdout: last 9 months locked; never used for this selection

## Rationale

First P2 cycle is locked to 12 of the 24 pre-filter variants before any NT8 bar is read. Steve's data order is MES/MNQ 1m first, so each of the 12 registered economic families contributes its micro contract (MES or MNQ) rather than the ES/NQ duplicate. That keeps one economically distinct mechanism per family, stays inside the 10-15 band, and avoids doubling the trial count into full-size contracts before the micro tape is proven. Lookbacks, thresholds, and 16/8 tick geometry are the catalog values already justified in the economic rationale fields. Ranking used only those fields. No Sharpe, FAR, PBO, or bar statistic entered the choice. The 12 unused ES/NQ duplicates remain in the 24-variant pre-filter for a later cycle after the holdout is still untouched.

## Selected variants

| config_id | template | instrument | lookback | threshold | mode | target/stop |
|---|---|---|---|---|---|---|
| mr-mes-10-1.5 | mean_reversion | MES | 10 | 1.5 | fade | 16/8 |
| vi-mnq-10-0.55 | volume_imbalance | MNQ | 10 | 0.55 | fade | 16/8 |
| rm-mes-10-0.40 | regime_momentum | MES | 10 | 0.4 | follow | 16/8 |
| or-mes-5-bo | opening_range_breakout | MES | 5 | 0.0 | breakout | 16/8 |
| or-mnq-15-fade | opening_range_fade | MNQ | 15 | 0.0 | fade | 16/8 |
| gap-mes-8 | overnight_gap | MES | 1 | 8.0 | fade | 16/8 |
| vwap-mes-20-1.5 | vwap_distance | MES | 20 | 1.5 | fade | 16/8 |
| rc-mes-20-0.25 | range_compression | MES | 20 | 0.25 | breakout | 16/8 |
| cr-mes-3 | close_reversal | MES | 3 | 0.0 | fade | 16/8 |
| tod-mes-15 | time_of_day_inventory | MES | 15 | 0.0 | fade | 16/8 |
| pb-mnq-20 | trend_pullback | MNQ | 20 | 0.0 | follow | 16/8 |
| vx-mes-20 | volatility_expansion | MES | 20 | 0.25 | breakout | 16/8 |

## Deferred to a later cycle (still pre-filter, not discarded)

- `mr-es-20-1.5`
- `vi-nq-20-0.65`
- `rm-es-10-0.40`
- `or-es-5-bo`
- `or-nq-15-fade`
- `gap-es-4`
- `vwap-nq-40-2.0`
- `rc-es-20-0.25`
- `cr-nq-5`
- `tod-es-15`
- `pb-nq-20`
- `vx-es-20`
