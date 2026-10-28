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
