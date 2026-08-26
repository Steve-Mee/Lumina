# ADR-0046: Birth Foundation — evolvable plant (sequential 1/5–5/5)

**Status:** Accepted  
**Date:** 2026-08-14  
**Deciders:** LUMINA Engineering (Steve + AI)  
**Refines:** [ADR-0036](./0036-birth-exit-vs-maturation.md) §1 (exit = evolvable plant, not artifacts-only)

## Context

Intra-Birth numbering mixed three systems: S1–S3 survival/rolling WR, then a skip of S4 polish, then runway S5–S7 profit/risk/holdout as if they were Birth stages, then polish as index 8. Pass gates used WR 20/35/40% — a professional exam on a nursery geometry whose first-touch is ~29% and whose stops leaked ~3R.

## Decision

Birth is the **evolvable plant**. Five sequential stages, counted 1–5. Pass unit is process-R + occupancy + first-touch, never WR 20/35/40.

| # | Name | Pass (AND, fail-closed) |
|---|------|-------------------------|
| 1 | Closed loop | trades ≥ 150, constitution 0, entropy alive, settlement ≥ 70%, median_loss_R ≤ 1.5, net RR ≥ 0.80 |
| 2 | Selectivity | trades ≥ 250, occupancy 30–70%, round-trips, settlement, constitution 0, median_loss_R ≤ 1.5 |
| 3 | Mixed regimes | trades ≥ 400, occupancy 25–75%, settlement, constitution 0, median_loss_R ≤ 1.5, edge ≥ −0.05 |
| 4 | Viable plant | val slice, trades ≥ 100, occupancy, process-R, skill WR ≥ first-touch AND mean_R ≥ E_mech−0.10 |
| 5 | Probe & handoff | holdout read-only, trades ≥ 50, occupancy 25–75% (same `_common_body` as S3 — **intentional tighter extra**, not a loophole), edge ≥ −0.03, Sharpe > −2 (n≥50), DD ≤ 25% on $50k (`S5_DD_EQUITY_USD`), fitness vector |

Metric SSOT: `lumina_core/birth/foundation_metrics.py`. HUD `stage_pass_now` ≡ engine `passed`.

### Relocated (not deleted)

| Former Birth slot | Home now |
|-------------------|----------|
| Runway S5 profit (WR ≥ BE, mean R ≥ 0) | Playground (`post_birth_skill_gates.economic_viability`) |
| Runway S6 Sharpe 0.20 / DD 12% | Apprenticeship (`risk_discipline`) |
| Runway S7 / Evolution Proof OOS 0.45 | Awakening (`awakening_evolution_proof_from_fitness`) |
| Certificate OOS 0.48 / Sharpe 0.35 / DD 8% | Proving Ground / cert pipeline (`certificate_oos_walls`) |
| Perfect Birth KPIs | Phase 2 unlock (ADR-0036) |
| S4 polish as stage 8 | Light polish inside Birth stage 5 |

Death-spiral: expand data (90→180→365), then freeze. No swarm as novelty after signature repeat. No S1-trend oracle seed into later buffers.

Birth exit requires **all** five `foundation_v2` receipts plus checksum-consistent `lumina_birth_fitness_vector.json`. Completed flag or artifacts alone cannot exit.

## Consequences

- Live v1 receipts / `stage5_profit_val` checkpoints are incompatible — rewind to stage 1.
- Certificate evaluator remains; it is not an intra-Birth counter.
- Training HUD may still show WR/BE; pass gates must not.
