# ADR-004: AGI Safety System v54

**Status:** Accepted  
**Date:** 2026-04-23  
**Authors:** LUMINA Engineering (AI-assisted)

## Context

LUMINA v53 introduced seven constitutional principles enforced by `ConstitutionalChecker` (inline in `evolution_orchestrator.py`) and `MutationSandbox` (a subprocess executor). These were a good first step but had structural weaknesses:

1. **Only 7 principles** — missing critical financial controls (Kelly cap, leverage limit, daily loss stop, session guard, circuit breaker).
2. **No pre-mutation check** — principles were only enforced at *promotion time*, meaning the sandbox spent compute scoring DNA that would have been blocked anyway.
3. **Inline implementation** — the checker was instantiated directly in `_run_single_generation` with no shared state, statistics, or audit trail.
4. **No red-team coverage** — there were no adversarial tests attempting to bypass the principles.
5. **Scattered ownership** — `ConstitutionalChecker` in `engine/`, `MutationSandbox` in `evolution/`, no unified `safety/` package.

## Decision

Introduce a unified **`lumina_core/safety/`** package with three components:

### TradingConstitution (15 principles)
- Expanded from 7 to 15 principles covering all critical risk vectors.
- Singleton `TRADING_CONSTITUTION` imported once and shared.
- All principles fail-closed (exceptions treated as violations).
- `probe_attack()` method for red-team testing.

### SandboxedMutationExecutor
- Replaces `MutationSandbox` with a more robust implementation.
- Strips all secret env vars before subprocess fork.
- Adds `input_hash` + `output_hash` for forensic audit trail.
- Blocks network calls inside the sandbox via `socket.setdefaulttimeout`.

### ConstitutionalGuard
- Top-level integration point composing the above two.
- Three phases: `check_pre_mutation` → `evaluate_sandboxed` → `check_pre_promotion`.
- Shared instance per `EvolutionOrchestrator` (not re-instantiated per generation).
- Appends structured JSON to `state/constitutional_audit.jsonl`.
- Exposes `stats` (total checks, total blocks) for monitoring.

### Integration Points
- `_generate_candidates()`: `check_pre_mutation()` before registering each candidate.
- `_run_single_generation()`: `check_pre_promotion()` replaces the old inline checker.

## Consequences

### Positive
- **Defence in depth**: Pre-mutation → sandbox → pre-promotion creates three independent blocking opportunities.
- **Complete coverage**: All 15 principles documented with rationale, tested with ≥ 3 unit tests each.
- **Audit trail**: Every safety decision is logged with a unique `audit_id` for forensic review.
- **Red-team verified**: 38+ adversarial tests confirm attacks are blocked.
- **Unified ownership**: All safety code in `lumina_core/safety/`; backwards-compatible re-exports in old locations.

### Negative
- **Slightly more overhead per generation**: An extra in-process constitution check runs for each candidate before the sandbox. This is O(15) dict lookups — negligible vs. sandbox subprocess cost.
- **Frozen bypass keys**: Some attack vectors (deeply nested keys) are deliberately not checked at this time. This is documented and accepted.

## Backwards Compatibility

- `lumina_core/engine/constitutional_principles.py` remains intact (backward compat).
- `lumina_core/evolution/mutation_sandbox.py` remains intact (backward compat).
- The new `ConstitutionalGuard` in `evolution_orchestrator.py` replaces the inline `ConstitutionalChecker()` calls; the import remains for compatibility with any direct callers.
