# 2026-06-11 — Phase 2 deliverable 3 slice 7: PolicyEngine typed bus history reads

**Classification**: Small (lineage read hygiene; no gate behavior change).

**Parents**: slice 6 residual, `decision_lineage` slice 3.

**Hypothesis**: Reusing `decision_context_id_from_event` in `PolicyEngine.execute_order` recovers lineage from typed `payload_instance` when metadata is sparse.

**Prediction (30d)**: Policy lineage tests pass; perfection + Track C gates stay green.

**Rollback**: Revert `policy_engine.py` + public export in `decision_lineage.py`.

## Done

- `_decision_context_id_from_event` promoted to public `decision_context_id_from_event`.
- `PolicyEngine.execute_order` uses helper for ctx recovery + prev_hash arb filter.
- Tests: `tests/engine/test_policy_engine_lineage.py` (3 unit).

## Phase 2 deliverable 3 — updated status

| Layer | Status |
|-------|--------|
| Critical subscribers | Done |
| `decision_lineage` / `dna_registry` | Done |
| Tracker + JSONL export | Done (slices 5–6) |
| `PolicyEngine` bus history | Done (slice 7) |
| Residual | `order_gatekeeper` history loops (metadata-first; separate slice if tightened) |

## Verify

```bash
py -3.13 -m pytest tests/engine/test_policy_engine_lineage.py tests/risk/test_decision_lineage_typed.py -q --tb=short
py -3.13 scripts/phase3_perfection_gate_verify.py
```
