# ADR-0019: Expectancy-Oriented RL Reward Shaping

## Status

Accepted (2026-06-27)

## Context

Birth and sim PPO training used a reward approximately equal to raw net PnL per step (`realized_pnl - costs - drawdown_penalty + sharpe_bonus`). This incentivizes win rate without distinguishing trade quality: a +$25 win and +$100 win at the same risk received proportional-to-size but not expectancy-aware shaping. Oracle pattern labels used a separate `clip(pnl/100)` formula, misaligned with rollout rewards.

## Decision

Introduce **`lumina_core/rl/reward_shaper.py`** as SSOT for training rewards in **`trade_mode in {"birth", "sim"}`**:

1. **R-multiple quality** — `net_pnl / risk_usd` with win-size bonus when profit exceeds rolling average loss.
2. **Loss asymmetry** — losses scaled by `loss_asymmetry_coeff` (>1).
3. **Volatility adjustment** — quality divided by `(1 + volatility_penalty_coeff * trend_atr_norm)`.
4. **Trend alignment bonus** — `trend_align_bonus_coeff * max(0, side * trend_regime_strength)`.
5. **Portfolio terms** — drawdown penalty and sharpe bonus (configurable).
6. **`trade_mode == "real"`** — unchanged legacy reward path (fail-closed safety).

Configuration via `BirthRewardConfig` in [`config.yaml`](../../config.yaml) under `birth_v2.reward`, mirrored on `RLConfig.reward`.

**Invariants preserved:**

- `info["rl_close_accounting_net_usd"]` remains raw close accounting (certificate/OOS metrics).
- `info["training_reward"]` is the shaped PPO signal.
- Expectancy shaping applies only on **trade close** steps in birth/sim; hold/entry steps reward `0` (except VAR/ES penalty on sim non-close steps).

## Consequences

- Positive: Policy learns +EV behavior (favor high R-multiple, trend-aligned entries).
- Positive: Oracle and rollout trajectories share the same reward SSOT.
- Negative: Reward distribution shift — PPO retrain required.
- Negative: Tuning sensitivity via `birth_v2.reward` coefficients.

## Related ADRs

- ADR-0012: Single simulator SSOT
- ADR-0018: RL observation trend features (trend_regime_strength input to alignment bonus)
