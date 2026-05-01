# ADR-001: Constitutional Trading Principles

**Status:** Accepted  
**Date:** 2026-04-23  
**Deciders:** LUMINA Engineering (Steve + AI)

---

## Context

LUMINA's self-evolution loop can mutate trading DNA without human intervention
in SIM/PAPER mode.  In REAL mode, human approval is required, but there was no
machine-readable safety contract that could be enforced at runtime — the rules
lived only in `.cursorrules` prose and operator runbooks.

The gap: a mutant DNA with `disable_risk_controller: true` or
`max_risk_percent: 10.0` could theoretically pass all existing gates
(twin confidence, shadow validation, swarm vote) and still be promoted to REAL
trading, potentially destroying capital.

## Decision

Introduce **Constitutional Principles** — a set of machine-enforceable, typed
checks that each DNA mutant must satisfy before promotion.  These are implemented
in `lumina_core/engine/constitutional_principles.py`.

### Principles (v53)

| Name | Severity | Description |
|------|----------|-------------|
| `capital_preservation_in_real` | FATAL | `max_risk_percent` <= 3 % in REAL |
| `no_naked_orders` | FATAL | DNA must not disable risk controller or order gatekeeper |
| `max_mutation_depth_enforced` | FATAL | `mutation_depth` must be `conservative` in REAL |
| `approval_required_in_real` | FATAL | `approval_required` must not be False in REAL |
| `no_synthetic_data_in_real_neuro` | FATAL | neuroevolution in REAL requires real OHLC |
| `drawdown_kill_percent_bounded` | FATAL | `drawdown_kill_percent` <= 25 % in any mode |
| `no_aggressive_evolution_in_real` | WARN | `aggressive_evolution` should be False in REAL |

### Enforcement point

The `ConstitutionalChecker` is called inside
`EvolutionOrchestrator._run_one_generation()` immediately after the mode-specific
gates and before the final swarm deliberation.  A FATAL violation sets
`promoted = False` and logs the reason — the swarm cannot override it.

### Sandboxing

All fitness scoring of mutants runs through `MutationSandbox`, which spawns a
subprocess with state/ redirected to a temp directory.  This prevents a buggy
mutant from corrupting the live state before being rejected.

## Consequences

- **Positive:** Formal, testable safety contract that cannot be overridden by
  any agent or model output.
- **Positive:** New principles can be added by appending to
  `CONSTITUTIONAL_PRINCIPLES` without changing the orchestrator.
- **Neutral:** ~45 s overhead per promoted candidate in REAL mode (sandbox timeout);
  negligible in nightly batch context.
- **Negative:** A false positive in the checker would block a valid mutation —
  mitigated by the `raise_on_fatal=False` audit mode used for logging and by
  the explicit test suite in `tests/test_constitutional_principles.py`.

## Alternatives Considered

1. **Config-only enforcement**: Rely on `config.yaml` flags being correct.
   Rejected — config can be mutated by the evolution loop itself.
2. **Post-promotion rollback**: Allow promotion, monitor, and rollback on breach.
   Rejected — capital can be lost before rollback fires.
3. **Separate compliance service**: External API that gates promotion.
   Rejected — adds network dependency and latency to the nightly loop.
