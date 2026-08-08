# ADR-0036: Birth Exit vs Maturation Continuum

**Status:** Accepted (2026-08-06)  
**Deciders:** LUMINA Engineering (Steve + AI)  
**Supersedes / refines:** Partial guidance in [organism-maturation-phases.md](./organism-maturation-phases.md), [0027-lumina-maturation-ladder.md](./0027-lumina-maturation-ladder.md)

## Context

Operators and automated gates conflated several “done” concepts:

| Concept | Intent |
|---------|--------|
| **Birth exit** | Newborn *survived* closed-loop training (breathe, plant, checkpoint) |
| **Birth Certificate v2** | Stronger curriculum + OOS artifact (may still be Birth exit *evidence*) |
| **Perfect Birth** | Twin / autonomy / shadow KPI conjunction → Phase 2 unlock |
| **Maturation phases** | Awakening → Playground → Apprenticeship → Proving Ground → REAL |
| **REAL eligibility** | Fail-closed multi-milestone + human approve |

Using Perfect Birth, PromotionGate, OOS WR ≥ 0.48, or READY_FOR_REAL as **Birth exit** grades a newborn as a professional and traps curriculum in recovery theater.

## Decision

### 1. Birth exit is survival-only

Birth phase completes when **any** sufficient proof holds:

- `birth_curriculum_complete` (engine completed flag / stages)
- `birth_artifacts_ok` (checkpoint / DNA / completed flag)
- `birth_certificate_issued` (certificate present — optional stronger proof)
- `birth_started_with_artifacts` (crash recovery path)

Default Stage-1 EdgeScore uses **survival floors** (`birth_survival_pass_enabled: true`):

- WR floor ≈ **0.20** (not 0.35 skill, not 0.48 OOS)
- Expectancy floor ≈ **−0.50**
- Plant soft-block rate cap

**Playground+ / skill-mode Stage-1** (when survival mode is **off**): skill floors WR 0.35 and expectancy −0.15.  
OOS / cert skill walls remain **Proving Ground / certificate pipeline** — never Birth-exit blockers.

### 1b. Intra-Birth stage floors (not Birth-exit)

**Birth exit** (this ADR §1) is survival-only. That does **not** mean every curriculum stage inside Birth uses survival floors.

| Stage | Floor class | Expectancy (WR−0.50 proxy) | Notes |
|-------|-------------|----------------------------|--------|
| Stage 1 (survival on) | Survival | ≥ **−0.50** (≡ ~20% WR) | Breathe / plant |
| Stage 2 Range | **Early-quality** | ≥ **−0.15** (≡ ~35% WR) | Flat 30–70%; **not** pro cert |
| Stage 3 Mixed | **Early-quality** | ≥ **−0.15** + WR floor ~0.35 | Still inside Birth |

Normative language, why, anti-patterns, and config keys:  
**[docs/birth-curriculum-stage-floors.md](../birth-curriculum-stage-floors.md)** (locked SSOT).

Do **not** lower Stage-2/3 floors to −0.50 “because Birth is newborn,” and do **not** treat Stage-2 pass as Perfect Birth or REAL competence.

### 2. Explicit non-requirements for Birth exit

These **must not** block Birth → Phase Hub:

- Perfect Birth flag / autonomy KPI conjunction  
- Evolution Proof (Awakening)  
- Deck unlock / first SIM order (Playground)  
- `sim_real_guard_stable` / READY_FOR_REAL (Apprenticeship)  
- Shadow / PromotionGate (Proving Ground)  
- Human REAL approval  
- Twin full_auto / high-conf primary  

They remain **post-birth** milestones on the maturation continuum.

### 3. After Birth: Phase Hub, not Deck / REAL

On Birth exit:

1. Continuum marks `birth` completed with exit proofs  
2. Operator returns to **Phase Hub** (`app_surface=hub`)  
3. Next phase is **Awakening** (manual / telegram / auto_evolve per hub policy)  
4. REAL remains multi-gate + human (H2); never pure auto  

### 4. Code SSOT

| Surface | Path |
|---------|------|
| Policy + evaluate | `lumina_core/maturity/birth_exit.py` |
| Phase exit proofs | `phase_specs.evaluate_exit_proofs("birth")` → birth_exit |
| Continuum migrate | `continuum.migrate_from_milestones` uses `evaluate_birth_exit` |
| Mark complete | `MaturityService.mark_birth_complete_from_artifacts` |
| API | `GET /api/maturity/birth-exit` |
| EdgeScore floors (Stage 1) | `starship_edgescore_stage1.py` survival vs skill-side |
| Intra-Birth Stage 2/3 floors | `starship_edgescore_stage{2,3}.py` + [birth-curriculum-stage-floors.md](../birth-curriculum-stage-floors.md) |

## Consequences

### Positive

- Newborn is not failed for not “walking.”  
- Perfect Birth and REAL gates stay honest and separate.  
- Hub can show a single Birth-exit panel (`birth_exit_v1`).  

### Negative / trade-offs

- Certificate is *sufficient* but not *required* for Birth exit — operators who want cert-hard Birth must still run certificate pipeline before treating organism as “certified.”  
- Soft lab modes for later phases unchanged (`experimental_soft_complete`).  

## Alternatives considered

1. **Certificate-only Birth exit** — rejected; traps survival when OOS skill walls fail.  
2. **Perfect Birth as Birth exit** — rejected; Perfect Birth is Phase 2 unlock (C1).  
3. **Keep only prose ADR** — rejected; H7 needs enforceable SSOT + tests.  

## Related

- ADR-0012 Birth phase v2  
- ADR-0013 Birth Certificate v2  
- ADR-0026 Evolution Proof  
- ADR-0027 Maturation ladder  
- organism-maturation-phases.md (hub + survival floors)  
- [birth-curriculum-stage-floors.md](../birth-curriculum-stage-floors.md) — Stage 1 survival vs Stage 2/3 early-quality (locked)  
- ADR-0007 Promotion gate REAL  
- H2 real multi-gate  
