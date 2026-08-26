# ADR-0036: Birth Exit vs Maturation Continuum

**Status:** Accepted (2026-08-06); **§1 refined 2026-08-14 by [ADR-0046](./0046-birth-foundation-evolvable-plant.md)** (exit = evolvable plant, not any-of artifacts).  
**Deciders:** LUMINA Engineering (Steve + AI)  
**Supersedes / refines:** Partial guidance in [organism-maturation-phases.md](./organism-maturation-phases.md), [0027-lumina-maturation-ladder.md](./0027-lumina-maturation-ladder.md)

## Context

Operators and automated gates conflated several “done” concepts:

| Concept | Intent |
|---------|--------|
| **Birth exit** | Newborn *evolvable plant* — five Foundation receipts + fitness (ADR-0046) |
| **Birth Certificate v2** | Proving Ground / cert pipeline (not Birth exit) |
| **Perfect Birth** | Twin / autonomy / shadow KPI conjunction → Phase 2 unlock |
| **Maturation phases** | Awakening → Playground → Apprenticeship → Proving Ground → REAL |
| **REAL eligibility** | Fail-closed multi-milestone + human approve |

Using Perfect Birth, PromotionGate, OOS WR ≥ 0.48, or READY_FOR_REAL as **Birth exit** grades a newborn as a professional and traps curriculum in recovery theater.

## Decision

### 1. Birth exit is the evolvable plant (ADR-0046)

Birth phase completes when **all** of these hold (fail-closed):

- five `foundation_v2` receipts for `ordered_stages()` (S1–S5), each passing `verify_stage_pass_receipt`
- checksum-consistent `lumina_birth_fitness_vector.json`

These are **not** sufficient (closed loopholes):

- completed flag / `birth_curriculum_complete`
- PPO artifacts / checkpoint / DNA (`birth_artifacts_ok`)
- `birth_certificate_issued`
- crash-recovery `birth_started_with_artifacts`

Code SSOT: `is_birth_exit_sufficient` in `lumina_core/maturity/birth_exit.py`.

Default Stage-1 **EdgeScore** (HUD only) may still use **survival floors** (`birth_survival_pass_enabled: true`):

- WR floor ≈ **0.20** (diagnostic — not Foundation `passed`)
- Expectancy floor ≈ **−0.50**
- Plant soft-block rate cap

**Playground+ / skill-mode Stage-1** (when survival mode is **off**): skill floors WR 0.35 and expectancy −0.15 remain HUD pressure.  
OOS / cert skill walls remain **Proving Ground / certificate pipeline** — never Birth-exit blockers.

### 1b. Intra-Birth Foundation stages (not Birth-exit)

**Birth exit** (this ADR §1 + ADR-0046) is five sequential Foundation receipts. Intra-Birth pass is process-R / occupancy / first-touch — **never WR 20/35/40**.

| Stage | Pass class | Gate | Notes |
|-------|------------|------|--------|
| 1 Closed loop | Process-R | median_loss_R ≤ 1.5, net RR ≥ 0.80, settlement | No occupancy / WR / edge pass |
| 2 Selectivity | Occupancy + process-R | occupancy 30–70%, round-trips | EdgeScore `.passed` is HUD-only |
| 3 Mixed | Occupancy + edge | occupancy 25–75%, edge ≥ −0.05 | WR ~0.35 is **not** current law |
| 4 Viable plant | Skill AND | edge ≥ 0 AND mean_R ≥ E_mech−0.10 | Purged val slice |
| 5 Probe | Holdout + fitness | edge ≥ −0.03, Sharpe > −2, DD ≤ 25% | Occupancy extra via `_common_body` |

Normative language, why, anti-patterns, and config keys:  
**[docs/birth-curriculum-stage-floors.md](../birth-curriculum-stage-floors.md)** and **[ADR-0046](./0046-birth-foundation-evolvable-plant.md)**.

Do **not** restore Stage-2/3 WR 35% “because Birth is newborn,” and do **not** treat Stage-2 pass as Perfect Birth or REAL competence.

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

- Certificate is a **Proving Ground** wall — it is neither required nor sufficient for Birth exit. Operators who want cert-hard organisms still run the certificate pipeline after Foundation exit.  
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
