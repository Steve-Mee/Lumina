# ADR-0018: RL Observation Trend Features — 43-dim Extension

## Status

Accepted (2026-06-27)

## Context

Birth Phase PPO training used a 32-dim observation vector (ADR-0015) with a binary regime scalar at index 1 (`regime_val` mapped from `TREND_UP`/`NEUTRAL`). Tick enrichment in `tick_enricher.py` used a simple 20-bar return threshold, providing weak trend signal for policy learning.

The policy could not distinguish trend strength, persistence, multi-period momentum, or volatility context — limiting birth curriculum effectiveness.

## Decision

Extend the observation SSOT (`lumina_core/rl/observation_builder.py`) from **32 to 43 dimensions**:

1. **Replace index 1** — `regime_val` (binary) → `trend_regime_strength` (signed continuous `[-1, 1]`).
2. **Append indices 32–42** — 11 trend features computed during tick enrichment and read at observation build time.
3. **Shared module** — `lumina_core/rl/trend_features.py` holds ADX, ATR, OLS slope, persistence, and regime strength logic.
4. **Tick enrichment** — `enrich_ticks_for_sim()` writes all `trend_*` keys; string `regime` label derived from `trend_regime_strength` for bible/curriculum compatibility.

### Feature table

| Index | Tick key | Description | Normalization |
|-------|----------|-------------|---------------|
| 1 | `trend_regime_strength` | Continuous trend strength | Signed `[-1, 1]` from ADX + slope + persistence |
| 32 | `trend_adx_7` | ADX(7) | `/100` → `[0, 1]` |
| 33 | `trend_adx_14` | ADX(14) | `/100` |
| 34 | `trend_adx_21` | ADX(21) | `/100` |
| 35 | `trend_slope_5` | OLS slope, 5 bars | `(slope/mean_price)×1000`, clip `[-1, 1]` |
| 36 | `trend_slope_15` | OLS slope, 15 bars | Same |
| 37 | `trend_slope_30` | OLS slope, 30 bars | Same |
| 38 | `trend_slope_60` | OLS slope, 60 bars | Same |
| 39 | `trend_direction` | Price direction | `-1`, `0`, `+1` |
| 40 | `trend_duration_norm` | Trend persistence | Consecutive same-direction bars / 60 |
| 41 | `trend_atr_norm` | Volatility | `ATR(14) / price` |
| 42 | `trend_atr_ratio` | Volatility context | `ATR / mean(ATR, 60)` clipped to `[0, 3]/3` |

Indices 0 and 2–31 are unchanged from ADR-0015 (price, tape, dream, fib, macro, position, bible, DNA).

Warm-up: ticks with index `< 60` receive zero trend defaults; aligns with `RLTradingEnvironment.reset()` starting at `_idx = 60`.

## Consequences

- **Positive**: PPO receives rich trend context during birth SIM rollouts and oracle pattern mining.
- **Positive**: `regime_scalar()` retained for backward compatibility; non-enriched paths fall back to computed or scalar regime.
- **Negative**: Existing `lumina_ppo_policy.zip` trained on 32-dim observations is **invalid** — birth retrain required.
- **Negative**: Tick-only OHLC (high=low=close=last) yields approximate ADX/ATR vs true bar data.

## Related ADRs

- ADR-0015: RL observation SSOT (32-dim base layout; dim count superseded by this ADR)
- ADR-0012: Single simulator SSOT
- ADR-0017: Birth Research Oracle
