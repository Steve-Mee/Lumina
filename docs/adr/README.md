# Architecture Decision Records (ADR)

Deze map bevat de canonieke ADR-reeks voor LUMINA.  
Doel: architectuurbeslissingen expliciet, toetsbaar en mission-aligned vastleggen volgens `.cursorrules`.

## Canonieke reeks

**Nieuwe ADR:** `python scripts/new_adr.py "Jouw titel"` — zie [CONTRIBUTING.md](../../CONTRIBUTING.md) (sectie *Een nieuwe ADR aanmaken*).

Nieuwe ADR's gebruiken het formaat `000x-title.md`.  
De kernmissie (extreme intellectual honesty, rigoureuze testing, radicale creativiteit) en het Elon Musk Mindset Protocol moeten expliciet worden benoemd in iedere ADR.

## Overzicht

| Nummer | Titel | Status | Datum | Link |
|---|---|---|---|---|
| 0000 | ADR Template | Proposed | 2026-05-01 | [0000-template.md](./0000-template.md) |
| 0001 | Introductie van Bounded Contexts en Centrale Event Bus | Accepted | 2026-05-01 | [0001-bounded-contexts-central-event-bus.md](./0001-bounded-contexts-central-event-bus.md) |
| 0002 | Shadow Deployment en Verplichte Human Approval voor Radicale Mutaties | Accepted | 2026-05-01 | [0002-shadow-deployment-human-approval.md](./0002-shadow-deployment-human-approval.md) |
| 0003 | Trading Constitution en Sandboxed Mutation Executor | Accepted | 2026-05-01 | [0003-trading-constitution-sandboxed-mutation-executor.md](./0003-trading-constitution-sandboxed-mutation-executor.md) |
| 0004 | Purged Cross-Validation, Order Book Replay en Reality Gap Penalty | Accepted | 2026-05-01 | [0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md](./0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md) |
| 0005 | Test Suite Overhaul met Markers, Timeouts en Isolated Fixtures | Proposed | 2026-05-01 | [0005-test-suite-overhaul-markers-timeouts-isolated-fixtures.md](./0005-test-suite-overhaul-markers-timeouts-isolated-fixtures.md) |
| 0006 | State Manager Cross-Process Locks en Busy Timeout | Accepted | 2026-05-02 | [0006-state-manager-cross-process-locks-and-busy-timeout.md](./0006-state-manager-cross-process-locks-and-busy-timeout.md) |
| 0007 | Promotion Gate voor REAL mode | Accepted | 2026-05-02 | [0007-promotion-gate-real-mode.md](./0007-promotion-gate-real-mode.md) |
| 0008 | LuminaEngine service decomposition | Accepted | 2026-05-02 | [0008-lumina-engine-service-decomposition.md](./0008-lumina-engine-service-decomposition.md) |
| 0009 | Thin Engine orchestrator en verwijdering van app-shim | Accepted | 2026-05-03 | [0009-thin-engine-orchestrator-and-app-shim-removal.md](./0009-thin-engine-orchestrator-and-app-shim-removal.md) |
| 0010 | Death of trusted path optimization | Accepted | — | [0010-death-of-trusted-path-optimization.md](./0010-death-of-trusted-path-optimization.md) |
| 0011 | Tauri lifecycle gate — backend SSOT for startup surface | Accepted | 2026-06-11 | [0011-tauri-lifecycle-gate-ssot.md](./0011-tauri-lifecycle-gate-ssot.md) |
| 0012 | Birth Phase v2 — Single Simulator SSOT | Accepted | 2026-06-11 | [0012-birth-phase-v2-single-simulator-ssot.md](./0012-birth-phase-v2-single-simulator-ssot.md) |
| 0013 | Birth Certificate v2 | Accepted | 2026-06-11 | [0013-birth-certificate-v2.md](./0013-birth-certificate-v2.md) |
| 0014 | Birth Curriculum + OOS Gate | Accepted | 2026-06-11 | [0014-birth-curriculum-oos-gate.md](./0014-birth-curriculum-oos-gate.md) |
| 0015 | RL observation SSOT 32-dim | Accepted | 2026-06-11 | [0015-rl-observation-ssot-32dim.md](./0015-rl-observation-ssot-32dim.md) |
| 0016 | Streamlit UI retirement | Accepted | 2026-06-12 | [0016-streamlit-ui-retirement.md](./0016-streamlit-ui-retirement.md) |
| 0018 | RL observation trend features 43-dim | Accepted | 2026-06-27 | [0018-rl-observation-trend-features-43dim.md](./0018-rl-observation-trend-features-43dim.md) |
| 0019 | Expectancy-oriented RL reward shaping | Accepted | 2026-06-27 | [0019-expectancy-reward-shaping.md](./0019-expectancy-reward-shaping.md) |
| 0020 | Stage 1 intra-curriculum easy→hard | Accepted | 2026-06-27 | [0020-stage1-intra-curriculum.md](./0020-stage1-intra-curriculum.md) |
| 0021 | Birth meta controller (learning observation & recovery SSOT) | Accepted | 2026-06-27 | [0021-birth-meta-controller.md](./0021-birth-meta-controller.md) |
| 0022 | Meta self-eval strategy probe | Accepted | 2026-06-27 | [0022-meta-self-eval-strategy-probe.md](./0022-meta-self-eval-strategy-probe.md) |
| 0023 | Birth plateau evolution escalator | Accepted | 2026-06-27 | [0023-birth-plateau-evolution-escalator.md](./0023-birth-plateau-evolution-escalator.md) |
| 0024 | Lumina attention notifications | Accepted | 2026-06-27 | [0024-lumina-attention-notifications.md](./0024-lumina-attention-notifications.md) |
| 0025 | Lumina milestone notifications | Accepted | 2026-06-28 | [0025-lumina-milestone-notifications.md](./0025-lumina-milestone-notifications.md) |
| 0026 | Post-birth Evolution Proof gate | Accepted | 2026-06-27 | [0026-evolution-proof-gate.md](./0026-evolution-proof-gate.md) |
| 0027 | Lumina maturation ladder | Accepted | 2026-06-27 | [0027-lumina-maturation-ladder.md](./0027-lumina-maturation-ladder.md) |
| 0028 | Operator notification matrix | Accepted | 2026-06-27 | [0028-lumina-operator-notification-matrix.md](./0028-lumina-operator-notification-matrix.md) |
| 0029 | NinjaTrader native bridge | Accepted | — | [0029-ninjatrader-native-bridge.md](./0029-ninjatrader-native-bridge.md) |
| 0030 | Architecture Meta-Controller (sandboxed self-improvement of architecture) | Accepted | 2026-07-13 | [0030-architecture-meta-controller.md](./0030-architecture-meta-controller.md) |
| 0031 | Approval Twin on Event Bus + primary auto-approval | Accepted | 2026-07-13 | [0031-approval-twin-event-bus.md](./0031-approval-twin-event-bus.md) |
| 0032 | Approval Twin as Human Replacement Layer | Accepted | 2026-07-14 | [0032-approval-twin-human-replacement-layer.md](./0032-approval-twin-human-replacement-layer.md) |
| 0033 | Trading Code Evolution Prototype (sandbox + Twin + constitution) | Accepted | 2026-07-15 | [0033-trading-code-evolution-prototype.md](./0033-trading-code-evolution-prototype.md) |
| 0034 | Phase 2 autonomy foundation | Accepted | — | [0034-phase2-autonomy-foundation.md](./0034-phase2-autonomy-foundation.md) |
| 0035 | Execution Fabric gRPC (supersedes WS wire protocol) | Accepted | 2026-07-20 | [0035-execution-fabric-grpc.md](./0035-execution-fabric-grpc.md) |
| 0036 | Birth exit vs maturation continuum (survival ≠ Perfect Birth / REAL) | Accepted | 2026-08-06 | [0036-birth-exit-vs-maturation.md](./0036-birth-exit-vs-maturation.md) |
| 0037 | Self-play lab (Phase 0 scaffold; no birth-loop apply) | Accepted | 2026-08-07 | [0037-self-play-design.md](./0037-self-play-design.md) |

## Legacy notitie

Historische `ADR-00x-*` documenten blijven voorlopig aanwezig voor bestaande referenties.  
Nieuwe beslissingen worden uitsluitend toegevoegd aan de `000x`-reeks.
