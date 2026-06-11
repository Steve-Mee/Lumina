# 2026-06-04 — Phase 2 deliverable 3 slice 1: payload_instance on Event Bus

**Classification**: Contract infrastructure (backward compatible; no trading behavior change).

## Done

- `model_validate_payload_with_instance()` in `schemas.py`
- `DomainEvent.payload_instance` + `typed_payload(model)` helper
- `EventBus.publish` attaches instance for all validated topics (critical + registered)
- Test: `test_critical_topic_subscriber_receives_payload_instance`

## Remaining (deliverable 3 Yellow → Green)

- See slices 2–3 (`2026-06-04-phase2-d3-slice2-*.md`, `2026-06-04-phase2-d3-slice3-*.md`)
- `dna_registry` event handler; MC row when full migration declared

## Verify

```bash
python -m pytest tests/agent_orchestration/test_event_bus_contracts.py -q --tb=short
```

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

