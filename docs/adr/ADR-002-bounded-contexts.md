# ADR-002: Bounded Contexts in lumina_core/engine/

**Status:** Accepted (namespace phase complete; physical migration pending)  
**Date:** 2026-04-23  
**Deciders:** LUMINA Engineering (Steve + AI)

---

## Context

`lumina_core/engine/` has grown to 70+ Python modules in a single flat directory.
This makes it difficult to reason about module responsibilities, creates implicit
coupling between unrelated concerns, and increases the cognitive load for new
contributors.

The `.cursorrules` standard explicitly requires:
> "Gebruik moderne patronen: bounded contexts, event-driven architecture,
> dependency injection, fail-closed design."

## Decision

Introduce five bounded contexts as sub-packages within `lumina_core/engine/`:

| Package | Responsibility | Key modules |
|---------|---------------|-------------|
| `engine/execution/` | Order routing, trade reconciliation, engine main loop | `lumina_engine`, `order_gatekeeper`, `trade_reconciler` |
| `engine/analysis/` | Market analysis, regime detection, reasoning | `analysis_service`, `regime_detector` |
| `engine/data/` | OHLCV ingestion, tape reading, market data management | `market_data_service`, `market_data_manager`, `tape_reading_agent` |
| `engine/agents/` | Agent coordination (emotional twin, swarm, meta orchestrator) | `emotional_twin_agent`, `meta_agent_orchestrator`, `swarm_manager` |
| `engine/risk/` | Capital protection, position sizing, session guards, constitutional principles | `risk_controller`, `risk_gates`, `session_guard`, `constitutional_principles` |

### Phase 1 (v53 — this ADR): Namespace packages

Each sub-package has an `__init__.py` that re-exports the canonical classes
from their current flat locations in `engine/`.  No files are moved.  This
establishes the bounded context API surface without breaking any existing imports.

```python
# Usage after Phase 1:
from lumina_core.engine.risk import HardRiskController, ConstitutionalChecker
from lumina_core.engine.execution import LuminaEngine, OrderGatekeeper
```

### Phase 2 (v54 — future): Physical migration

Files are physically moved to their respective sub-packages.  The flat
`engine/` `__init__.py` retains backward-compat re-exports for one version.
CI enforces no direct imports from `lumina_core.engine.risk_controller` (must
use `lumina_core.engine.risk`).

## Consequences

- **Positive:** Bounded contexts are immediately navigable in IDEs and grep.
- **Positive:** New modules go into the correct context from day one.
- **Positive:** Backward compatible — all existing imports continue to work.
- **Neutral:** Two import paths exist during the migration window (v53–v54).
- **Negative:** Phase 2 (physical migration) requires a large diff; must be done
  in a dedicated sprint with full test coverage.

## Alternatives Considered

1. **Keep flat directory**: Simple but increasingly unmaintainable.  Rejected.
2. **Full immediate migration**: Correct but risky without full test coverage.
   Deferred to v54.
3. **Separate top-level packages**: Too much structural change.  Rejected.
