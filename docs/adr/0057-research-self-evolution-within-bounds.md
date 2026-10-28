# ADR-0057: Research self-evolution within bounds (Phase 3)

**Status:** Accepted  
**Date:** 2026-10-28  
**Deciders:** LUMINA Engineering

## Context

Phase 1 put a fail-closed Validation Gate in `lumina_research/validation/`. Phase 2 put a propose-only research loop on the Event Bus (`HypothesisProposed` → sealed `ValidationResult` → `PromotionCandidate`). Steve's Phase 3 goal is that birth and parameter tuning may adapt, but only through those gates.

First principles:

- Capital preservation stays outside the evolutionary path. The live Risk Core (`lumina_core/risk/`) and the packaged research Risk Core / gate floors are not search parameters.
- Truth-seeking: every mutation is a trial. DSR N must increase. Fitness is the Phase 1 composite of OOS metrics, never in-sample PnL.
- Adaptation rate only counts if the Validation Gate still kills noise.
- Extreme intellectual honesty, rigorous testing, and radical creativity: the organism may open new walk-forward windows and tune parameters; it may not rewrite the fort.

This supports the mission: a self-evolving research loop that remains fail-closed.

## Decision

- Birth and evolution live in `lumina_research/evolution/`. They do not import `archive/birth-v1/`.
- `ReflectorAgent` and `BirthPhase` can only **propose**. `GovernanceGate` admits or rejects. Admitted parameter/window mutations become Phase 2 hypotheses and must pass `evaluate_candidate` → `passes_validation_gate` → research Risk Core before a `PromotionCandidate`.
- Every `propose()` records a `TrialRegistry` trial before the mutation is sealed.
- Regime detection (volatility, trend) returns a **size multiplier** only. Hard strategy switches are refused.
- Changing Risk Core or `gate_thresholds.toml` / `FLOOR_*` requires an ADR file under `docs/adr/` **and** an HMAC-signed human review (`ReviewAuthority`, separate key from research provenance). Even then evolution **does not apply** the file write; it records `protected_recorded_not_applied`.
- Integrity snapshots hash live `lumina_core/risk`, research `risk_core`, gate floors, and the bound Validation Gate. Drift or monkeypatching fail-closes the run.
- Additive bus topics: `research.mutation.proposed`, `research.governance.decision`. Existing topics stay unchanged.

## Consequences

### Positive

- Parameter search and new windows are possible without opening a skip-gate path.
- DSR N reflects the real search. Noise mutations are expected to die.
- Threshold / Risk Core tampering is an explicit human process, not a fitness trick.

### Negative

- ADR-approved threshold changes are not auto-applied (humans edit files out of band). That is intentional fail-closed.
- Each mutation costs a full Phase 1 evaluation (walk-forward, CPCV, DSR, PBO, costs, regimes).

## Alternatives considered

1. Let the reflector write floors when fitness is high — rejected: that is a skip-gate / capital-preservation violation.
2. Reuse `archive/birth-v1/` search — rejected: RESEARCH_CHARTER forbids it.
3. Regime-conditional strategy switching — rejected: sizing/throttling only.
4. Share the provenance HMAC key with human reviews — rejected: agents could forge a "human" signature.

## Links

- Charter: `RESEARCH_CHARTER.md`
- Phase 1/2: `lumina_research/validation/`, `lumina_research/agents/`
- Related: `docs/adr/0007-promotion-gate-real-mode.md`, `docs/adr/0003-trading-constitution-sandboxed-mutation-executor.md`
