# ADR-0030: Architecture Meta-Controller (Sandboxed Self-Improvement of Architecture)

**Status**: Accepted (2026-07-13)

## Context

Current evolution (SelfEvolutionMetaAgent + EvolutionOrchestrator + birth meta) is powerful for trading DNA, hyperparams, and curriculum recovery. However, the system cannot yet propose, sandbox, and safely promote *its own architecture and source improvements*. The Recursive Self-Improvement Protocol and constitution call for measurable, small-step evolution of architecture while maintaining strict safety.

History and analysis explicitly noted that evolution remained "only hyperparameter tuning".

## Decision

Introduce a **radically simple ArchitectureMetaController** layer:

- Pure observe → propose model (modeled directly on `BirthMetaController`).
- Fixed catalog of 4 narrow, safe operators only (`EXTRACT_PURE_HELPER`, `INTRODUCE_TYPED_MODEL`, `BOUNDARY_VIA_PORT`, `SIMPLIFY_GUARD`).
- Every candidate evaluated in `ArchitectureMutationSandbox` (tempdir isolation, modeled on `SandboxedMutationExecutor`).
- Full `ArchitectureConstitution` + reuse of `ConstitutionalGuard` patterns (pre-mutation / pre-promotion).
- **Mandatory human-in-the-loop promotion gate** (never auto-apply, even in SIM). Marker file + decision record.
- Primary measurable: deterministic `arch_health_score` (0-10) + deltas logged to `logs/architecture_evolution.jsonl`.
- Default **disabled**. Small patches (<80 lines). Whitelisted targets only.

Implementation lives in new bounded context `lumina_core/architecture_meta/`.

Invariants preserved:
- Constitution (bounded contexts, typed contracts, no god growth).
- Kapitaalbehoud (indirect via safer architecture).
- Fail-closed on every gate.
- Agents propose; explicit human is Final Arbitration.
- No changes to trading execution, risk, or order paths.

## Consequences

**Positive**:
- Measurable, falsifiable progress on evolvability and architecture health.
- Strong safety rails (sandbox + constitution + human) allow safe experimentation on the meta layer itself later.
- Reuses proven patterns (birth meta purity, sandbox isolation, rollout/human gates).

**Negative / Trade-offs**:
- Additional (but tiny) code surface.
- Human gate adds latency (intentional).
- v1 uses heuristic proposals (no LLM generation) to stay deterministic and simple.

## Files

- `lumina_core/architecture_meta/{controller,sandbox,constitution,promotion_gate}.py`
- Schemas, config, tests, ADR.

## Related

- ADR-0003 (constitution + sandboxed mutation)
- ADR-0021/0022/0023 (birth meta controller patterns)
- `project-dna/lumina/self-improvement-protocol.md`
- `project-dna/lumina/constitution.md`
- Evolution Rollout Framework

## Measurement

`arch_health_score` improvement on accepted proposals; proposal acceptance rate; zero violations of core constitution principles on applied patches.
