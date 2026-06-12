# ADR-0012: Birth Phase v2 — Single Simulator SSOT

**Status**: Accepted

**Date**: 2026-06-11

## Context

Birth Phase v1 used a custom tick loop in `LuminaBirthEngine` with simplified PnL physics (no slippage/fees, 42-tick time exits) parallel to `RLTradingEnvironment`. That created distribution shift between birth-trained policies and evolution/nightly rollouts. The Elon Musk Mindset Protocol demands one physics truth: delete parallel simulators.

## Decision

We replace the custom birth tick simulator with `RLTradingEnvironment` + `ValuationEngine` as the sole training physics for Birth Phase v2. Custom `_simulate_chunk_with_policy` logic is removed; rollouts run via `lumina_core/birth/sim_runner.py`.

`InfiniteSimulator` remains for nightly evolution only; shared historical loading lives in `lumina_core/birth/history_loader.py`.

## Consequences

- Positief: Birth policies train on the same cost model and observation pipeline as PPO/evolution.
- Positief: Eliminates duplicate maintenance of exit logic and PnL math.
- Negatief: Existing v1 policy zips are invalid; operators must re-run Birth v2 (hard break).
- Risico's: Birth duration may change; mitigated by curriculum (ADR-0014).

## Alternatives Considered

- **Optie A:** Keep custom sim and align math incrementally — rejected; two truths persist.
- **Optie B:** Use InfiniteSimulator for birth — rejected; wrong abstraction and synthetic bias.

## Related ADRs

- ADR-0004: Purged cross-validation
- ADR-0011: Tauri lifecycle gate
- ADR-0013: Birth Certificate v2
- ADR-0014: Birth curriculum + OOS gate
