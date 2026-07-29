# LUMINA — Agent Instructions Index (SSOT pointer)

**Role of this file:** Index for humans and AI agents. It does **not** invent policy.
Binding laws live in the documents listed below. If this index conflicts with
`constitution.md`, the constitution wins.

## Read order (mandatory)

1. [`constitution.md`](constitution.md) — non-negotiable invariants
2. [`north-star.md`](north-star.md) — mission compression
3. [`architecture.md`](architecture.md) — layers and bounded contexts (DNA view)
4. [`docs/architecture.md`](../../docs/architecture.md) — living architecture overview
5. [`docs/roadmap.md`](../../docs/roadmap.md) — capability waves (not release tags)
6. [`evolutionary-debt.md`](evolutionary-debt.md) — current evolvability debt catalog
7. [`operating-system/skills/README.md`](operating-system/skills/README.md) — agent skills

## Bounded contexts (canonical under `lumina_core/`)

| Context | Path |
|---------|------|
| Safety | `lumina_core/safety/` |
| Evolution | `lumina_core/evolution/` |
| Risk Management | `lumina_core/risk/` |
| Agent Orchestration | `lumina_core/agent_orchestration/` |
| Trading Engine | `lumina_core/trading_engine/` (+ `engine/` composition/compat root) |

Extended ownership: `audit/`, `broker/`, `reasoning/`, `birth/`, `rl/`, `state/`, `monitoring/`, `ports/`.
Operator UI SSOT: `tauri-app/` + FastAPI `lumina_os/backend/` (ADR-0016).

## Non-negotiable operating rules (pointers only)

- **Kapitaalbehoud is heilig in REAL mode** — fail-closed; shadow + approval gates.
- **Approval Twin** supplies *judgment* in birth/SIM; never bypasses constitution, sandbox, shadow aperture, or REAL PromotionGate (ADR-0031/0032).
- **Inter-context** communication prefers the typed Event Bus; market path only via Admission Chain + Order Gatekeeper.
- **No god-files** — modular, testable components with clear interfaces.
- **Token efficiency** — classify tasks; Plan Mode for Medium/Complex/Safety-Critical; see skills.

## Cursor-specific thin layer

Repo root [`.cursorrules`](../../.cursorrules) is a Cursor overlay. This file is the DNA index it refers to.
Skills under `.cursor/skills/` mirror `operating-system/skills/` where applicable.

## Debt and status

- Evolutionary debt: [`evolutionary-debt.md`](evolutionary-debt.md) (not `current-reality/` — that path is retired).
- Current status snapshot: [`current-status.md`](current-status.md).
- ADR index: [`docs/adr/README.md`](../../docs/adr/README.md).
