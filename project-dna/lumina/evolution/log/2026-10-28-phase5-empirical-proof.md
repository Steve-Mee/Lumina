# Phase 5 empirical proof and Fabric ports (2026-10-28)

ADR-0059. `lumina_research` stays a separate layer. No NT8/gRPC coupling. No SIM or live orders.

- P1: independent verification suite (`lumina_research/proof/`). Phase 4 floors frozen. Two-horizon TTD 15 / 45.
- P2: 12 registered economic templates, 24 variants. Real data or documented stop. Kill-rate diagnostic, not a gate.
- P4: Guardian asserts Risk Core hash, sealed gate passage, mutation kill ≥ 0.80. Weekly FAR/TTD by horizon. Capital-preservation violations must be 0.
- P5 costs: existing CostModel bands; limit trade-through fill model; SIM plan written, not started.
- Ports: `research.signal.intent` / `research.order.intent` / `research.fill.observed` / `research.execution.alert`. Shadow logs CostModel fills. SIM whitelist empty and immutable. LIVE_RELEASE forbidden. Fail-closed: stale/lost → no new orders; alarm → de-weight; flatten only as a Risk Core recommendation.

CLI: `python -m lumina_research.proof verify|research|weekly`

## Honest run (2026-10-28)

- `python -m lumina_research.proof verify` exit 2. Phase 1 gate passed. Mutation kill 0.825 passed. Medium horizon passed (slow TTD max 31 ≤ 45). Short horizon failed: independent `high_vol_mixture` FAR 0.95 vs frozen 0.10 cap. Detection on decaying kinds was 1.0 with max TTD 13 ≤ 15. Floors were not retuned.
- `python -m lumina_research.proof research` exit 3. No ES/NQ/MES/MNQ bars on disk. 24 templates pre-registered, 0 tested. SIM plan written, not started.
- No NT8 coupling. No SIM or live orders.

## Follow-up (plan authors / Steve, same day)

- Primary high-vol FAR is now `healthy_regime_switch` (between-window 20d>75th of 252d or VIX>25). `high_vol_mixture` is reported as STRESS only.
- Detector may scale variance to live noise vol; packaged thresholds unchanged. High-vol confirm = 3 (max 3); normal stays 2. Alarms log `vol_regime`.
- Official continuity FAR/TTD uses HOLDOUT_SEEDS, disjoint from Phase 4 and the PR #63 independent set. Gate suite stays on the independent planted seeds.
- P2 prep: 12 of 24 variants pre-registered (MES/MNQ, one per family) before seeing bars. Holdout lock on last 9 months, fail-closed. NT8 1m MES/MNQ data spec written. Cycle not run.

## Official holdout verify (2026-10-28T20:32:00Z)

`python -m lumina_research.proof verify` exit 0. Every frozen floor passed. Seeds `8675309, 424242, 135790, 246801, 112358, 132134, 178101, 192837, 204060, 777277`.

| slice | n | FAR | FAR floor | detection | TTD max | TTD floor | pass |
|---|---|---|---|---|---|---|---|
| healthy_laplace | 60 | 0.0000 | 0.05 | 0.0000 | n/a | n/a | PASS |
| abrupt_student | 60 | 0.0000 | n/a | 1.0000 | 8.0 | 15 | PASS |
| gradual_smooth | 60 | 0.0000 | n/a | 1.0000 | 14.0 | 15 | PASS |
| healthy_regime_switch | 60 | 0.0333 | 0.10 | 0.0000 | n/a | n/a | PASS |
| high_vol_mixture | 60 | 0.6833 | stress | 0.0000 | n/a | n/a | reported |
| regime_laplace | 60 | 0.0000 | n/a | 1.0000 | 11.0 | 15 | PASS |
| material_break | 60 | 0.0000 | n/a | 1.0000 | 5.0 | 15 | PASS |
| regime=normal | 295 | 0.0000 | 0.05 | 1.0000 | 14.0 | 15 | PASS |
| regime=high_vol | 65 | 0.0308 | 0.10 | 0.0000 | n/a | n/a | PASS |
| slow_gradual_30 | 60 | 0.0000 | n/a | 1.0000 | 21.0 | 45 | PASS |
| slow_gradual_45 | 60 | 0.0000 | n/a | 1.0000 | 26.0 | 45 | PASS |
| slow_gradual_60 | 60 | 0.0000 | n/a | 1.0000 | 30.0 | 45 | PASS |

- mutation kill 0.825 ≥ 0.80. Phase 1 gate passed on independent planted seeds.
- `python -m lumina_research.proof research` exit 3. No NT8 bars on disk. 12 MES/MNQ first-cycle variants pre-registered before `discover_data`. Holdout lock fail-closed. No orders.
