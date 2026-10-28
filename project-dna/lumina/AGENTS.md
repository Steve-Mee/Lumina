# LUMINA — Agent Instructions Index (SSOT pointer)

**Role of this file:** Index for humans and AI agents. It does **not** invent policy.
Binding laws live in the documents listed below. If this index conflicts with
`constitution.md`, the constitution wins.

## Read order (mandatory)

1. [`constitution.md`](constitution.md) — non-negotiable invariants
2. [`RESEARCH_CHARTER.md`](RESEARCH_CHARTER.md) — Validation Gate; research may only propose
3. [`north-star.md`](north-star.md) — mission compression
4. [`architecture.md`](architecture.md) — layers and bounded contexts (DNA view)
5. [`docs/architecture.md`](../../docs/architecture.md) — living architecture overview
6. [`docs/roadmap.md`](../../docs/roadmap.md) — capability waves (not release tags)
7. [`evolutionary-debt.md`](evolutionary-debt.md) — current evolvability debt catalog
8. [`operating-system/skills/README.md`](operating-system/skills/README.md) — agent skills

## Bounded contexts (canonical under `lumina_core/`)

| Context | Path |
|---------|------|
| Safety | `lumina_core/safety/` |
| Research | `lumina_core/research/` (propose-only Validation Gate; no Risk Core) |
| Evolution | `lumina_core/evolution/` (promotion/shadow/twin fabric; birth-v1 experiments in `archive/birth-v1/`) |
| Risk Management | `lumina_core/risk/` |
| Agent Orchestration | `lumina_core/agent_orchestration/` |
| Trading Engine | `lumina_core/trading_engine/` (+ `engine/` composition/compat root) |

Extended ownership: `audit/`, `broker/`, `reasoning/`, `rl/`, `state/`, `monitoring/`, `ports/`. Birth-v1 training lives under `archive/birth-v1/` (compat shims remain at `lumina_core/birth`).
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
