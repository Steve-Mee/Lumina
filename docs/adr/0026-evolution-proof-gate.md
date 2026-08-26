# ADR-0026: Post-Birth Evolution Proof Gate

> **Supersession (2026-08-14):** Birth Foundation no longer uses a WR 35–45% curriculum pass ([ADR-0046](./0046-birth-foundation-evolvable-plant.md)). Evolution Proof remains an **Awakening / post-Birth** wall. Certificate OOS ≥48% remains Proving Ground — not Birth exit.

## Status

Accepted (2026-06-27)

## Context

Birth curriculum stage 1 can use a **configurable** winrate pass gate (default 45%, floor 35%) to validate the learning pipeline without claiming REAL readiness. Birth Certificate v2 already requires OOS winrate ≥48% for artifact validation. Operators may lower the birth gate to unblock curriculum progression while the organism is still immature.

**Mission alignment:** Kapitaalbehoud blijft heilig — REAL mode must fail-closed until objective post-birth fitness is demonstrated. **Elon Musk Mindset:** delete what fails (block REAL without proof), keep what works (allow birth to complete at lower gate when pipeline-validated).

## Decision

Introduce a **three-layer promotion model**:

| Layer | Purpose | Threshold | Blocks REAL? |
|-------|---------|-----------|--------------|
| Birth curriculum (stage 1) | Pipeline bootstrap | Configurable (default 45%, floor 35%) | No |
| Birth Certificate v2 OOS | Holdout quality | ≥48% winrate (existing) | Yes |
| **Evolution Proof Gate** (new) | Post-birth improvement | Winrate lift ≥5% vs birth exit **or** polish OOS ≥45% on ≥500 trades | Yes |

Implementation SSOT: [`lumina_core/birth/evolution_proof_gate.py`](../../lumina_core/birth/evolution_proof_gate.py)

- Evaluated at certificate issue via `record_and_evaluate_at_certificate()`.
- Persisted to `state/lumina_evolution_proof.json`.
- `evolution_proof_passed()` returns **False** when no record exists (fail-closed). Legacy grandfather is opt-in via `birth_v2.curriculum.evolution_proof_grandfather_missing` or `allow_legacy_grandfather=True`.
- [`lumina_launcher/services/birth_service.py`](../../lumina_launcher/services/birth_service.py): `artifacts_ok()` and `real_trading_eligible()` require evolution proof pass.

Config under `birth_v2.curriculum.evolution_proof_*`.

## Consequences

- Positive: Lower birth gate (35%) no longer implies REAL eligibility; operator must see measurable evolution.
- Positive: Fail-closed REAL launcher; constitution and certificate gates unchanged.
- Negative: Additional polish/OOS data required before REAL — may extend post-birth refinement window.
- Negative: Legacy runs without a proof file are **not** REAL-eligible unless `evolution_proof_grandfather_missing` is explicitly enabled.

## Related ADRs

- ADR-0013: Birth Certificate v2
- ADR-0014: Birth Curriculum OOS gate
- ADR-0007: Promotion gate REAL mode
- ADR-0025: Milestone notifications (`evolution_proof_passed` / `failed` events)
