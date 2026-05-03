# ADR-0007: PromotionGate as hard REAL-mode gate

**Status**: Accepted

**Date**: 2026-05-02

## Context

REAL promotions previously depended on shadow progression and rollout checks, but could still be influenced by lightweight profitability signals that do not sufficiently capture overfitting, execution drift, and stress fragility. For a self-evolving trading organism, this creates unacceptable capital risk in REAL mode.

LUMINA requires a machine-enforced gate that is measurable, fail-closed, and auditable before any candidate can move from shadow to REAL.

## Decision

We introduce `PromotionGate` in `lumina_core/evolution/promotion_gate.py` and enforce it as a mandatory step inside `PromotionPolicy.run_shadow_validation_gate()` for REAL mode.

Promotion is allowed only when all four criteria pass:

1. Out-of-sample robustness (Purged Walk Forward + Combinatorial Purged CV).
2. Reality gap constraints (band, trend, fill-rate drop, slippage ratio).
3. Stress drawdown ceiling under deterministic scenarios.
4. Statistical significance (`p < 0.05`, `Cohen's d > 0.3`, minimum sample size).

If any evidence is missing/invalid, or any criterion fails, promotion is rejected (fail-closed).  
Every evaluation is written to `state/promotion_gate_audit.jsonl`.

## Consequences

- Positive:
  - REAL promotion is now a hard, measurable safety gate.
  - Promotion decisions become auditable per DNA hash with explicit fail reasons.
  - Overfit and execution-fragile candidates are blocked before human approval can approve promotion.
- Negative:
  - Promotions can be delayed when evidence pipelines are incomplete.
  - Existing test fixtures may require richer promotion evidence payloads.
- Risks:
  - False negatives when thresholds are too strict for early-stage strategies.
  - Operational dependency on consistent reporting of CV/reality-gap/stress metrics.

## Alternatives Considered

- Shadow-only gate without statistical/OOS evidence: rejected (insufficient against overfitting).
- Human approval as primary guard: rejected (not deterministic, not machine-enforced).
- Single-metric gate (`mean_pnl > 0` or Sharpe only): rejected (too easy to game, weak under distribution shift).

## Related ADRs

- `docs/adr/0002-shadow-deployment-human-approval.md`
- `docs/adr/0003-trading-constitution-sandboxed-mutation-executor.md`
- `docs/adr/0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md`
