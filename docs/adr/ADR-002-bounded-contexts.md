# ADR-002: Bounded Contexts in lumina_core/

**Status:** Implemented (physical migration complete)  
**Date:** 2026-04-23 | **Updated:** 2026-05-01  
**Deciders:** LUMINA Engineering (Steve + AI)

---

## Context

`lumina_core/engine/` had grown to 70+ Python modules in a single flat directory.
This made it difficult to reason about module responsibilities, created implicit
coupling between unrelated concerns, and increased cognitive load.

The `.cursorrules` standard explicitly requires:
> "Gebruik moderne patronen: bounded contexts, event-driven architecture,
> dependency injection, fail-closed design."

## Decision

Introduce bounded contexts as top-level sub-packages within `lumina_core/`:

| Package | Responsibility | Canonical modules |
|---------|---------------|-------------------|
| `lumina_core/risk/` | Capital protection, position sizing, session guards | `risk_controller`, `risk_allocator`, `risk_gates` |
| `lumina_core/trading_engine/` | Engine main loop, trade reconciliation | `lumina_engine`, `trade_reconciler` |
| `lumina_core/agent_orchestration/` | Agent coordination, event bus, blackboard | `event_bus`, `engine_bindings` |
| `lumina_core/safety/` | Constitutional guard, sandboxed mutation executor | `constitutional_guard`, `sandboxed_executor` |
| `lumina_core/evolution/` | DNA evolution, rollout, shadow deployment | `evolution_orchestrator`, `rollout`, `dna_registry` |

### Phase 1 (v53): Namespace packages with lazy re-exports

Each bounded context package had an `__init__.py` that re-exported classes
from their flat locations in `engine/` using lazy `__getattr__` to avoid
circular imports.  No files were moved.

### Phase 2 (v54 — this update): Physical migration

Risk modules physically migrated out of `engine/` into `lumina_core/risk/`:

```
lumina_core/risk/
    __init__.py          — lazy re-export surface
    risk_controller.py   — canonical: MarginTracker, RiskLimits, RiskState,
                           HardRiskController, risk_limits_from_config
    risk_allocator.py    — canonical: RiskAllocatorMixin (MC drawdown, VaR/ES)
    risk_gates.py        — canonical: RiskGatesMixin (pre-trade gates, kill-switch)
```

Deleted legacy engine shims (no backward-compat layer):
- `lumina_core/engine/risk_controller.py`
- `lumina_core/engine/risk_allocator.py`
- `lumina_core/engine/risk_gates.py`
- `lumina_core/engine/risk/__init__.py`

All active imports now use:
```python
from lumina_core.risk.risk_controller import HardRiskController, RiskLimits, risk_limits_from_config
from lumina_core.risk.risk_allocator import RiskAllocatorMixin
from lumina_core.risk.risk_gates import RiskGatesMixin
from lumina_core.risk import HardRiskController  # via __init__ lazy export
```

### Phase 3 (v55 — future): Remaining engine modules

Remaining engine modules to migrate:
- `engine/session_guard.py` → `lumina_core/risk/session_guard.py`
- `engine/margin_snapshot_provider.py` → `lumina_core/risk/margin_snapshot_provider.py`
- `engine/portfolio_var_allocator.py` → `lumina_core/risk/portfolio_var_allocator.py`
- `engine/constitutional_principles.py` → `lumina_core/safety/constitutional_principles.py`
- `engine/lumina_engine.py` → `lumina_core/trading_engine/lumina_engine.py` (physical)
- `engine/trade_reconciler.py` → `lumina_core/trading_engine/trade_reconciler.py` (physical)

## Consequences

- **Positive:** Risk domain is now a first-class bounded context with a clean API surface.
- **Positive:** No circular imports — risk modules have no engine-level dependencies.
- **Positive:** `lumina_core.risk.*` is the single import path; no duplicate paths.
- **Positive:** 58 unit tests + 17 integration tests pass without regression.
- **Positive:** Lint clean on all migrated files.
- **Neutral:** `lumina_core/engine/` still contains non-migrated modules; migration continues incrementally.
- **Negative:** Breaking change — no backward-compat shims. Acceptable because
  the app has not been used in production yet.

## Alternatives Considered

1. **Keep flat directory**: Simple but increasingly unmaintainable. Rejected.
2. **Keep engine/risk/ sub-package**: Extra indirection without domain clarity. Rejected in favour of top-level bounded contexts.
3. **Separate top-level packages outside lumina_core**: Too much structural change. Rejected.
