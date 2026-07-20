# ADR-0034: Phase 2 Autonomy Foundation (Gated Scaffold)

**Status:** Accepted (2026-07-20)  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

Roadmap §7 defines Phase 2 Autonomy pillars (dynamic wall triggers, self-adaptive parameters, never-stop at scale, dynamic spawn without restart) as **planned**. Perfect Birth KPIs and unlock (`state/perfect_birth_complete.flag`) are documented but pillars must not be enabled opportunistically.

Existing building blocks already cover baseline never-stall recovery:

- `wall_trigger_engine.py` — pure stall evaluation  
- `adaptive_parameter_manager.py` — bounded window/chunk patches  
- `organism_autonomy.py` — twin-subordinated recovery dispatch  
- Event Bus birth handlers (`WallAdaptationHandler`, `OrganismAutonomyHandler`, …)

We need a **fail-closed architectural base** so pillars can be enabled incrementally under Approval Twin + Constitution + shadow discipline — without rewriting birth recovery or opening REAL capital paths.

## Decision

Introduce birth-scoped package `lumina_core/birth/phase2_autonomy/` with:

1. **Feature flags (default all OFF)** on `BirthCurriculumConfig` / `birth_v2.curriculum`:
   - `phase2_autonomy_enabled` (master)
   - `phase2_dynamic_wall_enabled`
   - `phase2_self_adaptive_params_enabled`
   - `phase2_instance_adapt_enabled`
   - `phase2_require_perfect_birth_flag` (default true)
   - `phase2_allow_sim_scaffold` (default false; SIM-only bypass of perfect-birth flag for tests)
   - `phase2_require_twin_for_apply` (default true)

2. **Gate order (non-negotiable):**  
   master → pillar → perfect birth unlock (or SIM scaffold) → constitution violations → twin (apply) → shadow if risk-touching.

3. **Pure proposers** (no side effects):
   - Dynamic wall: clamped `stall_wall_sec_multiplier` ∈ [0.75, 1.5], `stagnation_rollouts_delta` ∈ [-1, 2]
   - Params: `BIRTH_SAFE_PARAM_CATALOG` only; forbid risk/capital keys
   - Instance adapt: in-process only (`refresh_handler_cfg`, `spawn_plateau`, `spawn_phoenix_reset`, `noop`)

4. **Thin orchestrator** `Phase2AutonomyOrchestrator`: propose → gate → typed bus publish → optional non-REAL apply.

5. **Typed Event Bus topics:**
   - `birth.phase2.wall.proposal`
   - `birth.phase2.param.proposal`
   - `birth.phase2.instance.proposal`
   - `birth.phase2.gate.result`

6. **Integration:** optional hook from `WallAdaptationHandler` and lazy wiring via `BirthHandlerRegistry` / `build_orchestrator_from_cfg` — **zero behavior change** when master flag is false.

7. **Does not replace** `evaluate_wall_trigger` or `evaluate_terminal_stall`. Proposals feed inputs / recovery flags only when gated.

8. **Slice A closed loop (2026-07-20):** when gate allows apply (SIM/birth only):
   - Dynamic wall → `dataclasses.replace` shadow cfg thresholds into the **same** `evaluate_wall_trigger`
   - Param pillar → mutates `WallAdaptationState` on recovery signals
   - Instance pillar → merges `spawn_plateau` / `spawn_phoenix_reset` into adaptation response; optional `sync_curriculum_cfg`
   - REAL mode apply is hard-rejected (`risk_surface`)

## Scope and limitations (v1 foundation)

| In scope | Out of scope |
|----------|----------------|
| Interfaces + fail-closed gates | Auto-declare Perfect Birth |
| Clamped wall threshold proposals | ML wall policy / second wall engine |
| Birth recovery param catalog | Risk DNA / strategy code mutation |
| In-process instance adapt | OS process / multi-process spawn |
| Typed bus + unit tests | REAL broker twin paths |
| Consume perfect-birth flag | Never-stop at-scale KPI achievement |

## Consequences

### Positive

- Incremental enablement after Perfect Birth without capital-path risk.
- Clear contracts and tests for fail-closed defaults.
- Reuses existing twin subordination and birth handlers.

### Negative / trade-offs

- Another surface to maintain (justified by isolation + gates).
- Full pillar behavior still requires future slices after evidence.

## Alternatives considered

1. Enable dynamic walls directly inside `wall_trigger_engine` without gates — rejected (no Perfect Birth / twin rem).  
2. Top-level `lumina_core/phase2` package — rejected (birth bounded context ownership).  
3. OS process spawning for “dynamic spawn” — rejected for v1 (blast radius / REAL coupling).

## Links

- Roadmap §7: `docs/roadmap.md`  
- Perfect Birth KPIs: `docs/birth-phase-live-validation-runbook.md` §8–9  
- ADR-0031 / 0032 (Approval Twin)  
- ADR-0033 (code evolution — parallel evaluate-only pattern)  
- Code: `lumina_core/birth/phase2_autonomy/*`
