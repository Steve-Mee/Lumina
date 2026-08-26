# ADR-0033: Trading Code Evolution Prototype (Sandbox + Twin + Constitution)

**Status:** Accepted (2026-07-15)  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

DNA evolution (`SandboxedMutationExecutor`) and architecture meta (ADR-0030) exist, but Lumina still cannot **propose and safely evaluate** small *trading-related code* changes (parameter tweaks, simple indicators, minor strategy snippets) under a single fail-closed pipeline.

Roadmap §8 called this “secure self-code evolution” a vision. This ADR introduces the **first minimal prototype**: evaluate-only, fixed operators, default disabled.

## Decision

Introduce bounded context `lumina_core/code_evolution/` with:

1. **Fixed operator catalog** only: `PARAMETER_TWEAK`, `ADD_SIMPLE_INDICATOR`, `STRATEGY_SNIPPET_ADJUST`.
2. **Logical sandbox targets** only (`sandbox.params`, `sandbox.indicator`, `sandbox.strategy_snippet`) — never live risk/broker paths.
3. **Pipeline order (non-negotiable):**  
   `CodeEvolutionConstitution` → optional `ConstitutionalGuard` → `ApprovalTwinAgent.evaluate_code_proposal` → `SandboxedCodeExecutor` → audit + journal.
4. **Subprocess sandbox** (`lumina_core/safety/sandboxed_code_executor.py`) reusing DNA sandbox isolation patterns (tmpdir, secret strip, timeout, JSON I/O, no network).
5. **Evaluate-only v1 (superseded in code by H5 sandbox-store apply):** live-repo apply remains forbidden. H5 may write `state/code_evolution/applied/{champion,challenger}/` under gates. Closed-loop load/cutover is **ADR-0045** — not claimed Done here. Reversibility via `before_snapshot` + `REVERT.json` journal bundles.
6. **Default disabled** (`evolution.code_evolution.enabled: false` in `config.yaml`).
7. **Typed Event Bus topics:** `evolution.code.proposal.created`, `evolution.code.sandbox.result`, `evolution.code.decision`.
8. **Canonical audit stream:** `evolution.code_mutation` → `state/code_evolution_audit.jsonl`.

Twin judgment is mode-aware (shadow/assisted/full_auto). Twin **never** bypasses constitution or sandbox. Shadow mode may still run sandbox evaluation when the twin does not hard-veto; `effective_recommendation` remains non-executable for apply.

## Consequences

### Positive

- First real foothold for self-modifying *trading* logic under hard rem.
- Auditable, reversible, testable, fail-closed.
- Clear separation from architecture_meta (no trading behavior) and DNA evolution.

### Negative / trade-offs

- No live apply yet (intentional).
- No LLM open-ended codegen (intentional).
- Extra pipeline surface to maintain.

## Alternatives considered

1. Fold into architecture_meta — rejected (ADR-0030 forbids trading behavior change).
2. Only AST validate in-process (StrategyGenerator) — rejected (insufficient isolation + no Twin/audit pipeline).
3. Free-form LLM file rewrites — rejected for v1 safety.

## Links

- ADR-0003 (constitution + sandboxed mutation)
- ADR-0030 (architecture meta — orthogonal)
- ADR-0031 / 0032 (Approval Twin)
- Code: `lumina_core/code_evolution/*`, `lumina_core/safety/sandboxed_code_executor.py`
- Docs: `docs/AGI_SAFETY.md`, `docs/roadmap.md` §8
