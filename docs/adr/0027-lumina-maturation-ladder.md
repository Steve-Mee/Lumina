# ADR-0027: Lumina Maturation Ladder

## Status

Accepted (2026-06-27)

## Context

LUMINA is modeled as a living organism: **Genesis** (contract) → **Birth** (embryogenesis on historical data) → post-birth **growth phases** before REAL capital. Operators lacked a single surface to set birth goals and understand REAL maturity requirements. The Stage 1 winrate gate was hidden in running-phase settings instead of Genesis.

**Elon Musk Mindset:** Delete what fails (REAL without proof), keep what works (configurable birth pipeline), make the ladder visible.

## Decision

Define a **six-phase maturation ladder** SSOT:

| Phase | Name | Purpose | Blocks REAL? |
|-------|------|---------|--------------|
| 0 | Genesis | Maturity contract (training + birth gate) | No |
| 1 | Birth | Curriculum on historical simulator | No |
| 2 | Awakening | Certificate v2 + Evolution Proof (ADR-0026) | Yes |
| 3 | Playground | NT sim, relaxed exploration | No |
| 4 | Apprenticeship | `sim_real_guard`, REAL constitution | Yes (stability) |
| 5 | Proving Ground | Shadow + PromotionGate (ADR-0007) | Yes |
| 6 | REAL | Live capital | — |

**Genesis UI** ([`BirthGenesisDeck.tsx`](../../tauri-app/src/components/birth/BirthGenesisDeck.tsx)) becomes the **Maturity Charter**: educative copy, ladder preview, birth goals (including `stage1_winrate_pass_threshold`), and read-only REAL maturity targets.

**Progress SSOT:** [`lumina_core/maturity/maturation_progress.py`](../../lumina_core/maturity/maturation_progress.py) → `state/lumina_maturity_progress.json`

**API:** `GET /api/maturity/progress`, `POST /api/maturity/approve-real`

**REAL toggle:** Command Deck fail-closed on `maturation_eligible_for_real()` — requires milestones: Birth Certificate, Evolution Proof, SIM stability (`READY_FOR_REAL`), and PromotionGate pass. Operator approval recorded via `POST /api/maturity/approve-real` before `POST /api/core/mode` with `mode=real`.

**Event hooks:** [`lumina_core/maturity/milestone_hooks.py`](../../lumina_core/maturity/milestone_hooks.py) wired from birth engine, SIM stability checker, and evolution orchestrator.

## Consequences

- Positive: Operators set birth gate before ACTIVATE BIRTH; REAL requirements are explicit and enforced on backend.
- Positive: Unified configure path persists winrate gate via [`persist_tauri_quick_config`](../../lumina_launcher/services/setup_persist.py).
- Positive: Single REAL gate replaces fragmented go-live / certificate-only checks.
- Negative: Genesis UI is denser — mitigated by collapsible advanced panel.
- Constitution: SIM/REAL separation unchanged; no relaxatie of REAL admission chain.

## Related ADRs

- ADR-0011: Tauri lifecycle gate
- ADR-0013: Birth Certificate v2
- ADR-0026: Evolution Proof gate
- ADR-0007: Promotion gate REAL mode
