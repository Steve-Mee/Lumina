# Anti-Patterns

These are patterns we actively try to avoid in Lumina.

## High-Risk Anti-Patterns

- **Hiding or softening risk parameters** to improve backtest results.
- **Overfitting** without proper out-of-sample validation and regime awareness.
- **Making changes directly in Real mode** without prior validation in SIM/Paper.
- **Large, untestable modules** ("god files") that make evolution dangerous.
  - Example: `lumina_launcher.py` repeatedly grew beyond 3000+ lines (multiple major refactors in 2025-2026).
  - Example: `LuminaEngine` accumulated responsibilities across PnL, RL, backtesting, risk references, dream state, etc. (repeatedly flagged in architecture reviews as god object).
- **Tight coupling** between strategy logic and risk management.
- **Prolonged legacy compat layers in critical paths** — old wrappers in `engine/`, risk, and meta-agent layers kept "temporarily" for years, increasing regression surface and slowing bounded context adoption.

## Process Anti-Patterns

- Changing core logic without documenting the reasoning and evidence.
- Treating in-sample optimized parameters as robust.
- Ignoring transaction costs, slippage, or execution realities in backtesting.
- Adding complexity without clear evolutionary benefit.
- Bypassing Plan Mode for significant changes to risk or execution logic.
- **Frequent full state resets instead of proper migrations** — dozens of `backups/reset_*` folders created over short periods (May 2026) as workaround for instability rather than robust data evolution paths.
- **Large "big bang" refactors** instead of incremental decomposition (e.g. repeated full rewrites of launcher and engine monoliths rather than continuous modularization).
- Introducing new architectural capabilities (Blackboard, MetaAgentOrchestrator, Neural Command Deck) while leaving major monolith hotspots (`LuminaEngine`, legacy evolution modules) unaddressed.

## Cultural Anti-Patterns

- Performance chasing at the expense of truth-seeking.
- Fear of small, controlled experiments in SIM/Paper.
- Accumulating technical debt that makes future evolution harder.
- Relying on intuition instead of evidence when making decisions.
- **Building ambitious new systems on unclean foundations** — repeatedly adding complex layers (swarm agents, meta-orchestration, new UI decks) while core monoliths and legacy compat debt remain.
- **Treating recurring god-file growth as inevitable** instead of enforcing early modular boundaries and "no god file" rules in new code.
- **Over-tolerance for lingering compat layers** as "temporary" solutions that become permanent, slowing down the transition to clean bounded contexts and typed contracts.
- **Reset culture over resilience** — preferring to wipe state and start over rather than investing in proper migration, versioning, and backward-compatible evolution of system state.