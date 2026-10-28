# LUMINA — Agent Instructions Index (SSOT pointer)

**Role of this file:** Index for humans and AI agents. It does **not** invent policy.
Binding laws live in the documents listed below. If this index conflicts with
`constitution.md` on capital-preservation or REAL-mode safety, the constitution wins.
If this index conflicts with `RESEARCH_CHARTER.md` on validation, promotion, or
signal writing, the charter wins.

## Read order (mandatory)

1. [`RESEARCH_CHARTER.md`](../../RESEARCH_CHARTER.md) — Validation Gate; research may only propose; **no new signals until Phase 1**
2. [`constitution.md`](constitution.md) — non-negotiable capital and REAL-mode invariants
3. [`north-star.md`](north-star.md) — mission compression
4. [`architecture.md`](architecture.md) — layers and bounded contexts (DNA view)
5. [`docs/architecture.md`](../../docs/architecture.md) — living architecture overview
6. [`docs/roadmap.md`](../../docs/roadmap.md) — capability waves (not release tags)
7. [`evolutionary-debt.md`](evolutionary-debt.md) — current evolvability debt catalog
8. [`operating-system/skills/README.md`](operating-system/skills/README.md) — agent skills

## Skills (mandatory activation)

- [`validation-rigor`](../../.cursor/skills/validation-rigor/SKILL.md) — enforce the Validation Gate (DSR, PBO, CPCV, walk-forward, costs, regimes). Canonical copy: [`operating-system/skills/validation-rigor.md`](operating-system/skills/validation-rigor.md).
- [`constitution-guard`](../../.cursor/skills/constitution-guard/SKILL.md)
- [`risk-safety-review`](../../.cursor/skills/risk-safety-review/SKILL.md)
- [`token-efficiency`](../../.cursor/skills/token-efficiency/SKILL.md)

Skill index: [`.cursor/skills/SKILL.md`](../../.cursor/skills/SKILL.md) and [`operating-system/skills/README.md`](operating-system/skills/README.md).

## Phase 1 freeze

Agents **may not write new signals**, strategy mutants, or birth curricula until Phase 1 of `lumina_research/` is complete. Do not build on `archive/birth-v1/`. Research may only propose; the Risk Core and `PromotionGate` remain the only promotion path.

## Bounded contexts (canonical under `lumina_core/`)

| Context | Path |
|---------|------|
| Safety | `lumina_core/safety/` |
| Evolution (KEEP fabric) | `lumina_core/evolution/` (PromotionGate, Twin, shadow, Event Bus wiring) |
| Research (propose-only) | `lumina_research/` |
| Risk Management | `lumina_core/risk/` |
| Agent Orchestration | `lumina_core/agent_orchestration/` |
| Trading Engine | `lumina_core/trading_engine/` (+ `engine/` composition/compat root) |

Experimental Birth-v1 / strategy-search lives in `archive/birth-v1/` only.

Operator UI SSOT: `tauri-app/` + FastAPI `lumina_os/backend/` (ADR-0016).

## Non-negotiable operating rules (pointers only)

- **Kapitaalbehoud is heilig in REAL mode** — fail-closed; shadow + approval gates.
- **Approval Twin** supplies *judgment* in SIM; never bypasses constitution, sandbox, shadow aperture, or REAL PromotionGate (ADR-0031/0032).
- **Inter-context** communication prefers the typed Event Bus; market path only via Admission Chain + Order Gatekeeper.
- **No god-files** — modular, testable components with clear interfaces.
- **Token efficiency** — classify tasks; Plan Mode for Medium/Complex/Safety-Critical; see skills.
- **No skip-gate path** — mutation, promotion and birth that would skip the Validation Gate must hard-fail via `PromotionGate` / `VALIDATION_GATE_REQUIRED`.

## Cursor-specific thin layer

Repo root [`.cursorrules`](../../.cursorrules) is a Cursor overlay. This file is the DNA index it refers to.
Skills under `.cursor/skills/` mirror `operating-system/skills/` where applicable.

## Debt and status

- Evolutionary debt: [`evolutionary-debt.md`](evolutionary-debt.md) (not `current-reality/` — that path is retired).
- Current status snapshot: [`current-status.md`](current-status.md).
- ADR index: [`docs/adr/README.md`](../../docs/adr/README.md).
