# ADR-0038: One Twin DNA · Dual Authority (SIM explore vs REAL values)

**Status:** Accepted  
**Date:** 2026-08-10  
**Deciders:** LUMINA Engineering (Steve + Grok Captain)  
**Relates:** [ADR-0032](./0032-approval-twin-human-replacement-layer.md), [ADR-0044](./0044-twin-base-curriculum-and-escalation.md), H2 real multi-gate, `sim_real_guard`

## Context

Operators need **free exploration in pure SIM/Birth** (learn from mistakes) while keeping **careful judgment when capital is at stake** (REAL, and pre-REAL `sim_real_guard`). Dual Twin models (SIM-Twin + REAL-Twin) would drift and contradict. Base curriculum previously mixed “SIM may be loose” language into the only conscience.

## Decision

1. **Single ApprovalTwin DNA** — one model, one `SteveValuesRegistry`, one conscience.  
2. **Dual authority by `capital_mode`** (policy, not a second agent):

| capital_mode | `twin_values_role` | Twin preference blocks DNA/learn loop? | Sole-execute REAL capital? |
|--------------|--------------------|----------------------------------------|----------------------------|
| birth / sim | `explore_pass` | **No** (pass-through; shadow log OK) | No |
| sim_real_guard | `values_active` | **Yes** (trained REAL values) | No (SIM $ + REAL-like guards) |
| real / live / prod | `values_inside_gates` | Input only + multi-gate | **Never** without human multi-gate |

3. **Base / micro / escalation labels train REAL-conscience only** (`base_v4`).  
   Free SIM freedom is **authority**, never a training target of “always APPROVE because SIM”.  
4. **Hard safety unchanged** — constitution, sandbox, PromotionGate, real multi-gate never bypassed.  
5. SSOT helpers: `twin_values_role`, `twin_primary_judgment_for_decision`, `apply_mode_authority` in `twin_discipline` / `twin_mode_types`.

## Consequences

### Positive
- One coherent operator conscience for dress rehearsal and REAL.  
- Birth/SIM velocity: Twin does not throttle the organism with preference vetoes.  
- Clear mental model for operators filling base training.

### Negative / mitigated
- Operators must retrain on version bump (`base_v4`) — fail-closed readiness.  
- Shadow Twin in explore_pass may still log — throttle Telegram if noisy.

## Alternatives rejected

1. Two Twin agents — drift, dual maintenance.  
2. Train Twin to always APPROVE in SIM — pollutes single DNA at regime flip.  
3. Twin bypasses REAL gates on high conf — constitution violation.

## Links

- Code: `twin_discipline.py`, `twin_mode_types.apply_mode_authority`, `organism_autonomy.py`, `twin_base_curriculum.py`  
- ADR-0032, ADR-0044  

*One conscience. Two authority regimes. Hard gates never optional.*
