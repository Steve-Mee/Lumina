# 2026-06-11 — Phase 2 deliverable 3 slice 8: OrderGatekeeper typed bus history

**Classification**: Safety-Critical adjacent (lineage read hygiene only; gate decisions unchanged).

**Parents**: slice 7 `PolicyEngine`, `decision_lineage` helpers.

**Hypothesis**: Lazy-imported `decision_context_id_from_event` / `event_hash_from_event` in gatekeeper history loops recover lineage from typed events without changing allow/deny outcomes.

**Prediction (30d)**: `test_order_gatekeeper_contracts` + slice 8 tests pass; Track C green.

**Rollback**: Revert `order_gatekeeper.py` history blocks; keep public helpers in `decision_lineage.py`.

## Done

- Main-bus proposal + dream + blackboard history loops use shared lineage helpers.
- `risk.policy.decision` prev_hash arb filter uses `decision_context_id_from_event`.
- Lazy imports avoid `order_gatekeeper` ↔ `decision_lineage` circular import at module load.
- Tests: `tests/engine/test_order_gatekeeper_typed_history.py` + helper tests in `test_decision_lineage_typed.py`.

## Phase 2 deliverable 3 — status

**Green-Yellow → Green at slice level** (critical path + history reads migrated).

## Verify

```bash
py -3.13 -m pytest tests/engine/test_order_gatekeeper_typed_history.py tests/test_order_gatekeeper_contracts.py -q --tb=short
py -3.13 scripts/phase3_perfection_gate_verify.py
```
