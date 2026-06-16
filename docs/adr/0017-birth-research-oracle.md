# ADR-0017: Birth Research Oracle (BRO)

**Status**: Accepted

**Date**: 2026-06-12

## Context

Birth v2 curriculum could stop mid-training when a single rollout produced few trades (`curriculum_failed`, `simulation_stall`). PPO updates also received zero usable rows because trajectory observations used `vector` while the trainer only read `price`. Operators saw stale failure snapshots after fixes because the backend process was not restarted.

Curriculum was treated as an exam; the system needed to treat it as **research** on all available historical data, with only the OOS Birth Certificate v2 blocking Command Deck access.

## Decision

Introduce **Birth Research Oracle (BRO-v1)** in SIM/birth only:

1. **Pattern miner** — hindsight oracle scan labels profitable entries on historical ticks and injects trajectories into the PPO buffer (priority 3.0+).
2. **Data expansion ladder** — on stagnation, escalate `days_back` through `[90, 180, 365, 730]`, re-enrich, re-mine; birth continues unless all expansion steps fail with zero patterns and zero trades.
3. **News enricher** — Finnhub → FMP → Alpha Vantage → local cache; degraded mode when APIs unavailable (no hard-fail).
4. **Engine loop** — `_run_stage_research_loop` replaces stall-on-underperformance; phases `curriculum_research`, `curriculum_learning`, `data_expansion`; gen-0 oracle soft-pass when buffer is rich.
5. **PPO fix** — `_trajectory_buffer_to_rows` reads `observation.vector[0]` as price fallback.
6. **UI/SSOT** — running birth sanitizes stale `curriculum_failed` progress; new progress fields exposed to Command Deck client.

**Hard invariants:**

- No REAL order-flow changes.
- Oracle labels are research-only (historical hindsight).
- Constitution guard remains on rollout entries.
- Only OOS certificate failure or true `history_unavailable` may block deck entry mid-pipeline.

## Consequences

- Positief: Birth never stops on underperformance during curriculum; PPO receives signal from oracle + rollouts.
- Positief: News-aware observation enrichment improves regime coverage without blocking birth.
- Positief: Stale UI failure states suppressed while training is live.
- Negatief: More compute per stage (oracle scan + expansion).
- Risico's: Oracle soft-pass must not inflate OOS certificate metrics — certificate gate unchanged (ADR-0013).

## Alternatives Considered

- **Optie A:** Lower stage trade thresholds only — rejected; treats symptom, not learning signal gap.
- **Optie B:** Infinite rollouts without oracle — rejected; HOLD-only policies stall indefinitely.
- **Optie C:** Re-introduce `curriculum_failed` for operator clarity — rejected; violates never-stop research model.

## Related ADRs

- ADR-0012: Single simulator SSOT
- ADR-0013: Birth Certificate v2
- ADR-0014: Birth Curriculum + OOS Gate
- ADR-0015: RL observation SSOT (32-dim vectors)
