# ADR-0037: Self-play lab (Accepted — Phase 0 scaffold only)

**Status:** Accepted (lab scaffold only; **no birth-loop hooks**, **no apply**)  
**Date:** 2026-08-07  
**Deciders:** LUMINA Engineering  
**Track:** Deep-audit T16 / perfect self-play plan

## Context

After Perfect Birth tooling and Phase 2 SIM shadow (ADR-0034), multi-policy pressure beyond a single curriculum is valuable. Naive self-play is dangerous:

1. **Capital preservation is sacred** — never open REAL or bypass multi-gate.  
2. **Birth ≠ competence** (ADR-0036) — not a winrate war.  
3. **Twin / constitution** — no yaml `full_auto` force; judgment inside gates only.  
4. **Champion freeze** — cannot train past `rejected_no_lift` until accept/wipe.  
5. **Honesty** — hollow Perfect Birth / Phase 2 flags stay fail-closed.

Existing multi-policy pressure (compose, don’t fork):

- Policy swarm + `tournament_score` / tournament lift  
- Evolution generation + shadow deployment  
- Phase 2 autonomy proposers (observe/shadow first)

### Why implement Phase 0 *now*

T1–T15 closed the code bar for safety/ops gates. Remaining gaps are **operator evidence** (Fabric live, aperture samples, PB declare, twin labels). Phase 0 ships a **default-off pure lab** so physics and gates are testable without competence theater in `stage_loop`.

## Decision

### D1 — Musk first principles (delete first)

| Delete | Keep |
|--------|------|
| Second scoring universe / “selfplay_edgescore” | `tournament_score` only |
| stage_loop god-hook in v0 | Pure package + CLI + shadow report |
| REAL path | SIM / birth / lab capital only |
| Train through freeze | `blocked_champion_freeze` |
| Hollow production claim | Explicit Phase 0 label |

### D2 — One-sentence product

> **Self-play lab:** N policy variants evaluate on the **same frozen tick windows**; rank by `tournament_score`; emit a **shadow report**; never place orders; never mutate birth progress in Phase 0.

### D3 — Physics contract

| Axis | Decision |
|------|----------|
| Unit of play | Frozen-window policy variants (same as Policy Swarm) |
| Score | `tournament_score(trades, wins, total_pnl)` |
| Lift | Optional delta vs champion; `swarm_tournament_lift` floor |
| Apply | **Shadow report only** in Phase 0 |
| Default | `SelfPlayLabConfig.enabled = False` |
| Package | `lumina_core/birth/self_play/` |

### D4 — Gate order (fail-closed)

1. Lab enabled  
2. Not REAL-like capital  
3. Champion freeze inactive (or champion accepted)  
4. Frozen windows when required  
5. Apply always forbidden while `allow_apply=False` / Phase 0  

### D5 — Phases

| Phase | Scope | Status |
|-------|--------|--------|
| **0** | Pure scorer + gates + report + CLI + tests | **This ADR** |
| **1** | SIM apply under Twin + constitution (opt-in) | Deferred (SP3) |
| **2** | Birth-loop observe hook behind flag | Deferred (SP4) |

### D6 — Forbidden (any phase)

- Auto REAL / `sim_real_guard` orders from self-play  
- Lowering certificate floors  
- yaml force of twin `full_auto`  
- Architecture auto-apply of self-play mutations  
- Bypassing champion freeze / accept-champion-or-wipe  

### D7 — Operator residuals (higher priority than Phase 1+)

| ID | Residual | Why listed |
|----|----------|------------|
| OR1 | Fabric live SAFE_MODE / HB≥5s cancel | Mock gate done; NT8 host still operator |
| OR2 | Aperture ≥95% live samples | Tooling done; production samples missing |
| OR3 | Perfect Birth campaign + declare | Fail-closed human declare |
| OR4 | Twin promote + SSOT audit green | No yaml force; need labels/evidence |
| OR5 | Live champion freeze accept/wipe | Unit sacred; live is human fork |
| OR6 | Recovery theater awareness | Compress done; live theater = stop spin |

## Consequences

### Positive

- Testable tournament ranking without birth-loop risk  
- Explicit residual board so self-play cannot distract from capital honesty  
- Composes existing physics (no vanity fork)

### Negative

- No automatic skill gain in live birth until Phase 1–2  
- Operator must still run PB / Fabric / twin evidence tracks

## Alternatives considered

1. **Implement self-play in stage_loop now** — rejected: god-surface + freeze risk.  
2. **Rename swarm as self-play only** — vanity without new lab contract.  
3. **Stay Deferred forever** — rejected: user asked for perfect design + implementable Phase 0.

## Implementation (Phase 0 — shipped with this acceptance)

- `lumina_core/birth/self_play/{types,gates,scorer,report}.py`  
- `tests/birth/test_self_play_lab.py`  
- `scripts/validation/self_play_lab_gate.py`  
- `docs/self-play-lab.md`  
- Soft wire in `run_deep_audit_gates.py`

## Related

- [0034-phase2-autonomy-foundation.md](./0034-phase2-autonomy-foundation.md)  
- [0036-birth-exit-vs-maturation.md](./0036-birth-exit-vs-maturation.md)  
- [starship-birth.md](../starship-birth.md)  
- [birth-zero-human-metrics-runbook.md](../birth-zero-human-metrics-runbook.md)  
- [self-play-lab.md](../self-play-lab.md)  
