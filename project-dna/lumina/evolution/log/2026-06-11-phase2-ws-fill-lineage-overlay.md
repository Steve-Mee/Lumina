# 2026-06-11 — Phase 2 deliverable 2 residual: WS/poll fill lineage overlay

**Classification**: Safety-Critical adjacent (broker metadata only; fail-open).

**Parent**: `2026-06-06-phase2-live-broker-lineage-wiring.md` + MC deliverable 2 gap.

## Hypothesis

CrossTrade `_pending_lineage` (populated at submit) can be shared across `get_fills()`, WS `ingest_fill_event`, and poll `ingest_fill_event` via `lookup_pending_lineage()`, so live production fills publish typed `execution.fill.received` with real `decision_context_id` + `prev_hash`.

## Done

- `CrossTradeBroker.lookup_pending_lineage()` + `get_fills()` refactor
- `TradeReconciler._overlay_pending_broker_lineage()` on WS/poll ingest (via `_resolve_broker_for_lineage`)
- Tests: broker helper, get_fills regression, WS frame overlay, no-broker no-op

## Verify

```bash
python -m pytest tests/engine/test_trade_reconciler.py tests/test_broker_bridge.py::test_cross_trade_lookup_pending_lineage_peek_and_consume tests/test_broker_bridge.py::test_cross_trade_get_fills_overlays_pending_lineage -q --tb=short
python scripts/phase3_track_c_gate_verify.py
```

## Rollback

Revert `broker_bridge.py` + `trade_reconciler.py` + tests; pending map is in-memory only.

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

