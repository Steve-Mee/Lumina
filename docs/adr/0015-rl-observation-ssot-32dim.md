# ADR-0015: RL Observation SSOT — 32-dim Canonical Environment

## Status

Accepted (2026-06-11)

## Context

Birth Phase v2 and PPO training used two incompatible `RLTradingEnvironment` implementations:

- **Canonical** (`lumina_core/rl/gym_environment.py`): 32 dimensions including bible slots and DNA hash embedding.
- **Meta-RL legacy** (`lumina_core/engine/rl/rl_trading_environment.py`): 23 dimensions with RuntimeContext live quotes.

Dual observation spaces caused policy shape mismatches and violated ADR-0012 single-simulator SSOT.

## Decision

1. **`lumina_core/rl/observation_builder.py`** is the SSOT for observation vector construction (32 dims).
2. **`lumina_core/rl/RLTradingEnvironment`** is the only supported training environment for birth, PPO, and Meta-RL nightly paths.
3. **`MetaRLTradingEnvironmentLegacy`** remains as deprecated alias only; new code must not import it.
4. Meta-RL `PPOTrainer` (`engine/rl/ppo_trainer.py`) builds canonical env with OHLC replay data from `RuntimeContext`.

## Consequences

- All observation-space tests assert `OBSERVATION_DIM == 32`.
- Policies trained on 23-dim Meta-RL env are invalid after this ADR; retrain required.
- `birth_policy_observation.py` delegates regime mapping to `observation_builder`.
